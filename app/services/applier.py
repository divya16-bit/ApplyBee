import os
import tempfile
import logging
import json
from loguru import logger
from datetime import datetime
from app.services.playwright_runner_async import run_playwright_autofill
from app.services.parser import parse_resume
from app.services.jd_fetcher import fetch_job_description
from app.services.gist_generator import generate_gist
from app.services.llm_client import last_llm_used

logger = logging.getLogger(__name__)


def _safe_trim_text(text: str, max_chars: int = 12000) -> str:
    """Lightweight trimming guard to prevent overly long JD/resume payloads."""
    if not text:
        return text
    if len(text) > max_chars:
        logger.warning(f"🪓 Trimming input text from {len(text)} → {max_chars} chars to fit model context window")
        return text[:max_chars] + "..."
    return text


async def apply_to_greenhouse(job_url: str, resume_bytes: bytes, form_data: dict = None):
    temp_resume_path = None
    try:
        # Step 1: Save resume temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(resume_bytes)
            temp_resume_path = tmp.name
        logger.info(f"📄 Saved resume to temp path: {temp_resume_path}")

        # Step 2: Parse resume into structured data
        parsed_resume = parse_resume(temp_resume_path)
        logger.info(f"🧠 Parsed resume fields: {list(parsed_resume.keys())}")

        # Step 3: Fetch JD data (HTML or text)
        jd_data = fetch_job_description(job_url)
        logger.info(f"📜 Job description fetched ({len(jd_data)} chars)")

        # Step 4: Run Playwright once in "discovery mode" to detect form fields
        logger.info("🧾 Detecting form fields for gist generation...")
        form_preview = await run_playwright_autofill(
            job_url,
            temp_resume_path,
            parsed_resume,
            detect_only=True  # new flag (no autofill yet)
        )

        form_fields = form_preview.get("detected_fields", [])
        logger.info(f"📋 Found {len(form_fields)} form fields")

        # Step 5: Generate contextual answers using JD + Resume + Field labels
        logger.info("🧠 Generating contextual gist answers...")
        jd_data = _safe_trim_text(jd_data)
        gist_answers = await generate_gist(parsed_resume, jd_data, form_fields)
        logger.info(f"✅ Gist answers generated ({len(gist_answers)} fields).")
        logger.info(f"🧩 Preview:\n{json.dumps(gist_answers, indent=2)}")

        # Detect source model from llm_client.py
        llm_used = last_llm_used or "unknown"
        logger.info(f"🤖 LLM used for gist generation: {llm_used}")

        # 🔥 FIX: Pass gist_answers as separate parameter, NOT merged 🔥
        logger.info("🚀 Running Playwright autofill with resume + gist answers...")
        final_result = await run_playwright_autofill(
            job_url=job_url,
            resume_path=temp_resume_path,
            parsed_resume=parsed_resume,
            gist_answers=gist_answers,  # ✅ THIS WAS MISSING!
            manual_submit=True,
            detect_only=False
        )

        # Step 8: Return combined output
        return {
            "status": "success",
            "job_url": job_url,
            "submitted_at": datetime.utcnow().isoformat(),
            "ats_alignment": form_preview.get("ats_alignment", {}),
            "application_result": final_result,
            "gist_answers": gist_answers,
            "llm_source": llm_used,
        }

    except Exception as e:
        logger.error(f"❌ Exception during apply_to_greenhouse: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"status": "error", "error": str(e)}

    finally:
        if temp_resume_path and os.path.exists(temp_resume_path):
            os.remove(temp_resume_path)
            logger.info(f"🧹 Deleted temp file: {temp_resume_path}")

