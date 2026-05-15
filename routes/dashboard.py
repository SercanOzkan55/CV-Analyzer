"""Dashboard, favorites, sharing, benchmark, and usage endpoints.

This router was extracted from main.py to reduce application bootstrap size.
It intentionally pulls transitional shared symbols from the already-loading
main module; later passes can move those shared helpers into services.
"""

from fastapi import APIRouter
from core.runtime_bridge import main_module as _main_module
from core.route_dependencies import *  # noqa: F403


router = APIRouter(tags=["dashboard"])

class FavoriteToggleRequest(BaseModel):
    analysis_id: int
    note: str = ""


@router.get("/api/v1/favorites")
def list_favorites(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
):
    """List user's favorite/bookmarked analyses."""
    from models import Favorite

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    favs = (
        db.query(Favorite)
        .filter(Favorite.user_id == db_user.id)
        .order_by(Favorite.created_at.desc())
        .limit(limit)
        .all()
    )

    # Also fetch associated analysis data
    analysis_ids = [f.analysis_id for f in favs]
    analyses = {}
    if analysis_ids:
        records = (
            db.query(Analysis)
            .filter(Analysis.id.in_(analysis_ids), Analysis.user_id == db_user.id)
            .all()
        )
        analyses = {a.id: a for a in records}

    return {
        "favorites": [
            {
                "id": f.id,
                "analysis_id": f.analysis_id,
                "note": f.note or "",
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "analysis": {
                    "similarity_score": a.similarity_score,
                    "interpretation": a.interpretation,
                    "job_title": a.job_title,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                } if (a := analyses.get(f.analysis_id)) else None,
            }
            for f in favs
        ]
    }


