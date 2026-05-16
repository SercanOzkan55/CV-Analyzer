from __future__ import annotations

import io
import json
import os
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text

from database import engine
from models import Analysis, Candidate, Organization, User
from schemas.recruiter import (
    RecruiterDashboardActionRequest,
    RecruiterJobRequest,
    RecruiterTemplatePreviewRequest,
    RecruiterTemplateRequest,
)
from schemas.rewrite import ScoreBreakdownRequest
from services.recruiter_batch_service import rank_cv_texts


def create_router(
    *,
    verify_supabase_jwt: Callable,
    get_db: Callable,
    get_or_create_user: Callable,
    require_abuse_check: Callable,
    feature_user_key: Callable,
    feature_bucket: Callable,
    next_feature_id: Callable,
    save_feature_store: Callable,
    feature_store_lock,
    resolve_job_description_text: Callable,
    extract_upload_text: Callable,
    run_pipeline: Callable,
    audit_log: Callable,
    env_name: str,
) -> APIRouter:
    router = APIRouter()

    def recruiter_required(user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        """Dependency: verify caller is a recruiter by checking DB record."""
        supabase_id = user.get("user_id")
        if not supabase_id:
            raise HTTPException(status_code=401, detail="Invalid user payload")

        db_user = get_or_create_user(db, supabase_id, user.get("email") or "")
        role = (db_user.role or "individual").lower()
        if role in ("recruiter", "admin"):
            return db_user

        allow_local_workspace = (
            env_name != "prod"
            and os.getenv("DEV_ALLOW_RECRUITER_SELF", "1").lower() in ("1", "true", "yes")
        )
        if not allow_local_workspace:
            raise HTTPException(status_code=403, detail="Recruiter role required")

        domain = f"personal-{db_user.id}.local"
        org = db.query(Organization).filter(Organization.domain == domain).first()
        if not org:
            org = Organization(name=f"{db_user.email} Workspace", domain=domain)
            db.add(org)
            db.commit()
            db.refresh(org)
        db_user.role = "recruiter"
        db_user.organization_id = org.id
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def is_postgres_engine() -> bool:
        try:
            url = getattr(engine, "url", None)
            if not url:
                return False
            return str(url.get_backend_name()).startswith("postgres")
        except Exception:
            return False

    @router.get("/api/v1/recruiter/candidates")
    def recruiter_candidates(
        limit: int = 20, db=Depends(get_db), recruiter=Depends(recruiter_required)
    ):
        """Return recent candidate analyses for the recruiter's organization."""
        org_id = recruiter.organization_id
        if not org_id:
            raise HTTPException(status_code=400, detail="Recruiter has no organization")

        users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()
        records = (
            db.query(Analysis)
            .filter(Analysis.user_id.in_(select(users_subq.c.id)))
            .order_by(Analysis.id.desc())
            .limit(limit)
            .all()
        )

        result = []
        for row in records:
            result.append(
                {
                    "analysis_id": getattr(row, "id", None),
                    "user_id": getattr(row, "user_id", None),
                    "similarity_score": getattr(row, "similarity_score", None),
                    "interpretation": getattr(row, "interpretation", None),
                    "confidence": getattr(row, "confidence", None),
                    "risk_level": getattr(row, "risk_level", None),
                    "domain_id": getattr(row, "domain_id", None),
                    "industry_id": getattr(row, "industry_id", None),
                    "specialization_id": getattr(row, "specialization_id", None),
                    "created_at": getattr(row, "created_at", None),
                }
            )

        return {"candidates": result}

    @router.get("/api/v1/recruiter/top_candidates")
    def recruiter_top_candidates(
        limit: int = 10,
        min_score: float = 0.0,
        start_date: str | None = None,
        end_date: str | None = None,
        db=Depends(get_db),
        recruiter=Depends(recruiter_required),
    ):
        """Return top N candidates for recruiter's org ordered by score."""
        org_id = recruiter.organization_id
        if not org_id:
            raise HTTPException(status_code=400, detail="Recruiter has no organization")

        users_subq = db.query(User.id).filter(User.organization_id == org_id).subquery()
        query = db.query(Analysis).filter(Analysis.user_id.in_(select(users_subq.c.id)))

        try:
            if min_score is not None:
                query = query.filter(Analysis.similarity_score >= float(min_score))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid min_score")

        if start_date:
            try:
                start = datetime.fromisoformat(start_date)
                query = query.filter(Analysis.created_at >= start)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid start_date format; expected ISO-8601"
                )

        if end_date:
            try:
                end = datetime.fromisoformat(end_date)
                query = query.filter(Analysis.created_at <= end)
            except Exception:
                raise HTTPException(
                    status_code=400, detail="Invalid end_date format; expected ISO-8601"
                )

        records = query.order_by(Analysis.similarity_score.desc()).limit(limit).all()
        result = []
        for row in records:
            result.append(
                {
                    "analysis_id": getattr(row, "id", None),
                    "user_id": getattr(row, "user_id", None),
                    "final_score": getattr(row, "similarity_score", None),
                    "interpretation": getattr(row, "interpretation", None),
                    "created_at": getattr(row, "created_at", None),
                }
            )

        return {"top_candidates": result}

    @router.get("/api/v1/recruiter/candidate/{analysis_id}")
    def recruiter_candidate_detail(
        analysis_id: int, db=Depends(get_db), recruiter=Depends(recruiter_required)
    ):
        """Return full analysis detail for a single candidate scoped to org."""
        org_id = recruiter.organization_id
        if not org_id:
            raise HTTPException(status_code=400, detail="Recruiter has no organization")

        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        user = db.query(User).filter(User.id == analysis.user_id).first()
        if not user or user.organization_id != org_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "analysis_id": getattr(analysis, "id", None),
            "user_id": getattr(analysis, "user_id", None),
            "final_score": getattr(analysis, "similarity_score", None),
            "interpretation": getattr(analysis, "interpretation", None),
            "confidence": getattr(analysis, "confidence", None),
            "risk_level": getattr(analysis, "risk_level", None),
            "domain_id": getattr(analysis, "domain_id", None),
            "industry_id": getattr(analysis, "industry_id", None),
            "specialization_id": getattr(analysis, "specialization_id", None),
            "created_at": getattr(analysis, "created_at", None),
            "raw": {"ats": getattr(analysis, "ats", None)},
        }

    @router.get("/api/v1/recruiter/search")
    def recruiter_search(
        q: str,
        limit: int = 20,
        db=Depends(get_db),
        recruiter=Depends(recruiter_required),
    ):
        """Full-text search over candidates for a recruiter's organization."""
        org_id = recruiter.organization_id
        if not org_id:
            raise HTTPException(status_code=400, detail="Recruiter has no organization")

        q = (q or "").strip()
        if not q:
            raise HTTPException(status_code=400, detail="Query q is required")

        results: list[dict] = []
        try:
            if is_postgres_engine():
                sql = text(
                    """
                    SELECT id, organization_id, cv_text,
                           ts_rank_cd(
                               to_tsvector('english', coalesce(cv_text, '')),
                               plainto_tsquery(:q)
                           ) AS rank
                    FROM candidates
                    WHERE organization_id = :org_id
                      AND to_tsvector('english', coalesce(cv_text, '')) @@ plainto_tsquery(:q)
                    ORDER BY rank DESC
                    LIMIT :limit
                    """
                )
                rows = db.execute(sql, {"q": q, "org_id": org_id, "limit": int(limit)}).fetchall()
                for row in rows:
                    results.append(
                        {
                            "id": row[0],
                            "organization_id": row[1],
                            "cv_preview": (row[2][:200] + "...") if row[2] and len(row[2]) > 200 else row[2],
                            "rank": float(row[3]),
                        }
                    )
            else:
                pattern = f"%{q}%"
                rows = (
                    db.query(Candidate)
                    .filter(Candidate.organization_id == org_id)
                    .filter(Candidate.cv_text.ilike(pattern))
                    .limit(limit)
                    .all()
                )
                for row in rows:
                    results.append(
                        {
                            "id": getattr(row, "id", None),
                            "organization_id": getattr(row, "organization_id", None),
                            "cv_preview": (
                                (row.cv_text[:200] + "...")
                                if getattr(row, "cv_text", None) and len(row.cv_text) > 200
                                else getattr(row, "cv_text", None)
                            ),
                        }
                    )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search error: {e}")

        return {"results": results}

    @router.post("/api/v1/recruiter/batch-rank")
    async def recruiter_batch_rank(
        request: Request,
        files: list[UploadFile] = File(...),
        job_description: str = Form(""),
        jd_file: UploadFile | None = File(None),
        _: None = Depends(require_abuse_check),
        recruiter=Depends(recruiter_required),
    ):
        if not files:
            raise HTTPException(status_code=400, detail="At least one CV file is required")
        if len(files) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 CV files allowed")

        jd_text = await resolve_job_description_text(job_description, jd_file)
        if not jd_text:
            raise HTTPException(status_code=400, detail="Job description is empty")

        cv_items = []
        for idx, upload in enumerate(files):
            contents = await upload.read()
            cv_text = extract_upload_text(contents, upload.content_type, upload.filename)
            if not cv_text:
                raise HTTPException(
                    status_code=400,
                    detail=f"CV contains no extractable text: {upload.filename or (idx + 1)}",
                )

            file_name = upload.filename or f"candidate_{idx + 1}.pdf"
            cv_items.append(
                {
                    "candidate_name": file_name.replace(".pdf", ""),
                    "file_name": file_name,
                    "cv_text": cv_text,
                }
            )

        ranking_result = rank_cv_texts(cv_items, jd_text, run_pipeline=run_pipeline)
        total = ranking_result["total_candidates"]
        avg_score = ranking_result["analytics"]["avg_score"]

        try:
            audit_log(
                "recruiter_batch_rank",
                recruiter_id=getattr(recruiter, "id", None),
                organization_id=getattr(recruiter, "organization_id", None),
                cv_count=total,
                avg_score=avg_score,
            )
        except Exception:
            pass

        return {
            "total_candidates": total,
            "job_description_preview": jd_text[:300],
            "ranking": ranking_result["ranking"],
            "analytics": ranking_result["analytics"],
        }

    @router.get("/api/v1/recruiter/jobs")
    def recruiter_list_jobs(recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            jobs = list(feature_bucket(user_key, "recruiter_jobs"))
        return {"jobs": jobs}

    @router.post("/api/v1/recruiter/jobs")
    def recruiter_create_job(body: RecruiterJobRequest, recruiter=Depends(recruiter_required)):
        title = body.title.strip()[:160]
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "recruiter_jobs")
            item = {
                "id": next_feature_id(bucket),
                "title": title,
                "description": (body.description or "")[:12000],
                "company": (body.company or "")[:160],
                "location": (body.location or "")[:160],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            bucket.insert(0, item)
            save_feature_store()
        return item

    @router.get("/api/v1/recruiter/dashboard/actions/{job_id}")
    def recruiter_dashboard_actions(job_id: str, recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            actions = [
                row for row in feature_bucket(user_key, "recruiter_actions")
                if str(row.get("job_id")) == str(job_id)
            ]
        return {"actions": actions}

    @router.get("/api/v1/recruiter/pipeline/{job_id}")
    def recruiter_pipeline(job_id: str, recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            actions = [
                row for row in feature_bucket(user_key, "recruiter_actions")
                if str(row.get("job_id")) == str(job_id)
            ]
        stages = {"review": [], "accepted": [], "rejected": [], "interview": [], "offer": []}
        for action in actions:
            stage = str(action.get("stage") or action.get("action") or "review")
            stages.setdefault(stage, []).append(action)
        return {"job_id": job_id, "stages": stages, "actions": actions}

    @router.put("/api/v1/recruiter/dashboard/actions/{action_id}/stage")
    def recruiter_update_action_stage(
        action_id: int,
        body: dict,
        recruiter=Depends(recruiter_required),
    ):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "recruiter_actions")
            item = next((row for row in bucket if int(row.get("id", 0)) == int(action_id)), None)
            if not item:
                raise HTTPException(status_code=404, detail="Action not found")
            stage = str(body.get("stage") or body.get("action") or "review")
            item["stage"] = stage
            item["action"] = stage
            item["updated_at"] = datetime.utcnow().isoformat() + "Z"
            save_feature_store()
        return {"action": item}

    @router.post("/api/v1/recruiter/dashboard/action")
    def recruiter_dashboard_action(
        body: RecruiterDashboardActionRequest,
        recruiter=Depends(recruiter_required),
    ):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "recruiter_actions")
            item = {
                "id": next_feature_id(bucket),
                "job_id": body.job_id,
                "candidate_name": body.candidate_name or "Candidate",
                "candidate_email": body.candidate_email or "",
                "cv_text": (body.cv_text or "")[:200000],
                "final_score": body.final_score,
                "ats_score": body.ats_score,
                "action": body.action or "review",
                "stage": body.stage or body.action or "review",
                "feedback": body.feedback or "",
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            bucket.insert(0, item)
            save_feature_store()
        return {"action": item}

    @router.post("/api/v1/recruiter/dashboard/preview")
    def recruiter_dashboard_preview(body: ScoreBreakdownRequest, recruiter=Depends(recruiter_required)):
        result = run_pipeline(body.cv_text or "", body.job_description or "", body.lang)
        return {
            "result": result,
            "strengths": result.get("detected_skills") or [],
            "weaknesses": result.get("missing_skills") or [],
            "score_breakdown": result.get("score_breakdown") or {},
        }

    @router.post("/api/v1/recruiter/dashboard/rank")
    def recruiter_dashboard_rank(body: dict, recruiter=Depends(recruiter_required)):
        cv_text = str(body.get("cv_text") or body.get("candidate_text") or "")
        jd_text = str(body.get("job_description") or body.get("jd_text") or "")
        if not cv_text or not jd_text:
            raise HTTPException(status_code=400, detail="cv_text and job_description are required")
        result = run_pipeline(cv_text, jd_text)
        return {"ranking": [{"rank": 1, "candidate_name": body.get("candidate_name") or "Candidate", **result}]}

    @router.post("/api/v1/recruiter/dashboard/batch-upload")
    async def recruiter_dashboard_batch_upload(
        job_id: str = Form(""),
        files: list[UploadFile] = File(...),
        recruiter=Depends(recruiter_required),
    ):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            jobs = feature_bucket(user_key, "recruiter_jobs")
            job = next((row for row in jobs if str(row.get("id")) == str(job_id)), None)
        jd_text = str((job or {}).get("description") or "General role")
        cv_items = []
        for idx, upload in enumerate(files[:50]):
            contents = await upload.read()
            cv_text = extract_upload_text(contents, upload.content_type, upload.filename)
            file_name = upload.filename or ""
            cv_items.append(
                {
                    "candidate_name": file_name or f"candidate_{idx + 1}",
                    "file_name": file_name,
                    "cv_text": cv_text,
                }
            )
        ranking_result = rank_cv_texts(cv_items, jd_text, run_pipeline=run_pipeline, include_cv_text=True)
        return {
            "total_candidates": ranking_result["total_candidates"],
            "ranking": ranking_result["ranking"],
            "analytics": ranking_result["analytics"],
        }

    @router.get("/api/v1/recruiter/report/{job_id}")
    def recruiter_report(job_id: str, recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            actions = [
                row for row in feature_bucket(user_key, "recruiter_actions")
                if str(row.get("job_id")) == str(job_id)
            ]
        csv = io.StringIO()
        csv.write("candidate_name,candidate_email,final_score,action,feedback\n")
        for row in actions:
            csv.write(
                ",".join(
                    [
                        json.dumps(row.get("candidate_name") or "")[1:-1],
                        json.dumps(row.get("candidate_email") or "")[1:-1],
                        str(row.get("final_score") or ""),
                        json.dumps(row.get("action") or "")[1:-1],
                        json.dumps(row.get("feedback") or "")[1:-1],
                    ]
                )
                + "\n"
            )
        csv.seek(0)
        return StreamingResponse(iter([csv.getvalue()]), media_type="text/csv")

    @router.get("/api/v1/recruiter/templates")
    def recruiter_list_templates(recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            templates = list(feature_bucket(user_key, "recruiter_templates"))
        return {"templates": templates}

    @router.post("/api/v1/recruiter/templates")
    def recruiter_create_template(body: RecruiterTemplateRequest, recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "recruiter_templates")
            item = {
                "id": next_feature_id(bucket),
                "name": body.name.strip()[:160],
                "template_type": body.template_type or "accept",
                "subject": (body.subject or "")[:240],
                "body": body.body[:6000],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            bucket.insert(0, item)
            save_feature_store()
        return item

    @router.delete("/api/v1/recruiter/templates/{template_id}")
    def recruiter_delete_template(template_id: int, recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            bucket = feature_bucket(user_key, "recruiter_templates")
            before = len(bucket)
            bucket[:] = [row for row in bucket if int(row.get("id", 0)) != int(template_id)]
            save_feature_store()
        return {"deleted": before != len(bucket)}

    @router.post("/api/v1/recruiter/templates/preview")
    def recruiter_template_preview(body: RecruiterTemplatePreviewRequest, recruiter=Depends(recruiter_required)):
        user_key = feature_user_key(recruiter)
        with feature_store_lock:
            templates = feature_bucket(user_key, "recruiter_templates")
            tpl = next((row for row in templates if str(row.get("id")) == str(body.template_id)), None)
        text = (tpl or {}).get("body") or "Hello {candidate_name}, thank you for your interest in {position}."
        values = {
            "candidate_name": body.candidate_name or "Candidate",
            "candidate_email": body.candidate_email or "",
            "position": body.position or "the role",
            "company": body.company or "our company",
            "score": str(body.score or ""),
            "top_skills": ", ".join(body.top_skills or []),
        }
        for key, value in values.items():
            text = text.replace("{" + key + "}", value)
        return {"preview": text, "subject": (tpl or {}).get("subject") or ""}

    @router.post("/api/v1/recruiter/send-email")
    def recruiter_send_email(body: dict, recruiter=Depends(recruiter_required)):
        return {"ok": True, "status": "queued", "to": body.get("candidate_email")}

    return router
