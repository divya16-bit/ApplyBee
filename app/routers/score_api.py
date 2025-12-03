# routers/score_api.py
from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
from typing import Optional
from app.models.score_models import ScoreRequest, ScoreResponse
from app.services import jd_fetcher, matcher
from app.services.score_engine import compute_resume_score

router = APIRouter()


@router.post("/resume-score", response_model=ScoreResponse)
async def resume_score_endpoint(data: ScoreRequest):
    """
    Compute resume-JD alignment score.

    Accepts:
    - parsed_resume (dict) with parsed_resume.get("raw_text") preferred
    - job_description (optional string)
    - job_url (optional) - if provided, JD will be fetched
    """

    try:
        parsed_resume = data.parsed_resume or {}
        jd_text = data.job_description or ""
        jd_sections = {}
        jd_full_text = ""

        # If job_url provided, fetch JD (threadpool)
        if data.job_url:
            jd_res = await run_in_threadpool(jd_fetcher.fetch_job_description, data.job_url)
            jd_full_text = jd_res.get("job_description_full") or ""
            sections = jd_res.get("jd_sections") or {}
            # reformat sections to the shape matcher expects
            jd_sections = {
                "responsibilities": sections.get("responsibilities") or [],
                "skills": sections.get("skills") or [],
                "bonus_skills": sections.get("bonus_skills") or []
            }
        else:
            # If only job_description string is provided, put it into skills/responsibilities fallback
            jd_full_text = jd_text or parsed_resume.get("raw_text", "")
            jd_sections = {
                "responsibilities": [jd_text] if jd_text else [],
                "skills": [],
                "bonus_skills": []
            }

        # Use compute_resume_score which calls matcher.calculate_match_score_text
        score_result = await compute_resume_score(
            parsed_resume=parsed_resume,
            jd_sections=jd_sections,
            jd_full_text=jd_full_text
        )

        return ScoreResponse(success=True, detail="Score computed", **score_result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Score computation failed: {str(e)}")
