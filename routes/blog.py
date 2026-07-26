"""Public community blog reads and authenticated, moderated writes."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, time, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func

from core.route_dependencies import Depends, HTTPException, Query, Request, get_db, rate_limit, verify_supabase_jwt
from models import BlogComment, BlogPost, BlogReaction, User
from services.blog_moderation_service import moderate_text
from services.user_service import get_or_create_user


router = APIRouter(prefix="/api/v1/blog", tags=["blog"])

ALLOWED_CATEGORIES = {
    "Technology",
    "Artificial Intelligence",
    "Design",
    "Data Science",
    "Security",
    "Cloud",
    "Career",
}
CATEGORY_ALIASES = {
    "Teknoloji": "Technology",
    "Yapay Zeka": "Artificial Intelligence",
    "Tasarım": "Design",
    "Veri Bilimi": "Data Science",
    "Güvenlik": "Security",
    "Kariyer": "Career",
}


class BlogPostCreate(BaseModel):
    title: str = Field(min_length=8, max_length=160)
    content: str = Field(min_length=40, max_length=12000)
    category: str = Field(max_length=32)
    tags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("title", "content")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = CATEGORY_ALIASES.get(value.strip(), value.strip())
        if normalized not in ALLOWED_CATEGORIES:
            raise ValueError("Unsupported category")
        return normalized

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        clean: list[str] = []
        for tag in tags:
            value = re.sub(r"[^\w +#.-]", "", str(tag), flags=re.UNICODE).strip()[:32]
            if value and value.casefold() not in {item.casefold() for item in clean}:
                clean.append(value)
        return clean[:5]


class BlogCommentCreate(BaseModel):
    text: str = Field(min_length=2, max_length=1500)
    parent_id: int | None = None

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class BlogReactionToggle(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: int


def _author_name(user: User) -> str:
    local = (user.email or "").split("@", 1)[0].replace(".", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in local.split())[:80] or "Member"


def _author_payload(user: User) -> dict:
    return {"name": _author_name(user), "role": user.role or "individual", "plan": user.plan_type or "free"}


def _like_tokens(count: int) -> list[str]:
    # Keep the existing UI contract without exposing who reacted.
    return [f"reaction-{index}" for index in range(max(0, count))]


def _post_payload(db, post: BlogPost, *, include_comments: bool = False) -> dict:
    author = db.query(User).filter(User.id == post.author_user_id).first()
    post_likes = (
        db.query(func.count(BlogReaction.id))
        .filter(BlogReaction.target_type == "post", BlogReaction.target_id == post.id)
        .scalar()
        or 0
    )
    top_comments = (
        db.query(BlogComment)
        .filter(
            BlogComment.post_id == post.id,
            BlogComment.status == "published",
            BlogComment.parent_id.is_(None),
        )
        .order_by(BlogComment.created_at.asc())
        .all()
    )
    comment_count = (
        db.query(func.count(BlogComment.id))
        .filter(BlogComment.post_id == post.id, BlogComment.status == "published")
        .scalar()
        or 0
    )
    serialized_comments = []
    if include_comments:
        for comment in top_comments:
            comment_author = db.query(User).filter(User.id == comment.author_user_id).first()
            comment_likes = (
                db.query(func.count(BlogReaction.id))
                .filter(BlogReaction.target_type == "comment", BlogReaction.target_id == comment.id)
                .scalar()
                or 0
            )
            replies = (
                db.query(BlogComment)
                .filter(BlogComment.parent_id == comment.id, BlogComment.status == "published")
                .order_by(BlogComment.created_at.asc())
                .all()
            )
            serialized_replies = []
            for reply in replies:
                reply_author = db.query(User).filter(User.id == reply.author_user_id).first()
                serialized_replies.append(
                    {
                        "id": str(reply.id),
                        "author": _author_payload(reply_author),
                        "text": reply.text,
                        "createdAt": reply.created_at.isoformat(),
                        "likes": [],
                    }
                )
            serialized_comments.append(
                {
                    "id": str(comment.id),
                    "author": _author_payload(comment_author),
                    "text": comment.text,
                    "createdAt": comment.created_at.isoformat(),
                    "likes": _like_tokens(comment_likes),
                    "replies": serialized_replies,
                }
            )
    return {
        "id": str(post.id),
        "title": post.title,
        "content": post.content,
        "summary": post.summary,
        "category": post.category,
        "slug": post.slug,
        "image": "",
        "author": _author_payload(author),
        "tags": post.tags or [],
        "createdAt": post.created_at.isoformat(),
        "views": post.view_count or 0,
        "likes": _like_tokens(post_likes),
        "comments": serialized_comments if include_comments else _like_tokens(comment_count),
    }


def _db_user(db, auth_user: dict) -> User:
    return get_or_create_user(db, auth_user.get("user_id"), auth_user.get("email"))


def _moderate_or_reject(text: str) -> None:
    decision = moderate_text(text)
    if decision.allowed:
        return
    if decision.reason == "moderation_unavailable":
        raise HTTPException(status_code=503, detail="Content moderation is temporarily unavailable")
    raise HTTPException(status_code=422, detail="Content did not pass community safety checks")


@router.get("/posts")
@rate_limit("30/minute")
def list_blog_posts(
    request: Request,
    db=Depends(get_db),
    category: str | None = Query(None, max_length=32),
    search: str | None = Query(None, max_length=100),
    limit: int = Query(40, ge=1, le=100),
):
    query = db.query(BlogPost).filter(BlogPost.status == "published")
    if category:
        query = query.filter(BlogPost.category == CATEGORY_ALIASES.get(category, category))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(BlogPost.title.ilike(pattern) | BlogPost.summary.ilike(pattern))
    posts = query.order_by(BlogPost.created_at.desc()).limit(limit).all()
    return {"posts": [_post_payload(db, post) for post in posts]}


@router.get("/posts/{slug}")
@rate_limit("60/minute")
def get_blog_post(slug: str, request: Request, db=Depends(get_db)):
    post = db.query(BlogPost).filter(BlogPost.slug == slug, BlogPost.status == "published").first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.view_count = (post.view_count or 0) + 1
    db.commit()
    db.refresh(post)
    return {"post": _post_payload(db, post, include_comments=True)}


@router.post("/posts", status_code=201)
@rate_limit("5/minute")
def create_blog_post(
    body: BlogPostCreate,
    request: Request,
    auth_user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    user = _db_user(db, auth_user)
    start_today = datetime.combine(datetime.now(timezone.utc).date(), time.min).replace(tzinfo=None)
    count_today = (
        db.query(func.count(BlogPost.id))
        .filter(BlogPost.author_user_id == user.id, BlogPost.created_at >= start_today)
        .scalar()
        or 0
    )
    limit = 999 if user.role == "admin" else 10 if user.role == "recruiter" or user.plan_type in ("pro", "enterprise") else 3
    if count_today >= limit:
        raise HTTPException(status_code=429, detail="Daily post limit reached")
    _moderate_or_reject(f"{body.title}\n\n{body.content}")
    base_slug = re.sub(r"[^a-z0-9]+", "-", body.title.casefold()).strip("-")[:170] or "post"
    slug = f"{base_slug}-{secrets.token_hex(4)}"
    summary = re.sub(r"\s+", " ", body.content).strip()[:317]
    if len(body.content) > 317:
        summary += "..."
    post = BlogPost(
        author_user_id=user.id,
        title=body.title,
        content=body.content,
        summary=summary,
        category=body.category,
        slug=slug,
        tags=body.tags,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"post": _post_payload(db, post, include_comments=True), "quota": {"used": count_today + 1, "limit": limit}}


@router.post("/posts/{post_id}/comments", status_code=201)
@rate_limit("10/minute")
def create_blog_comment(
    post_id: int,
    body: BlogCommentCreate,
    request: Request,
    auth_user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    user = _db_user(db, auth_user)
    post = db.query(BlogPost).filter(BlogPost.id == post_id, BlogPost.status == "published").first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if body.parent_id is not None:
        parent = (
            db.query(BlogComment)
            .filter(
                BlogComment.id == body.parent_id,
                BlogComment.post_id == post_id,
                BlogComment.parent_id.is_(None),
                BlogComment.status == "published",
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=404, detail="Parent comment not found")
    _moderate_or_reject(body.text)
    db.add(
        BlogComment(
            post_id=post.id,
            parent_id=body.parent_id,
            author_user_id=user.id,
            text=body.text,
        )
    )
    db.commit()
    return {"post": _post_payload(db, post, include_comments=True)}


@router.post("/reactions")
@rate_limit("20/minute")
def toggle_blog_reaction(
    body: BlogReactionToggle,
    request: Request,
    auth_user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    user = _db_user(db, auth_user)
    target = (
        db.query(BlogPost).filter(BlogPost.id == body.target_id, BlogPost.status == "published").first()
        if body.target_type == "post"
        else db.query(BlogComment).filter(BlogComment.id == body.target_id, BlogComment.status == "published").first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Reaction target not found")
    existing = (
        db.query(BlogReaction)
        .filter(
            BlogReaction.user_id == user.id,
            BlogReaction.target_type == body.target_type,
            BlogReaction.target_id == body.target_id,
        )
        .first()
    )
    liked = existing is None
    if existing:
        db.delete(existing)
    else:
        db.add(BlogReaction(user_id=user.id, target_type=body.target_type, target_id=body.target_id))
    db.commit()
    count = (
        db.query(func.count(BlogReaction.id))
        .filter(BlogReaction.target_type == body.target_type, BlogReaction.target_id == body.target_id)
        .scalar()
        or 0
    )
    return {"liked": liked, "count": count}
