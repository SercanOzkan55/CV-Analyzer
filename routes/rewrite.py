from __future__ import annotations

import difflib
import json
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from schemas.rewrite import (
    BulletRewriteRequest,
    CoverLetterRewriteRequest,
    CVAutoFixExportRequest,
    CVAutoFixParseRequest,
    CVRewriteRequest,
    DiffRequest,
    InterviewEvaluateRequest,
    InterviewQuestionsRequest,
    KeywordOptimizationRequest,
    ScoreBreakdownRequest,
    SummarySuggestionRequest,
)
from services import rewrite_service
from services.cv_autofix_service import auto_fix_cv_text, structured_text_to_builder_payload
from services.cv_builder_service import build_cv
from services.keyword_service import compute_keyword_gap
from services.language_service import DEFAULT_LANG


def create_router(
    *,
    verify_supabase_jwt: Callable,
    get_db: Callable,
    ensure_not_expired: Callable,
    get_or_create_user: Callable,
    resolve_effective_plan: Callable,
    ensure_ai_rewrite_allowed: Callable,
    current_db_user: Callable,
    audit_log: Callable,
    run_pipeline: Callable,
    rate_limit: Callable,
    analyze_pdf_rate_limit_per_min: int,
    extract_upload_text: Callable,
    metric_request: Callable,
    mock_services_on: bool,
    logger,
) -> APIRouter:
    router = APIRouter()

    def rewrite_cv_payload(body: CVRewriteRequest, user: dict, db):
        ensure_not_expired(user)

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        plan = ensure_ai_rewrite_allowed(db, db_user)

        try:
            text = rewrite_service.rewrite_cv(
                cv_text=body.cv_text,
                job_description=body.job_description or "",
                lang=body.lang,
                tone=body.tone,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        try:
            audit_log(
                "ai_rewrite_cv",
                user_id=db_user.id,
                organization_id=db_user.organization_id,
                plan=plan,
            )
        except Exception:
            pass

        return {"result": text, "plan": plan}

    @router.post("/api/v1/cv/auto-fix")
    @rate_limit(f"{analyze_pdf_rate_limit_per_min}/minute")
    async def auto_fix_cv_pdf(
        file: UploadFile = File(...),
        job_description: str = Form(""),
        lang: str = Form(DEFAULT_LANG),
        use_ai: bool = Form(True),
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        """Extract a CV upload and rewrite it into a cleaner ATS-friendly format."""

        ensure_not_expired(user)
        metric_request("cv-auto-fix")

        db_user = None
        if not mock_services_on:
            supabase_id = user.get("user_id")
            email = user.get("email")
            db_user = get_or_create_user(db, supabase_id, email)

        contents = await file.read()
        cv_text = extract_upload_text(contents, file.content_type, file.filename)

        try:
            result = await run_in_threadpool(
                auto_fix_cv_text,
                cv_text=cv_text,
                job_description=job_description,
                lang=lang,
                use_ai=use_ai,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.exception("auto_fix_cv_text unexpected error")
            raise HTTPException(status_code=500, detail=f"Auto-fix error: {e}")

        try:
            audit_payload = {
                "source": "upload",
                "used_ai": bool(result.get("used_ai")),
                "score_delta": float(result.get("score_delta", 0.0)),
            }
            if db_user is not None:
                audit_payload["user_id"] = db_user.id
                audit_payload["organization_id"] = db_user.organization_id
            audit_log("cv_auto_fix", **audit_payload)
        except Exception:
            pass

        return result

    @router.post("/api/v1/rewrite/cv")
    def rewrite_cv_endpoint(
        body: CVRewriteRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        return rewrite_cv_payload(body, user=user, db=db)

    @router.post("/api/v1/cv/auto-fix/export")
    def export_auto_fixed_cv(
        body: CVAutoFixExportRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        ensure_not_expired(user)

        if body.output_format not in ("docx", "pdf"):
            raise HTTPException(status_code=400, detail="output_format must be 'docx' or 'pdf'")

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        effective_plan = resolve_effective_plan(db, db_user)

        cv_data = structured_text_to_builder_payload(
            body.optimized_cv_text,
            job_description=body.job_description or "",
            lang=body.lang,
        )
        cv_data["template"] = body.template
        cv_data["output_format"] = body.output_format

        result = build_cv(
            cv_data=cv_data,
            job_description=body.job_description or "",
            template=body.template,
            output_format=body.output_format,
            lang=body.lang,
            plan=effective_plan,
        )

        try:
            audit_log(
                "cv_auto_fix_export",
                user_id=db_user.id,
                organization_id=db_user.organization_id,
                output_format=body.output_format,
                template=body.template,
            )
        except Exception:
            pass

        return StreamingResponse(
            result["buffer"],
            media_type=result["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
        )

    @router.post("/api/v1/cv/auto-fix/parse")
    def parse_auto_fixed_cv(
        body: CVAutoFixParseRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        ensure_not_expired(user)

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)

        try:
            builder_payload = structured_text_to_builder_payload(
                body.optimized_cv_text,
                job_description=body.job_description or "",
                lang=body.lang,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            audit_log(
                "cv_auto_fix_parse",
                user_id=db_user.id,
                organization_id=db_user.organization_id,
                lang=body.lang,
            )
        except Exception:
            pass

        return {"builder_payload": builder_payload}

    @router.post("/api/v1/rewrite/bullets")
    def rewrite_bullets_endpoint(
        body: BulletRewriteRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        ensure_not_expired(user)

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        plan = ensure_ai_rewrite_allowed(db, db_user)

        try:
            bullets = rewrite_service.rewrite_bullets(
                bullets=body.bullets,
                job_description=body.job_description or "",
                lang=body.lang,
                tone=body.tone,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        try:
            audit_log(
                "ai_rewrite_bullets",
                user_id=db_user.id,
                organization_id=db_user.organization_id,
                plan=plan,
                bullet_count=len(body.bullets or []),
            )
        except Exception:
            pass

        return {"results": bullets, "plan": plan}

    @router.post("/api/v1/rewrite/cover-letter")
    def rewrite_cover_letter_endpoint(
        body: CoverLetterRewriteRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        ensure_not_expired(user)

        supabase_id = user.get("user_id")
        email = user.get("email")
        db_user = get_or_create_user(db, supabase_id, email)
        plan = ensure_ai_rewrite_allowed(db, db_user)

        try:
            letter = rewrite_service.rewrite_cover_letter(
                cv_text=body.cv_text,
                job_description=body.job_description,
                lang=body.lang,
                tone=body.tone,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

        try:
            audit_log(
                "ai_rewrite_cover_letter",
                user_id=db_user.id,
                organization_id=db_user.organization_id,
                plan=plan,
            )
        except Exception:
            pass

        return {"result": letter, "plan": plan}

    @router.post("/api/v1/cv/rewrite")
    def rewrite_cv_alias(
        body: CVRewriteRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        return rewrite_cv_payload(body, user=user, db=db)

    @router.post("/api/v1/cv/optimize-keywords")
    def optimize_keywords_endpoint(
        body: KeywordOptimizationRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        ensure_ai_rewrite_allowed(db, db_user)
        gap = compute_keyword_gap(body.cv_text or "", body.job_description or "")
        prompt = (
            "Improve this CV excerpt by naturally incorporating only job-description "
            "keywords that are genuinely supported by the candidate background. "
            f"Language: {body.lang}.\n\n"
            f"Missing or weak keywords: {json.dumps(gap, ensure_ascii=False)[:2000]}\n\n"
            f"Job description:\n{(body.job_description or '')[:3000]}\n\n"
            f"CV:\n{(body.cv_text or '')[:5000]}"
        )
        try:
            optimized = rewrite_service.generate_text(prompt, max_tokens=900)
        except RuntimeError:
            optimized = body.cv_text
        return {"optimized_text": optimized, "keyword_gap": gap}

    @router.post("/api/v1/score/breakdown")
    def score_breakdown_endpoint(
        body: ScoreBreakdownRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        current_db_user(user, db)
        result = run_pipeline(body.cv_text, body.job_description, body.lang)
        return {
            "final_score": result.get("final_score"),
            "score_breakdown": result.get("score_breakdown") or {},
            "missing_skills": result.get("missing_skills") or [],
            "keyword_gap": result.get("keyword_gap") or {},
            "recommendations": result.get("recommendations") or [],
        }

    @router.post("/api/v1/cv/diff")
    def cv_diff_endpoint(body: DiffRequest, user=Depends(verify_supabase_jwt), db=Depends(get_db)):
        current_db_user(user, db)
        original_lines = (body.original_text or "").splitlines()
        optimized_lines = (body.optimized_text or "").splitlines()
        diff = list(
            difflib.unified_diff(
                original_lines,
                optimized_lines,
                fromfile="original",
                tofile="optimized",
                lineterm="",
            )
        )
        return {
            "diff": diff,
            "added": [line[1:] for line in diff if line.startswith("+") and not line.startswith("+++")],
            "removed": [line[1:] for line in diff if line.startswith("-") and not line.startswith("---")],
        }

    @router.post("/api/v1/linkedin/optimize")
    def optimize_linkedin_endpoint(
        body: KeywordOptimizationRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        ensure_ai_rewrite_allowed(db, db_user)
        prompt = (
            "Create a polished, factual LinkedIn profile summary and headline from this CV. "
            "Do not invent facts. Return JSON with headline, about, featured_skills.\n\n"
            f"Language: {body.lang}\nJob description/context:\n{(body.job_description or '')[:2000]}\n\n"
            f"CV:\n{(body.cv_text or '')[:5000]}"
        )
        try:
            text = rewrite_service.generate_text(prompt, max_tokens=700)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        return {"result": text}

    @router.post("/api/v1/job/match-score")
    def job_match_score_endpoint(
        body: ScoreBreakdownRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        current_db_user(user, db)
        result = run_pipeline(body.cv_text, body.job_description, body.lang)
        return {
            "score": result.get("final_score"),
            "match_score": result.get("final_score"),
            "missing_skills": result.get("missing_skills") or [],
            "recommendations": result.get("recommendations") or [],
        }

    @router.post("/api/v1/interview/questions")
    def interview_questions_endpoint(
        body: InterviewQuestionsRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        ensure_ai_rewrite_allowed(db, db_user)
        count = max(1, min(10, int(body.count or 5)))
        prompt = (
            f"Generate {count} interview questions for this candidate. "
            "Return JSON array only. Each item must include question, category, difficulty, and tip. "
            f"Mode: {body.mode}. Language: {body.lang}.\n\n"
            f"Job description:\n{(body.job_description or '')[:3000]}\n\nCV:\n{body.cv_text[:5000]}"
        )
        try:
            text = rewrite_service.generate_text(prompt, max_tokens=1000)
            parsed = json.loads(text)
            questions = parsed if isinstance(parsed, list) else parsed.get("questions", [])
        except Exception:
            questions = [
                {
                    "question": "Tell me about the experience most relevant to this role.",
                    "category": "behavioral",
                    "difficulty": body.mode or "senior",
                    "tip": "Use a concrete example and quantify the result.",
                }
                for _ in range(count)
            ]
        return {"questions": questions[:count]}

    @router.post("/api/v1/interview/evaluate")
    def interview_evaluate_endpoint(
        body: InterviewEvaluateRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        ensure_ai_rewrite_allowed(db, db_user)
        prompt = (
            "Evaluate this interview answer. Return JSON with score, strengths, improvements, and sample_answer. "
            f"Language: {body.lang}.\n\nQuestion: {body.question}\nAnswer: {body.answer}\n"
            f"Job description:\n{(body.job_description or '')[:2000]}"
        )
        try:
            text = rewrite_service.generate_text(prompt, max_tokens=700)
            evaluation = json.loads(text)
        except Exception:
            words = len((body.answer or "").split())
            evaluation = {
                "score": min(100, max(35, words * 4)),
                "strengths": ["Answer submitted with relevant context."],
                "improvements": ["Add a specific situation, action, and measurable result."],
                "sample_answer": "Use the STAR structure: situation, task, action, result.",
            }
        return {"evaluation": evaluation}

    @router.post("/api/v1/cv-builder/suggest-summary")
    def suggest_summary_endpoint(
        body: SummarySuggestionRequest,
        user=Depends(verify_supabase_jwt),
        db=Depends(get_db),
    ):
        db_user = current_db_user(user, db)
        ensure_ai_rewrite_allowed(db, db_user)
        prompt = (
            "Rewrite this professional summary into three concise ATS-friendly alternatives. "
            "Return JSON array of strings only. Preserve facts and language.\n\n"
            f"Language: {body.lang}\nJob description:\n{(body.job_description or '')[:2500]}\n\nSummary:\n{body.summary[:2000]}"
        )
        try:
            text = rewrite_service.generate_text(prompt, max_tokens=500)
            parsed = json.loads(text)
            suggestions = parsed if isinstance(parsed, list) else parsed.get("suggestions", [])
        except Exception:
            suggestions = [
                body.summary.strip(),
                f"{body.summary.strip()} Focused on measurable impact, collaboration, and role-aligned outcomes.",
            ]
        return {"suggestions": suggestions[:3]}

    return router
