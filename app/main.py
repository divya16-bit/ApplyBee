# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from routers.gist_api import router as gist_router
from routers.score_api import router as score_router

app = FastAPI(
    title="Extension Backend - Gist & Resume Score",
    description="Lightweight backend for browser extension (accepts parsed_resume JSON).",
    version="1.0.0",
)

# CORS: allow extension origins + common localhost/dev origins
allowed = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
frontend_env = os.getenv("FRONTEND_URL")
if frontend_env:
    allowed.append(frontend_env)

# Allow all chrome-extension origins via regex
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"^chrome-extension://.*$"
)

# Include routers
app.include_router(gist_router, prefix="")
app.include_router(score_router, prefix="")

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
