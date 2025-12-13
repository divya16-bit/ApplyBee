# routers/gist_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from services import gist_generator
from starlette.concurrency import run_in_threadpool

router = APIRouter()

class GetGistRequest(BaseModel):
    resume: str
    jd: Optional[str] = ""
    labels: List[str]

class GetGistResponse(BaseModel):
    success: bool
    detail: str
    answers: Dict[str, str]

@router.post("/get-gist", response_model=GetGistResponse)
async def get_gist_endpoint(payload: GetGistRequest):
    """
    Accepts:
      {
        "resume": "...text...",
        "jd": "...text...",
        "labels": ["Full Name", "Email", "Years of experience", ...]
      }

    Returns:
      { "Full Name": "Rajni", "Email": "...", ... }
    """
    try:
        parsed_resume = {"raw_text": payload.resume}
        jd_data = {"job_description": payload.jd or ""}
        labels = payload.labels or []

        # run potentially CPU/IO work in threadpool if needed
        answers = await gist_generator.generate_gist_for_labels(parsed_resume, jd_data, labels)
        return GetGistResponse(success=True, detail="Gists generated", answers=answers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gist generation failed: {e}")