@router.post("/api/v1/favorites/toggle")
def toggle_favorite(
    body: FavoriteToggleRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Toggle favorite status for an analysis. Returns { favorited: bool }."""
    from models import Favorite

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _get_owned_analysis_or_404(db, body.analysis_id, db_user)

    # Check plan limit for free users
    if db_user.plan_type == "free":
        fav_count = db.query(Favorite).filter(Favorite.user_id == db_user.id).count()
        if fav_count >= 5:
            # Check if we're removing (toggling off) — allow that
            existing = (
                db.query(Favorite)
                .filter(Favorite.user_id == db_user.id, Favorite.analysis_id == body.analysis_id)
                .first()
            )
            if not existing:
                raise HTTPException(
                    status_code=403,
                    detail="Free plan limited to 5 favorites. Upgrade for unlimited.",
                )

    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == db_user.id, Favorite.analysis_id == body.analysis_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False, "analysis_id": body.analysis_id}
    else:
        fav = Favorite(
            user_id=db_user.id,
            analysis_id=body.analysis_id,
            note=body.note[:200] if body.note else "",
        )
        db.add(fav)
        db.commit()
        return {"favorited": True, "analysis_id": body.analysis_id, "id": fav.id}


@router.get("/api/v1/favorites/ids")
def get_favorite_ids(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Quick lookup: returns list of analysis_ids that are favorited."""
    from models import Favorite

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    ids = (
        db.query(Favorite.analysis_id)
        .filter(Favorite.user_id == db_user.id)
        .all()
    )
    return {"ids": [r[0] for r in ids]}


# ── Job Description Templates CRUD ──────────────────────────────


class JDTemplateCreate(BaseModel):
    title: str
    description: str


@router.get("/api/v1/jd-templates")
def list_jd_templates(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """List user's saved job description templates."""
    from models import JobTemplate

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    templates = (
        db.query(JobTemplate)
        .filter(JobTemplate.user_id == db_user.id)
        .order_by(JobTemplate.created_at.desc())
        .all()
    )
    return {
        "templates": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in templates
        ]
    }


@router.post("/api/v1/jd-templates")
def create_jd_template(
    body: JDTemplateCreate,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Create a saved JD template. Free: max 3, Pro: unlimited."""
    from models import JobTemplate

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    if not body.title.strip() or not body.description.strip():
        raise HTTPException(status_code=400, detail="Title and description required")

    effective_plan = _resolve_effective_plan(db, db_user)
    if effective_plan == "free":
        count = db.query(JobTemplate).filter(JobTemplate.user_id == db_user.id).count()
        if count >= 3:
            raise HTTPException(
                status_code=403,
                detail="Free plan limited to 3 templates. Upgrade for unlimited.",
            )

    tmpl = JobTemplate(
        user_id=db_user.id,
        title=body.title.strip()[:120],
        description=body.description.strip()[:5000],
    )
    db.add(tmpl)
    db.commit()
    return {"id": tmpl.id, "title": tmpl.title}


@router.delete("/api/v1/jd-templates/{template_id}")
def delete_jd_template(
    template_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import JobTemplate

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    tmpl = (
        db.query(JobTemplate)
        .filter(JobTemplate.id == template_id, JobTemplate.user_id == db_user.id)
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tmpl)
    db.commit()
    return {"deleted": True}


# ── Analysis Sharing (public link) ──────────────────────────────


class ShareRequest(BaseModel):
    analysis_id: int


@router.post("/api/v1/share")
def create_share_link(
    body: ShareRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Create a public share link for an analysis (Pro feature)."""
    from models import AnalysisShare
    import secrets

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    effective_plan = _resolve_effective_plan(db, db_user)
    if effective_plan == "free":
        raise HTTPException(
            status_code=403,
            detail="Sharing is a Pro feature. Upgrade to share analyses.",
        )
    _get_owned_analysis_or_404(db, body.analysis_id, db_user)

    # Check if share already exists
    existing = (
        db.query(AnalysisShare)
        .filter(
            AnalysisShare.user_id == db_user.id,
            AnalysisShare.analysis_id == body.analysis_id,
            AnalysisShare.is_active == True,
        )
        .first()
    )
    if existing:
        return {"share_token": existing.share_token, "already_exists": True}

    token = secrets.token_urlsafe(32)
    share = AnalysisShare(
        user_id=db_user.id,
        analysis_id=body.analysis_id,
        share_token=token,
    )
    db.add(share)
    db.commit()
    return {"share_token": token, "already_exists": False}


@router.delete("/api/v1/share/{share_token}")
def revoke_share_link(
    share_token: str,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import AnalysisShare

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    share = (
        db.query(AnalysisShare)
        .filter(AnalysisShare.share_token == share_token, AnalysisShare.user_id == db_user.id)
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")
    share.is_active = False
    db.commit()
    return {"revoked": True}


@router.get("/api/v1/shared/{share_token}")
def view_shared_analysis(
    share_token: str,
    db=Depends(get_db),
):
    """Public endpoint — no auth required. View shared analysis result."""
    from models import AnalysisShare

    share = (
        db.query(AnalysisShare)
        .filter(AnalysisShare.share_token == share_token, AnalysisShare.is_active == True)
        .first()
    )
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found or expired")

    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == share.analysis_id, Analysis.user_id == share.user_id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    share.views = (share.views or 0) + 1
    db.commit()

    return {
        "score": analysis.similarity_score,
        "interpretation": analysis.interpretation,
        "job_title": analysis.job_title,
        "result": analysis.result if isinstance(analysis.result, dict) else {},
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "views": share.views,
    }


# ── History CSV Export ──────────────────────────────────────────


@router.get("/api/v1/history/export")
def export_history_csv(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Export user's analysis history as CSV (Pro feature)."""
    import csv
    import io

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    effective_plan = _resolve_effective_plan(db, db_user)
    if effective_plan == "free":
        raise HTTPException(
            status_code=403,
            detail="CSV export is a Pro feature. Upgrade to export history.",
        )

    records = (
        db.query(Analysis)
        .filter(Analysis.user_id == db_user.id)
        .order_by(Analysis.created_at.desc())
        .limit(500)
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Job Title", "Score", "Interpretation", "ATS Score", "Semantic", "Keyword", "Skill", "Experience"])
    for r in records:
        res = r.result if isinstance(r.result, dict) else {}
        writer.writerow([
            r.created_at.isoformat() if r.created_at else "",
            r.job_title or "",
            r.similarity_score or 0,
            r.interpretation or "",
            res.get("ats_score", ""),
            res.get("semantic_score", ""),
            res.get("keyword_score", ""),
            res.get("skill_score", ""),
            res.get("experience_score", ""),
        ])

    from starlette.responses import StreamingResponse
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cv_analysis_history.csv"},
    )


# ── Analysis Notes CRUD ─────────────────────────────────────────


class NoteRequest(BaseModel):
    analysis_id: int
    content: str


@router.post("/api/v1/notes")
def save_analysis_note(
    body: NoteRequest,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Save or update a note on an analysis."""
    from models import AnalysisNote

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Note content required")
    _get_owned_analysis_or_404(db, body.analysis_id, db_user)

    existing = (
        db.query(AnalysisNote)
        .filter(AnalysisNote.user_id == db_user.id, AnalysisNote.analysis_id == body.analysis_id)
        .first()
    )

    if existing:
        existing.content = body.content.strip()[:2000]
        existing.updated_at = datetime.utcnow()
        db.commit()
        return {"id": existing.id, "updated": True}
    else:
        note = AnalysisNote(
            user_id=db_user.id,
            analysis_id=body.analysis_id,
            content=body.content.strip()[:2000],
        )
        db.add(note)
        db.commit()
        return {"id": note.id, "updated": False}


@router.get("/api/v1/notes/{analysis_id}")
def get_analysis_note(
    analysis_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import AnalysisNote

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _get_owned_analysis_or_404(db, analysis_id, db_user)

    note = (
        db.query(AnalysisNote)
        .filter(AnalysisNote.user_id == db_user.id, AnalysisNote.analysis_id == analysis_id)
        .first()
    )
    if not note:
        return {"content": "", "exists": False}
    return {
        "id": note.id,
        "content": note.content,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
        "exists": True,
    }


@router.delete("/api/v1/notes/{analysis_id}")
def delete_analysis_note(
    analysis_id: int,
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    from models import AnalysisNote

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)
    _get_owned_analysis_or_404(db, analysis_id, db_user)

    note = (
        db.query(AnalysisNote)
        .filter(AnalysisNote.user_id == db_user.id, AnalysisNote.analysis_id == analysis_id)
        .first()
    )
    if note:
        db.delete(note)
        db.commit()
    return {"deleted": True}


# ── Usage Streak ────────────────────────────────────────────────


@router.get("/api/v1/usage-streak")
def get_usage_streak(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Return current and longest usage streaks for gamification."""
    from models import UsageDaily
    from datetime import timedelta

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    rows = (
        db.query(UsageDaily.date)
        .filter(UsageDaily.user_id == db_user.id, UsageDaily.count > 0)
        .order_by(UsageDaily.date.desc())
        .limit(365)
        .all()
    )

    if not rows:
        return {"current_streak": 0, "longest_streak": 0, "total_active_days": 0}

    dates = sorted(set(r[0].date() if hasattr(r[0], 'date') else r[0] for r in rows), reverse=True)
    today = datetime.utcnow().date()

    # Current streak
    current = 0
    for i, d in enumerate(dates):
        expected = today - timedelta(days=i)
        if d == expected:
            current += 1
        else:
            break

    # Longest streak
    longest = 1
    streak = 1
    sorted_asc = sorted(dates)
    for i in range(1, len(sorted_asc)):
        if (sorted_asc[i] - sorted_asc[i - 1]).days == 1:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 1

    return {
        "current_streak": current,
        "longest_streak": max(longest, current),
        "total_active_days": len(dates),
    }


# ── Dashboard Insights ──────────────────────────────────────────


@router.get("/api/v1/insights")
def get_dashboard_insights(
    user=Depends(verify_supabase_jwt),
    db=Depends(get_db),
):
    """Return AI-powered insights and tips based on user's analysis history."""
    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    records = (
        db.query(Analysis)
        .filter(Analysis.user_id == db_user.id)
        .order_by(Analysis.created_at.desc())
        .limit(20)
        .all()
    )

    if not records:
        return {"insights": [], "stats": {}}

    scores = [r.similarity_score for r in records if r.similarity_score]
    avg_score = sum(scores) / len(scores) if scores else 0
    best_score = max(scores) if scores else 0
    worst_score = min(scores) if scores else 0
    total = len(records)

    # Trend: compare last 5 vs previous 5
    recent_5 = scores[:5] if len(scores) >= 5 else scores
    prev_5 = scores[5:10] if len(scores) >= 10 else []
    trend = "improving" if prev_5 and (sum(recent_5)/len(recent_5)) > (sum(prev_5)/len(prev_5)) else "stable"
    if prev_5 and (sum(recent_5)/len(recent_5)) < (sum(prev_5)/len(prev_5)) - 5:
        trend = "declining"

    # Find weakest dimensions
    dim_totals = {"semantic": [], "keyword": [], "skill": [], "experience": [], "ats": []}
    for r in records:
        res = r.result if isinstance(r.result, dict) else {}
        for dim in dim_totals:
            val = res.get(f"{dim}_score")
            if val is not None:
                dim_totals[dim].append(val)

    dim_avgs = {k: sum(v)/len(v) if v else 0 for k, v in dim_totals.items()}
    weakest = sorted(dim_avgs.items(), key=lambda x: x[1])[:2]

    insights = []

    if trend == "improving":
        insights.append({
            "type": "positive",
            "icon": "📈",
            "text": f"Skorlarınız yükseliyor! Son analizlerde ortalama {sum(recent_5)/len(recent_5):.0f}%",
        })
    elif trend == "declining":
        insights.append({
            "type": "warning",
            "icon": "📉",
            "text": "Son analizlerde skorlarınız düşüş eğiliminde. Önerilere dikkat edin.",
        })

    if weakest and weakest[0][1] < 60:
        dim_name = {"semantic": "Semantik uyum", "keyword": "Anahtar kelime", "skill": "Yetenek eşleşme", "experience": "Deneyim", "ats": "ATS uyumluluk"}.get(weakest[0][0], weakest[0][0])
        insights.append({
            "type": "tip",
            "icon": "💡",
            "text": f"En zayıf alanınız: {dim_name} (ort. {weakest[0][1]:.0f}%). Bu boyutu iyileştirmeye odaklanın.",
        })

    if total >= 5 and avg_score >= 70:
        insights.append({
            "type": "achievement",
            "icon": "🏆",
            "text": f"{total} analiz tamamlandı, ortalama {avg_score:.0f}%. Harika gidiyorsunuz!",
        })

    if best_score >= 90:
        insights.append({
            "type": "positive",
            "icon": "⭐",
            "text": f"En iyi skorunuz {best_score:.0f}%! Mükemmel CV-iş uyumu.",
        })

    if total < 3:
        insights.append({
            "type": "tip",
            "icon": "🚀",
            "text": "Daha fazla analiz yaparak trend verilerinizi zenginleştirin.",
        })

    return {
        "insights": insights[:4],
        "stats": {
            "avg_score": round(avg_score, 1),
            "best_score": round(best_score, 1),
            "worst_score": round(worst_score, 1),
            "total": total,
            "trend": trend,
            "weakest_dim": weakest[0][0] if weakest else None,
        },
    }


# ── Global ATS Benchmark Endpoints (before catch-all {analysis_id}) ──


# ── Blog Feed: trending tech articles from Dev.to ───────────────────
_blog_feed_cache: dict = {"data": [], "ts": 0}

@router.get("/api/v1/blog/feed")
@rate_limit("10/minute")
async def get_blog_feed(request: Request):
    """Return trending tech/career articles from Dev.to (cached 4h)."""
    import time as _time
    import httpx

    now = _time.time()
    if _blog_feed_cache["data"] and (now - _blog_feed_cache["ts"]) < 14400:
        return {"articles": _blog_feed_cache["data"]}

    tags = ["career", "webdev", "programming", "ai", "python", "javascript"]
    articles = []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            for tag in tags[:3]:
                resp = await client.get(
                    "https://dev.to/api/articles",
                    params={"tag": tag, "top": 1, "per_page": 3},
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200:
                    for item in resp.json():
                        # Sanitize URLs - only allow https
                        raw_url = str(item.get("url") or "")
                        raw_image = str(item.get("cover_image") or item.get("social_image") or "")
                        raw_avatar = str(item.get("user", {}).get("profile_image_90") or "")
                        articles.append({
                            "id": item.get("id"),
                            "title": str(item.get("title") or "")[:200],
                            "summary": str(item.get("description") or "")[:500],
                            "url": raw_url if raw_url.startswith("https://") else "",
                            "image": raw_image if raw_image.startswith("https://") else "",
                            "author": str(item.get("user", {}).get("name") or "")[:100],
                            "author_avatar": raw_avatar if raw_avatar.startswith("https://") else "",
                            "published_at": item.get("published_at", ""),
                            "reading_time": item.get("reading_time_minutes", 3),
                            "tags": item.get("tag_list", [])[:10],
                            "reactions": item.get("positive_reactions_count", 0),
                            "comments": item.get("comments_count", 0),
                            "source": "dev.to",
                        })
    except Exception as exc:
        logger.warning("blog_feed: dev.to fetch failed: %s", exc)
        if _blog_feed_cache["data"]:
            return {"articles": _blog_feed_cache["data"]}
        return {"articles": []}

    seen_ids = set()
    unique = []
    for a in articles:
        if a["id"] not in seen_ids:
            seen_ids.add(a["id"])
            unique.append(a)
    unique.sort(key=lambda x: x.get("reactions", 0), reverse=True)
    unique = unique[:8]

    _blog_feed_cache["data"] = unique
    _blog_feed_cache["ts"] = now
    return {"articles": unique}


@router.get("/api/v1/benchmark/global")
@rate_limit("20/minute")
def get_global_benchmark_stats(request: Request, db=Depends(get_db)):
    """Return global ATS benchmark statistics (public, aggregated only)."""
    from services.benchmark_service import get_global_stats as _bm_global
    return _bm_global(db)


@router.get("/api/v1/benchmark/professions")
@rate_limit("20/minute")
def get_profession_benchmarks(request: Request, db=Depends(get_db)):
    """Return ATS benchmark statistics per profession group."""
    from services.benchmark_service import get_profession_stats as _bm_profs
    return {"professions": _bm_profs(db)}


@router.get("/api/v1/benchmark/{analysis_id:int}")
def get_benchmark(analysis_id: int, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return peer-group benchmark for a user's own analysis."""
    _ensure_not_expired(user)

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    effective_plan = _resolve_effective_plan(db, db_user)
    if not _is_premium_plan(effective_plan):
        raise HTTPException(status_code=403, detail="Premium plan required")

    analysis_record = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id)
        .first()
    )
    if not analysis_record:
        raise HTTPException(status_code=404, detail="Analysis not found")

    benchmark = _build_analysis_benchmark(db, analysis_record)
    return {
        "analysis_id": analysis_id,
        "score": float(analysis_record.similarity_score or 0),
        "effective_plan": effective_plan,
        "benchmark": benchmark,
    }


@router.get("/api/v1/usage")
def get_usage(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return usage counters for UI usage widgets."""
    _ensure_not_expired(user)

    if _main_module().MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        if not mock_user_id:
            mock_user_id = "mock-user"
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        db_user = get_or_create_user(db, str(mock_user_id), mock_email or "dev@example.com")
        effective_plan = _resolve_effective_plan(db, db_user)
        is_admin = _is_admin_user(db_user)
        daily_limit = (10**12) if is_admin else _resolve_daily_limit_for_plan(effective_plan)
        redis_quota = _get_daily_quota_status(str(mock_user_id), limit=daily_limit)
        if redis_quota is None:
            return {
                "plan_type": effective_plan,
                "role": db_user.role or "individual",
                "source": "mock",
                "daily": {
                    "used": int(db_user.daily_usage or 0),
                    "limit": daily_limit,
                    "remaining": (10**12) if is_admin else max(0, int(daily_limit - int(db_user.daily_usage or 0))),
                },
                "monthly": {
                    "used": int(db_user.monthly_usage or 0),
                    "limit": (10**12) if is_admin else int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])),
                    "remaining": (10**12) if is_admin else max(
                        0,
                        int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])) - int(db_user.monthly_usage or 0),
                    ),
                },
            }
        return {
            "plan_type": effective_plan,
            "role": db_user.role or "individual",
            "source": "redis",
            "daily": {
                "used": redis_quota["used"],
                "limit": (10**12) if is_admin else redis_quota["limit"],
                "remaining": (10**12) if is_admin else redis_quota["remaining"],
            },
            "monthly": {
                "used": int(db_user.monthly_usage or 0),
                "limit": (10**12) if is_admin else int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])),
                "remaining": (10**12) if is_admin else max(
                    0,
                    int(USER_PLAN_LIMITS_MONTHLY.get(effective_plan, USER_PLAN_LIMITS_MONTHLY["free"])) - int(db_user.monthly_usage or 0),
                ),
            },
        }

    supabase_id = user.get("user_id")
    email = user.get("email")
    db_user = get_or_create_user(db, supabase_id, email)

    plan_type = _resolve_effective_plan(db, db_user)
    is_admin = _is_admin_user(db_user)
    user_daily_limit = USER_PLAN_LIMITS_DAILY.get(plan_type, USER_PLAN_LIMITS_DAILY["free"])
    user_monthly_limit = USER_PLAN_LIMITS_MONTHLY.get(
        plan_type, USER_PLAN_LIMITS_MONTHLY["free"]
    )

    redis_quota = _get_daily_quota_status(
        db_user.supabase_id or str(db_user.id),
        limit=_resolve_daily_limit_for_plan(plan_type),
    )

    if redis_quota is not None:
        daily_used = redis_quota["used"]
        daily_limit = (10**12) if is_admin else redis_quota["limit"]
        daily_remaining = (10**12) if is_admin else redis_quota["remaining"]
        source = "redis"
    else:
        daily_used = int(db_user.daily_usage or 0)
        daily_limit = (10**12) if is_admin else int(user_daily_limit)
        daily_remaining = (10**12) if is_admin else max(0, daily_limit - daily_used)
        source = "db"

    monthly_used = int(db_user.monthly_usage or 0)
    monthly_limit = (10**12) if is_admin else int(user_monthly_limit)

    return {
        "plan_type": plan_type,
        "role": db_user.role or "individual",
        "source": source,
        "daily": {
            "used": daily_used,
            "limit": daily_limit,
            "remaining": daily_remaining,
        },
        "monthly": {
            "used": monthly_used,
            "limit": monthly_limit,
            "remaining": (10**12) if is_admin else max(0, monthly_limit - monthly_used),
        },
    }


@router.get("/api/v1/me")
def get_me(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
    """Return authenticated user's profile: role, plan, email."""
    _ensure_not_expired(user)
    if _main_module().MOCK_SERVICES_ON:
        mock_user_id = (user or {}).get("user_id") if isinstance(user, dict) else None
        mock_email = (user or {}).get("email") if isinstance(user, dict) else None
        db_user = get_or_create_user(db, str(mock_user_id or "mock-user"), mock_email or "dev@example.com")
    else:
        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
    return {
        "role": db_user.role or "individual",
        "plan_type": _normalize_plan(db_user.plan_type),
        "email": db_user.email,
        "organization_id": db_user.organization_id,
    }


