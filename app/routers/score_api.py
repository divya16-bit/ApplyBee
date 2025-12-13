# routers/score_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services import score_engine, jd_fetcher

router = APIRouter()

class ScoreRequest(BaseModel):
    parsed_resume: Dict[str, Any]
    jd_url: Optional[str] = None
    job_description: Optional[str] = ""

class ScoreResponse(BaseModel):
    success: bool
    detail: Optional[str] = None
    score: Optional[float] = None

@router.post("/resume-score")
async def resume_score_endpoint(req: ScoreRequest):
    try:
        parsed_resume = req.parsed_resume or {}
        jd_sections = {}
        jd_full_text = ""

        if req.jd_url:
            jd_res = jd_fetcher.fetch_job_description(req.jd_url)
            jd_sections = jd_res.get("jd_sections", {}) if jd_res else {}
            jd_full_text = jd_res.get("job_description_full", "") if jd_res else ""
        else:
            jd_full_text = req.job_description or ""

        result = await score_engine.compute_resume_score(parsed_resume, jd_sections, jd_full_text)
        # return a helpful wrapper
        return {"success": True, "detail": "Score computed", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
