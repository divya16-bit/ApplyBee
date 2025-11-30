# app/services/matcher_api.py
from fastapi import APIRouter, UploadFile, Form, File, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from bs4 import BeautifulSoup
from typing import Optional
import shutil
import os
import re

from services import matcher
from services.jd_fetcher import fetch_job_description, is_allowed_job_url
from rate_limit import limiter
from validators import validate_resume_file 
from services import parser as resume_parser

router = APIRouter()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HEADERS_TO_DROP = {
    "bonus skills", "what you bring", "about the role", "what you'll do",
    "what you'll do", "you will thrive in this role if", "what you will do"
}

def strip_html_to_text(s: str) -> str:
    if not s:
        return ""
    soup = BeautifulSoup(s, "html.parser")
    txt = soup.get_text("\n", strip=True)
    txt = re.sub(r"[•·▪–—➤▶■□►]", "-", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()

def clean_section_items(items):
    cleaned = []
    for it in items or []:
        t = strip_html_to_text(it) if ("<" in it and ">" in it) else it
        t = t.strip()
        if not t:
            continue
        if t.lower() in HEADERS_TO_DROP:
            continue
        cleaned.append(t)
    return cleaned

def _delete_silent(path: Optional[str]):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

@router.post("/auto_match")
@limiter.limit("5/minute")
async def auto_match( 
    resume: UploadFile = File(...),
    job_url: str = Form(...),
    debug: bool = False,
    request: Request = None 
):
    """
    Upload a resume + job URL.
    Runs ATS-style matching (semantic + TF-IDF + contextual).
    """

    file_content = await validate_resume_file(resume)
    
    if not is_allowed_job_url(job_url):
        raise HTTPException(status_code=400, detail="Only Greenhouse job URLs are supported right now.")

    resume_path = os.path.join(UPLOAD_DIR, resume.filename)
    try:
        with open(resume_path, "wb") as f:
            #shutil.copyfileobj(resume.file, f)
            f.write(file_content)  # 👈 Use validated content

        # Fetch JD
        jd_result = await run_in_threadpool(fetch_job_description, job_url)
        sections = jd_result.get("jd_sections") or {}
        jd_sections = {
            "responsibilities": clean_section_items(sections.get("responsibilities")),
            "skills": clean_section_items(sections.get("skills")),
            "bonus_skills": clean_section_items(sections.get("bonus_skills")),
        }
        if not any(jd_sections.values()):
            raise HTTPException(status_code=400, detail="Could not extract job description sections from URL")

        # Full raw JD text for YoE extraction
        #jd_raw_text = jd_result.get("jd_raw_text", "")
        jd_raw_text = jd_result.get("job_description_full", "")
        if not jd_raw_text:
            jd_raw_text = " ".join(
                jd_sections.get("responsibilities", [])
                + jd_sections.get("skills", [])
                + jd_sections.get("bonus_skills", [])
            )

        # Extract JD profile + skills
        jd_profile = jd_result.get("jd_profile") or {}
        jd_keywords = jd_profile.get("keywords") or []
        jd_skills_extracted = [k.get("name") for k in jd_keywords if k.get("name")]

        # Parse resume to text
        
        ext = os.path.splitext(resume_path)[1].lower()
        if ext == ".pdf":
            resume_text = await run_in_threadpool(resume_parser.parse_pdf, resume_path)
        elif ext == ".docx":
            resume_text = await run_in_threadpool(resume_parser.parse_docx, resume_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use PDF or DOCX.")

        if not resume_text or len(resume_text.strip()) < 20:
            raise HTTPException(status_code=400, detail="Could not extract text from resume.")

        # Run matcher
        result = await run_in_threadpool(
            matcher.calculate_match_score_text,
            resume_text_raw=resume_text,
            jd_sections=jd_sections,
            jd_skills_extracted=jd_skills_extracted,
            jd_full_text=jd_raw_text,
            debug=debug
        )

        # Normalize JD YoE for API output
        jd_yoe_val = result.get("years_experience_jd")
        if isinstance(jd_yoe_val, tuple):
            jd_yoe_output = list(jd_yoe_val)  # [min, max]
        else:
            jd_yoe_output = jd_yoe_val
        
        skill_gap = result.get("skill_gap_analysis", {})

        return {
            "filename": resume.filename,
            "job_url": job_url,
            "ats_score": result.get("ats_score", 0),
            "responsibility_score": result.get("responsibility_score", 0),
            "skills_score": result.get("skills_score", 0),
            "bonus_score": result.get("bonus_score", 0),
            "common_skills": result.get("common_skills", []),
            "missing_skills": result.get("missing_skills", []),
            "jd_skills_used": result.get("jd_skills_used", []),
            "normalized_overlap": result.get("normalized_overlap", []),
            "normalized_missing": result.get("normalized_missing", []),

            # NEW: explicitly expose direct vs contextual skill scores
            "direct_skill_score": result.get("direct_skill_score", 0),
            "contextual_skill_score": result.get("contextual_skill_score", 0),
            "all_matched_skills": result.get("all_matched_skills", []),
            "bonus_skills_jd": result.get("bonus_skills_jd", []),
            "matched_bonus_skills": result.get("matched_bonus_skills", []),

            "years_experience_resume": result.get("years_experience_resume"),
            "years_experience_jd": jd_yoe_output,
            "yoe_score": result.get("yoe_score", 0),

            "critical_gaps": skill_gap.get("critical_gaps", []),
            "recommended_gaps": skill_gap.get("recommended_gaps", []),
            "covered_categories": skill_gap.get("covered_categories", []),
                       
            "summary": result.get("summary", ""),
            "raw_section_scores": result.get("raw_section_scores", {}),
            "jd_summary": {
                "title": jd_profile.get("title"),
                "company": jd_profile.get("company_hint"),
                "location": jd_profile.get("location"),
                "work_model": jd_profile.get("work_model"),
                "years_experience": jd_profile.get("years_experience"),
                "seniority": jd_profile.get("seniority"),
            },
            "debug": jd_result.get("debug"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto match failed: {str(e)}")
    finally:
        _delete_silent(resume_path)

