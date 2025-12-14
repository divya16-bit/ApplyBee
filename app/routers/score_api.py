# routers/score_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services import score_engine, jd_fetcher
from loguru import logger
import os
import time

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
    start_time = time.time()
    try:
        # Log configuration at request start
        semantic_score = os.getenv("MATCHER_SEMANTIC_SCORE", "0")
        semantic_normalizer = os.getenv("MATCHER_SEMANTIC_NORMALIZER", "1")
        legacy_semantic = os.getenv("MATCHER_SEMANTIC", "")
        logger.info(f"🔧 Config: MATCHER_SEMANTIC_SCORE={semantic_score}, MATCHER_SEMANTIC_NORMALIZER={semantic_normalizer}, MATCHER_SEMANTIC={legacy_semantic}")
        
        parsed_resume = req.parsed_resume or {}
        jd_sections = {}
        jd_full_text = ""

        logger.info(f"📥 Received resume score request (resume length: {len(str(parsed_resume))} chars)")

        if req.jd_url:
            try:
                logger.info(f"🔗 Fetching JD from: {req.jd_url}")
                jd_res = jd_fetcher.fetch_job_description(req.jd_url)
                if jd_res and isinstance(jd_res, dict):
                    jd_sections = jd_res.get("jd_sections", {})
                    jd_full_text = jd_res.get("job_description_full", "")
                    logger.info(f"✅ JD fetched successfully ({len(jd_full_text)} chars)")
                else:
                    # Fallback if fetcher returns unexpected format
                    jd_sections = {}
                    jd_full_text = ""
                    logger.warning("⚠️ JD fetcher returned unexpected format")
            except Exception as fetch_err:
                # Log but continue with empty JD - score engine can still work
                logger.warning(f"⚠️ JD fetch failed for {req.jd_url}: {fetch_err}")
                jd_sections = {}
                jd_full_text = ""
        else:
            jd_full_text = req.job_description or ""
            logger.info(f"📄 Using provided JD text ({len(jd_full_text)} chars)")

        logger.info("🚀 Starting score computation...")
        score_start = time.time()
        result = await score_engine.compute_resume_score(parsed_resume, jd_sections, jd_full_text)
        score_duration = time.time() - score_start
        total_duration = time.time() - start_time
        
        logger.info(f"✅ Score computed in {score_duration:.2f}s (total: {total_duration:.2f}s)")
        # return a helpful wrapper
        return {"success": True, "detail": "Score computed", **result}
    except Exception as e:
        total_duration = time.time() - start_time
        logger.error(f"❌ Score computation failed after {total_duration:.2f}s: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
