import os
import tempfile
from datetime import datetime
from fastapi import APIRouter, UploadFile, Form, File, HTTPException, Request  # 👈 ADD Request
from loguru import logger

from services.applier import apply_to_greenhouse  # async Playwright function
from rate_limit import limiter
from validators import validate_resume_file

router = APIRouter()


@router.post("/apply")
@limiter.limit("2/minute")

async def apply_job(
    job_url: str = Form(...),
    resume: UploadFile = File(...),
    request: Request = None  
):
    """
    Apply to a Greenhouse job with resume autofill.
    
    Process:
    1. Reads uploaded resume
    2. Calls apply_to_greenhouse which handles:
       - Resume parsing
       - JD fetching
       - Form field detection
       - Gist generation
       - Playwright autofill
    """
    try:
        logger.info(f"📨 Received application request for: {job_url}")
        
        # Read resume file content
        #content = await resume.read()
        content = await validate_resume_file(resume)

        logger.info(f"📄 Resume uploaded: {resume.filename} ({len(content)} bytes)")

        # Call the main application service
        # This handles everything: parsing, JD fetch, gist gen, autofill
        result = await apply_to_greenhouse(job_url, content)

        # Return response
        return {
            "status": "success",
            "job_url": job_url,
            "submitted_at": datetime.utcnow().isoformat(),
            "application_result": result,
        }

    except Exception as e:
        logger.error(f"❌ Application failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))