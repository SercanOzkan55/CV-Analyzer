from __future__ import annotations

import hashlib
import io
import json
import time
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from models import Analysis
from schemas.workspace import JDTemplateRequest


def create_router(
    *,
    verify_supabase_jwt: Callable,
    get_db: Callable,
    current_db_user: Callable,
    resolve_effective_plan: Callable,
    analysis_payload: Callable,
    feature_user_key: Callable,
    feature_bucket: Callable,
    next_feature_id: Callable,
    save_feature_store: Callable,
    feature_store_lock,
    feature_store: dict,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/favorites")
    def get_favorites(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            favorites = list(feature_bucket(user_key, "favorites"))

        analysis_ids = [
            int(item.get("analysis_id"))
            for item in favorites
            if str(item.get("analysis_id", "")).isdigit()
        ]
        analyses = {}
        if analysis_ids:
            for row in db.query(Analysis).filter(Analysis.user_id == db_user.id, Analysis.id.in_(analysis_ids)).all():
                analyses[int(row.id)] = analysis_payload(row)

        return {
            "favorites": [
                {
                    **item,
                    "analysis": analyses.get(int(item.get("analysis_id", 0)), {}),
                }
                for item in favorites
            ]
        }

    @router.get("/api/v1/favorites/ids")
    def get_favorite_ids(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            ids = [item.get("analysis_id") for item in feature_bucket(user_key, "favorites")]
        return {"ids": ids}

    @router.post("/api/v1/favorites/toggle")
    def toggle_favorite(body: dict, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        try:
            analysis_id = int(body.get("analysis_id"))
        except Exception:
            raise HTTPException(status_code=400, detail="analysis_id is required")

        analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "favorites")
            existing = next((item for item in bucket if int(item.get("analysis_id", 0)) == analysis_id), None)
            if existing:
                bucket.remove(existing)
                favorited = False
                item = existing
            else:
                item = {
                    "id": next_feature_id(bucket),
                    "analysis_id": analysis_id,
                    "note": str(body.get("note") or "")[:1000],
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
                bucket.insert(0, item)
                favorited = True
            save_feature_store()
        return {"favorited": favorited, "favorite": item}

    @router.get("/api/v1/jd-templates")
    def list_jd_templates(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            templates = list(feature_bucket(user_key, "jd_templates"))
        return {"templates": templates}

    @router.post("/api/v1/jd-templates")
    def create_jd_template(
        body: JDTemplateRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        title = body.title.strip()[:120]
        description = body.description.strip()
        if not title or not description:
            raise HTTPException(status_code=400, detail="title and description are required")

        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "jd_templates")
            plan = resolve_effective_plan(db, db_user)
            if plan == "free" and len(bucket) >= 3:
                raise HTTPException(status_code=403, detail="Free plan supports up to 3 JD templates")
            item = {
                "id": next_feature_id(bucket),
                "title": title,
                "description": description[:10000],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            bucket.insert(0, item)
            save_feature_store()
        return item

    @router.delete("/api/v1/jd-templates/{template_id}")
    def delete_jd_template(template_id: int, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "jd_templates")
            before = len(bucket)
            bucket[:] = [item for item in bucket if int(item.get("id", 0)) != int(template_id)]
            save_feature_store()
        return {"deleted": before != len(bucket), "id": template_id}

    @router.get("/api/v1/history/export")
    def export_history_csv(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        rows = (
            db.query(Analysis)
            .filter(Analysis.user_id == db_user.id)
            .order_by(Analysis.created_at.desc())
            .all()
        )
        output = io.StringIO()
        output.write("id,created_at,job_title,similarity_score,risk_level,confidence\n")
        for row in rows:
            payload = analysis_payload(row)
            output.write(
                ",".join(
                    [
                        str(payload["id"] or ""),
                        str(payload["created_at"] or ""),
                        json.dumps(payload["job_title"] or "")[1:-1],
                        str(payload["similarity_score"]),
                        json.dumps(payload["risk_level"] or "")[1:-1],
                        str(payload["confidence"]),
                    ]
                )
                + "\n"
            )
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="cv_analysis_history.csv"'},
        )

    @router.post("/api/v1/notes")
    def save_note(body: dict, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        analysis_id = str(body.get("analysis_id") or "").strip()
        content = str(body.get("content") or "").strip()[:5000]
        if not analysis_id:
            raise HTTPException(status_code=400, detail="analysis_id is required")
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "notes")
            existing = next((item for item in bucket if str(item.get("analysis_id")) == analysis_id), None)
            if existing:
                existing["content"] = content
                existing["updated_at"] = datetime.utcnow().isoformat() + "Z"
                item = existing
            else:
                item = {
                    "id": next_feature_id(bucket),
                    "analysis_id": analysis_id,
                    "content": content,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                }
                bucket.insert(0, item)
            save_feature_store()
        return {"note": item}

    @router.get("/api/v1/notes/{analysis_id}")
    def get_note(analysis_id: str, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            item = next(
                (row for row in feature_bucket(user_key, "notes") if str(row.get("analysis_id")) == str(analysis_id)),
                None,
            )
        return {"note": item or {"analysis_id": str(analysis_id), "content": ""}}

    @router.delete("/api/v1/notes/{analysis_id}")
    def delete_note(analysis_id: str, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "notes")
            before = len(bucket)
            bucket[:] = [row for row in bucket if str(row.get("analysis_id")) != str(analysis_id)]
            save_feature_store()
        return {"deleted": before != len(bucket)}

    @router.post("/api/v1/share")
    def create_share_link(body: dict, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        try:
            analysis_id = int(body.get("analysis_id"))
        except Exception:
            raise HTTPException(status_code=400, detail="analysis_id is required")
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id, Analysis.user_id == db_user.id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        token = hashlib.sha256(f"{db_user.id}:{analysis_id}:{time.time()}".encode()).hexdigest()[:32]
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "shares")
            item = {
                "id": next_feature_id(bucket),
                "share_token": token,
                "analysis_id": analysis_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            bucket.insert(0, item)
            save_feature_store()
        return {"share_token": token, "url": f"/shared/{token}"}

    @router.delete("/api/v1/share/{share_token}")
    def revoke_share_link(share_token: str, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "shares")
            before = len(bucket)
            bucket[:] = [row for row in bucket if row.get("share_token") != share_token]
            save_feature_store()
        return {"revoked": before != len(bucket)}

    @router.get("/api/v1/shared/{share_token}")
    def get_shared_analysis(share_token: str, db=Depends(get_db)):
        with feature_store_lock:
            shares = []
            for user_store in feature_store.get("users", {}).values():
                shares.extend(user_store.get("shares", []) if isinstance(user_store, dict) else [])
            match = next((row for row in shares if row.get("share_token") == share_token), None)
        if not match:
            raise HTTPException(status_code=404, detail="Shared analysis not found")
        analysis = db.query(Analysis).filter(Analysis.id == int(match.get("analysis_id", 0))).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Shared analysis not found")
        return {"analysis": analysis_payload(analysis)}

    @router.get("/api/v1/blog/feed")
    def blog_feed():
        return {
            "posts": [
                {"title": "ATS-friendly CV structure", "slug": "ats-friendly-cv-structure", "category": "CV", "views": 1240},
                {"title": "How to tailor a cover letter", "slug": "tailor-cover-letter", "category": "Cover Letter", "views": 980},
                {"title": "Recruiter screening checklist", "slug": "recruiter-screening-checklist", "category": "Recruiting", "views": 760},
            ]
        }

    @router.get("/api/v1/me/data-summary")
    def get_my_data_summary(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        analysis_count = db.query(Analysis).filter(Analysis.user_id == db_user.id).count()
        with feature_store_lock:
            user_store = feature_store.get("users", {}).get(user_key, {})
            reminders = len(user_store.get("reminders", [])) if isinstance(user_store, dict) else 0
            candidate_actions = len(user_store.get("recruiter_actions", [])) if isinstance(user_store, dict) else 0
        return {
            "cv_versions": 0,
            "stored_cv_files": 0,
            "analyses": int(analysis_count or 0),
            "reminders": reminders,
            "candidate_actions": candidate_actions,
            "usage_days": int(analysis_count or 0),
        }

    @router.get("/api/v1/me/data-export")
    def export_my_data(
        include_raw: bool = Query(default=False),
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        analyses = [
            analysis_payload(row, include_raw=include_raw)
            for row in db.query(Analysis).filter(Analysis.user_id == db_user.id).order_by(Analysis.created_at.desc()).all()
        ]
        with feature_store_lock:
            user_store = feature_store.get("users", {}).get(user_key, {})
        return {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "include_raw": include_raw,
            "user": {"email": db_user.email, "plan_type": db_user.plan_type, "role": db_user.role},
            "analyses": analyses,
            "workspace": user_store if include_raw else {k: len(v) if isinstance(v, list) else 0 for k, v in (user_store or {}).items()},
        }

    @router.delete("/api/v1/me/data")
    def delete_my_data(
        scope: str = Query(default="stored_cvs"),
        confirm: str = Query(default=""),
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        if confirm != "DELETE":
            raise HTTPException(status_code=400, detail="confirm=DELETE is required")
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        deleted = 0
        if scope in ("analyses", "all"):
            rows = db.query(Analysis).filter(Analysis.user_id == db_user.id).all()
            deleted += len(rows)
            for row in rows:
                db.delete(row)
            db.commit()
        if scope in ("workspace", "stored_cvs", "all"):
            with feature_store_lock:
                users = feature_store.setdefault("users", {})
                if user_key in users:
                    deleted += sum(len(v) for v in users[user_key].values() if isinstance(v, list))
                    if scope == "all":
                        users[user_key] = {}
                    else:
                        for key in ("favorites", "jd_templates", "notes", "reminders", "recruiter_jobs", "recruiter_actions", "recruiter_templates"):
                            users[user_key][key] = []
                    save_feature_store()
        return {"deleted": deleted, "scope": scope}

    @router.get("/api/v1/reminders")
    def list_reminders(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            reminders = list(feature_bucket(user_key, "reminders"))
        return {"reminders": reminders}

    @router.post("/api/v1/reminders")
    def create_reminder(body: dict, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "reminders")
            item = {
                "id": next_feature_id(bucket),
                "job_id": body.get("job_id"),
                "event_date": body.get("event_date") or body.get("reminder_date"),
                "reminder_type": body.get("reminder_type") or "follow_up",
                "target_email": body.get("target_email") or db_user.email,
                "is_active": bool(body.get("is_active", True)),
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            bucket.insert(0, item)
            save_feature_store()
        return item

    @router.put("/api/v1/reminders/{reminder_id}")
    def update_reminder(reminder_id: int, body: dict, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "reminders")
            item = next((row for row in bucket if int(row.get("id", 0)) == int(reminder_id)), None)
            if not item:
                raise HTTPException(status_code=404, detail="Reminder not found")
            for key in ("job_id", "event_date", "reminder_date", "reminder_type", "target_email", "is_active"):
                if key in body:
                    target_key = "event_date" if key == "reminder_date" else key
                    item[target_key] = body[key]
            item["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_feature_store()
        return item

    @router.delete("/api/v1/reminders/{reminder_id}")
    def delete_reminder(reminder_id: int, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        db_user = current_db_user(user, db)
        user_key = feature_user_key(db_user)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "reminders")
            before = len(bucket)
            bucket[:] = [row for row in bucket if int(row.get("id", 0)) != int(reminder_id)]
            save_feature_store()
        return {"deleted": before != len(bucket), "id": reminder_id}

    @router.post("/api/v1/reminders/{reminder_id}/send-test")
    def send_reminder_test(reminder_id: int, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        current_db_user(user, db)
        return {"ok": True, "id": reminder_id, "message": "Test reminder accepted"}

    return router
