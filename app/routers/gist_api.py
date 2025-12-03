# routers/gist_api.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from app.models.gist_models import GistRequest, GistResponse
from app.services import gist_generator
from app.services import jd_fetcher

router = APIRouter()

@router.post("/generate-gists", response_model=GistResponse)
async def generate_gists_endpoint(data: GistRequest):
    """
    Accepts parsed_resume (dict) + optional job_description or job_url + fields list.
    Returns mapping: label -> answer (uses your existing generate_gist).
    """
    try:
        parsed_resume = data.parsed_resume or {}
        fields = data.fields or []
        jd_data = {}

        # If job_url provided, fetch JD via jd_fetcher
        if data.job_url:
            # jd_fetcher.fetch_job_description can be blocking; run in threadpool
            try:
                jd_res = await run_in_threadpool(jd_fetcher.fetch_job_description, data.job_url)
                jd_data = jd_res or {}
            except Exception as e:
                # If JD fetch failed, continue with empty jd_data
                jd_data = {"job_description": data.job_description or ""}
        else:
            # prefer job_description string if provided
            jd_data = {"job_description": data.job_description or ""}

        # Call your existing generate_gist (async)
        answers = await gist_generator.generate_gist(parsed_resume, jd_data, fields)
        return GistResponse(success=True, message="Gists generated successfully.", answers=answers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gist generation failed: {str(e)}")
