from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Request
import shutil
from dotenv import load_dotenv
import os
import re
import asyncio
import sys
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager  # ✅ ADD THIS
from rate_limit import limiter 
from validators import validate_resume_file 

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# --- Windows asyncio fix for Playwright ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load environment variables
load_dotenv()
print("🔑 HuggingFace API Key Loaded:",
      os.getenv("HF_API_KEY")[:10] + "..." if os.getenv("HF_API_KEY") else "MISSING")
print("🌐 HuggingFace API URL:", os.getenv("HF_API_URL"))



# -------------------------------
# FastAPI app initialization
# -------------------------------
from contextlib import asynccontextmanager

# ✅ LIFESPAN CONTEXT MANAGER
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Server starting up...")
    print("🔥 Warming up models...")
    
    try:
        # Import modules to trigger model loading
        from services import matcher
        from services import skill_normalizer
        print("✅ Models loaded during startup")
    except Exception as e:
        print(f"⚠️ Model loading failed (will load on first request): {e}")
    
    print("✅ Server ready!")
    
    yield  # Server is running
    
    # Shutdown (cleanup if needed)
    print("👋 Server shutting down...")


    # Import project modules after env setup
from services import parser
from services import jd_fetcher
from services.matcher_api import router as matcher_router
from services.applier_api import router as applier_api
from services.gist_generator import generate_gist   # <-- you already have this file

app = FastAPI(
    title="AI Job Applier Backend",
    description="FastAPI service that parses resumes, fetches job descriptions, and automates job applications on Greenhouse.",
    version="1.0.0",
    lifespan=lifespan  # ✅ Add this
)

# Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================
# ✅ UPDATED CORS - Production Ready
# ============================================

# Base allowed origins (local development)
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]

# ✅ Add production frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    ALLOWED_ORIGINS.append(frontend_url)
    print(f"✅ Added production frontend: {frontend_url}")

# ✅ CRITICAL: Allow Chrome Extension requests
# Chrome extensions have origin like: chrome-extension://abc123...
# We need to allow ALL chrome-extension origins

# ✅ For Vercel preview deployments (optional but useful)
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    ALLOWED_ORIGINS.append(f"https://{vercel_url}")
    print(f"✅ Added Vercel preview: https://{vercel_url}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"^chrome-extension://.*$"  # ✅ Allow all Chrome extensions
)

#pydantic models
class FieldItem(BaseModel):
    label: str
    type: str
    options: Optional[List[str]] = None

class GistRequest(BaseModel):
    resume: Dict[str, Any]
    job_description: Optional[str] = None
    fields: List[FieldItem]

class GistResponse(BaseModel):
    success: bool
    message: str
    answers: Dict[str, Any]

# ============================================
# Register routers
# ============================================
app.include_router(matcher_router)
app.include_router(applier_api, prefix="/api")


@app.get("/warmup")
def warmup():
    """Keep instance warm and models loaded"""
    from datetime import datetime
    return {
        "status": "warm",
        "semantic_enabled": os.getenv("MATCHER_SEMANTIC", "1") != "0",
        "timestamp": datetime.now().isoformat()
    }

# ============================================
# Health Check Endpoints
# ============================================

@app.get("/")
def read_root():
    return {"message": "AI Job Applier Backend Running!"}

# ✅ ADD THIS - Better for monitoring services
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "playwright_installed": True  # You can add actual checks here
    }


# -------------------------------
# Resume Parser Endpoint
# -------------------------------
@app.post("/parser_resume/")
@limiter.limit("10/minute")
async def parse_resume_endpoint(
    request: Request,
    file: UploadFile = File(...)
):
    file_content = await validate_resume_file(file)
    try:
        temp_file = f"temp_{file.filename}"
        with open(temp_file, "wb") as buffer:
            buffer.write(file_content)

        if file.filename.endswith(".pdf"):
            text = parser.parse_pdf(temp_file)
        elif file.filename.endswith(".docx"):
            text = parser.parse_docx(temp_file)
        else:
            os.remove(temp_file)
            raise HTTPException(status_code=400, detail="Unsupported file format")

        os.remove(temp_file)
        return {"filename": file.filename, "content": text[:2000]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------
# Fetch JD Endpoint
# -------------------------------
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

@app.get("/fetch_jd")
@limiter.limit("10/minute")
async def fetch_jd(
    request: Request,
    url: str = Query(..., description="URL of the job posting")
):
    try:
        res = jd_fetcher.fetch_job_description(url)

        full_txt = res.get("job_description_full") or ""
        if "<" in full_txt and ">" in full_txt:
            full_txt = strip_html_to_text(full_txt)
        res["job_description_full"] = full_txt

        sections = res.get("jd_sections") or {}
        sections = {
            "responsibilities": clean_section_items(sections.get("responsibilities")),
            "skills": clean_section_items(sections.get("skills")),
            "bonus_skills": clean_section_items(sections.get("bonus_skills")),
        }
        res["jd_sections"] = sections

        rel = "\n".join(
            sections.get("responsibilities", [])
            + sections.get("skills", [])
            + sections.get("bonus_skills", [])
        ).strip()
        res["job_description_relevant"] = rel[:8000]

        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD fetch failed: {str(e)}")


# -------------------------------
# Generate Gists Endpoint
# -------------------------------
@app.post("/generate-gists", response_model=GistResponse)
@limiter.limit("20/minute")
async def generate_gists_endpoint(
    request: Request,
    data: GistRequest
):
    """
    Extension sends:
    - resume (parsed_resume dict)
    - job_description text
    - fields = [ {label, type, options}, ... ]

    We call your existing generate_gist() with:
    parsed_resume, jd_data, form_fields
    """

    try:
        # Match EXACT signature of your working function:
        # async def generate_gist(parsed_resume, jd_data, form_fields)
        
        answers = await generate_gist(
            data.resume,            # parsed_resume
            {"job_description": data.job_description},  # jd_data (dict required)
            [field.dict() for field in data.fields]     # form_fields
        )

        return GistResponse(
            success=True,
            message="Gists generated successfully.",
            answers=answers
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gist generation failed: {str(e)}"
        )

# ============================================
# ✅ ADD THIS - For Render deployment
# ============================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False  # Disable reload in production
    )