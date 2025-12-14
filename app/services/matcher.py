# app/services/matcher.py
from __future__ import annotations
import os
import re
import pathlib
from typing import Dict, List, Tuple, Optional, Set
from loguru import logger

import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction import text as sk_text
from sentence_transformers import SentenceTransformer, util

# Use your parser service (supports PDF + DOCX)
from services.skill_normalizer import normalize_skills
from datetime import datetime

STOPWORDS = sk_text.ENGLISH_STOP_WORDS
# Separate flags for different use cases
# MATCHER_SEMANTIC_SCORE: Use semantic matching for resume score (slow but accurate)
# MATCHER_SEMANTIC_NORMALIZER: Use semantic matching for skill normalization (fast, small model)
USE_SEMANTIC_SCORE = str(os.getenv("MATCHER_SEMANTIC_SCORE", "0")).lower() not in {"0", "false", "no"}  # Default OFF for speed
USE_SEMANTIC_NORMALIZER = str(os.getenv("MATCHER_SEMANTIC_NORMALIZER", "1")).lower() not in {"0", "false", "no"}  # Default ON (fast)

# Legacy support: MATCHER_SEMANTIC controls both if set
LEGACY_SEMANTIC = str(os.getenv("MATCHER_SEMANTIC", "")).lower()
if LEGACY_SEMANTIC and LEGACY_SEMANTIC not in {"0", "false", "no"}:
    USE_SEMANTIC_SCORE = True
    USE_SEMANTIC_NORMALIZER = True
elif LEGACY_SEMANTIC in {"0", "false", "no"}:
    USE_SEMANTIC_SCORE = False
    USE_SEMANTIC_NORMALIZER = False

# For backward compatibility in code
USE_SEMANTIC = USE_SEMANTIC_SCORE  # Used for score calculation


# -----------------------------
# Normalization helpers
# -----------------------------
ALIASES = {
    # frontend frameworks
    "react.js": "react",
    "reactjs": "react",
    "next.js": "nextjs",
    "node.js": "node",
    "js": "javascript",
    # databases
    "postgres": "postgresql",
    "sqlserver": "sql_server",
    # misc
    "py": "python",
    "apis": "api",
    "api(s)": "api",
}

def apply_aliases(token: str) -> str:
    return ALIASES.get(token, token)

def preprocess_text(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s\+\#\-\.]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def tokenize_and_filter(s: str) -> set[str]:
    words = set(s.split())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}

# -----------------------------
# Resume text extraction
# -----------------------------
def extract_text_from_resume(path: str) -> str:
    ext = pathlib.Path(path).suffix.lower()
    if ext == ".pdf":
        return resume_parser.parse_pdf(path)
    if ext == ".docx":
        return resume_parser.parse_docx(path)
    raise ValueError("Unsupported resume format. Please upload PDF or DOCX.")


# ============================================
# IMPROVED YoE EXTRACTION - START
# ============================================

CURRENT_YEAR = datetime.now().year
CURRENT_MONTH = datetime.now().month

MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}

def parse_date_to_months(date_str: str) -> int:
    """
    Convert a date string to total months from year 0.
    Returns months as integer for easy calculation.
    """
    date_str = date_str.lower().strip()
    
    # Handle "present", "current", "now"
    if any(word in date_str for word in ["present", "current", "now", "ongoing"]):
        return (CURRENT_YEAR * 12) + CURRENT_MONTH
    
    # Try to extract year (required)
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if not year_match:
        return 0
    
    year = int(year_match.group(0))
    
    # Try to extract month
    month = 1  # Default to January if month not specified
    for month_name, month_num in MONTHS.items():
        if month_name in date_str:
            month = month_num
            break
    
    return (year * 12) + month


def extract_years_of_experience(text: str, source: str = "resume"):
    """
    Enhanced YoE extraction with better accuracy.
    
    For JD: Returns explicit requirements (e.g., "3-5 years" -> (3.0, 5.0))
    For Resume: Sums all employment periods
    """
    if not text:
        return 0.0

    text = text.lower()
    
    # ============================================
    # JD-SPECIFIC: Extract explicit requirements
    # ============================================
    if source == "jd":
        # Pattern 1: "3-5 years", "3 to 5 years"
        range_pattern = r'(\d{1,2})\s*(?:[-–—]|to)\s*(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)'
        range_matches = re.findall(range_pattern, text)
        
        for low_str, high_str in range_matches:
            try:
                low, high = int(low_str), int(high_str)
                if 0 < low <= high <= 50:
                    return (float(low), float(high))
            except:
                continue
        
        # Pattern 2: "5+ years", "minimum 3 years"
        single_patterns = [
            r'(\d{1,2})\+\s*(?:years?|yrs?)',
            r'(?:minimum|min|at least)\s*(?:of\s*)?(\d{1,2})\s*(?:years?|yrs?)',
            r'(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
        ]
        
        for pattern in single_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    yoe = int(match)
                    if 0 < yoe <= 50:
                        return float(yoe)
                except:
                    continue
    
    # ============================================
    # RESUME-SPECIFIC: Calculate from job history
    # ============================================
    if source == "resume":
        date_ranges = []
        
        # Enhanced date range patterns
        patterns = [
            r'(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\s+\d{4})\s*(?:[-–—]|to)\s*(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\s+\d{4}|present|current)',
            r'(\b(?:19|20)\d{2})\s*(?:[-–—]|to)\s*(\b(?:19|20)\d{2}|present|current)',
            r'(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\s+\d{4})\s*(?:[-–—]|to)\s*(present|current|now)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for start_str, end_str in matches:
                start_months = parse_date_to_months(start_str)
                end_months = parse_date_to_months(end_str)
                
                if start_months > 0 and end_months > 0 and end_months >= start_months:
                    duration_months = end_months - start_months
                    duration_years = duration_months / 12.0
                    
                    if 0 < duration_years <= 50:
                        date_ranges.append({
                            'start': start_months,
                            'end': end_months,
                            'duration': duration_years
                        })
        
        # Remove overlapping periods
        if date_ranges:
            date_ranges.sort(key=lambda x: x['start'])
            
            merged = []
            for current in date_ranges:
                if not merged:
                    merged.append(current)
                else:
                    last = merged[-1]
                    if current['start'] <= last['end']:
                        last['end'] = max(last['end'], current['end'])
                        last['duration'] = (last['end'] - last['start']) / 12.0
                    else:
                        merged.append(current)
            
            total_years = sum(period['duration'] for period in merged)
            
            if total_years > 0:
                return round(total_years, 1)
        
        # Fallback: explicit mentions
        explicit_patterns = [
            r'(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
            r'(?:with|over|around)\s*(\d{1,2})\+?\s*(?:years?|yrs?)',
        ]
        
        for pattern in explicit_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    yoe = int(match)
                    if 0 < yoe <= 50:
                        return float(yoe)
                except:
                    continue
    
    return 0.0

# ============================================
# IMPROVED YoE EXTRACTION - END
# ============================================


# -----------------------------
# Semantic model 
# -----------------------------
_MODEL_NAME = os.getenv("SENTENCE_MODEL", "all-MiniLM-L6-v2")
_semantic_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _semantic_model
    if _semantic_model is None:
        print("🔄 Loading sentence transformer model...")
        _semantic_model = SentenceTransformer(_MODEL_NAME)
        print("✅ Model loaded successfully")
    return _semantic_model

# ✅ PRE-LOAD MODEL ON MODULE IMPORT (during server startup)
# Only pre-load if semantic matching is enabled for score calculation
if USE_SEMANTIC_SCORE:
    print("🚀 Pre-loading semantic model for score calculation...")
    try:
        _ = get_model()
        print("✅ Model ready for requests")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        USE_SEMANTIC_SCORE = False
        USE_SEMANTIC = False

def chunk_text_words(text: str, chunk_size: int = 220, overlap: int = 40) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    i = 0
    step = max(1, chunk_size - overlap)
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += step
    return chunks

def embed_chunks(text: str, chunk_size: int = 220, overlap: int = 40):
    model = get_model()
    chunks = chunk_text_words(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return [], model.encode([""], convert_to_tensor=True, normalize_embeddings=True)
    emb = model.encode(chunks, convert_to_tensor=True, normalize_embeddings=True)
    return chunks, emb

def tfidf_score(a: str, b: str) -> float:
    if not a.strip() or not b.strip():
        return 0.0
    try:
        vec = TfidfVectorizer(stop_words="english")
        mat = vec.fit_transform([a, b])
        score = cosine_similarity(mat[0:1], mat[1:2])[0][0] * 100.0
        return float(score) if score == score else 0.0
    except Exception:
        return 0.0

def semantic_score_against_chunks(resume_chunks_emb: torch.Tensor, section_text: str) -> float:
    if not USE_SEMANTIC_SCORE:
        return 0.0
    if not section_text.strip():
        return 0.0
    _, sec_emb = embed_chunks(section_text, chunk_size=160, overlap=30)
    if sec_emb.size(0) == 0 or resume_chunks_emb.size(0) == 0:
        return 0.0
    sims = util.cos_sim(sec_emb, resume_chunks_emb)
    topk = min(3, sims.size(-1))
    topk_vals, _ = torch.topk(sims, k=topk, dim=-1)
    return float(topk_vals.mean().item()) * 100.0

def section_match(resume_text_norm: str, resume_chunks_emb: torch.Tensor, section_text_raw: str) -> Tuple[float, float, float]:
    tfidf = tfidf_score(resume_text_norm, preprocess_text(section_text_raw))
    sem = semantic_score_against_chunks(resume_chunks_emb, section_text_raw) if USE_SEMANTIC_SCORE else 0.0
    # If semantic is disabled, use TF-IDF only (faster)
    combined = (0.6 * sem) + (0.4 * tfidf) if USE_SEMANTIC_SCORE else tfidf
    return combined, tfidf, sem

# -----------------------------
# Skill extraction
# -----------------------------
TECH_SKILLS = {
    "python","java","c++","c#","javascript","typescript","react","reactjs","nextjs","next","angular","vue",
    "node","nodejs","express","django","flask","spring","kubernetes","docker","aws","azure","gcp","sql",
    "mysql","postgresql","nosql","mongodb","graphql","rest","api","jenkins","git","devops","html","css",
    "sass","less","bootstrap","tailwind","linux","tensorflow","pytorch","nlp","machinelearning","ml","ai",
    "spark","hadoop","pandas","numpy","kafka","redis","webpack","babel","vite","eslint","jest","rtl",
    "cypress","storybook","redux","frontend","ui","ux","designsystems","postgres"
}
NOISE_TOKENS = {
    "instagram","linkedin","facebook","twitter","com","www","http","https","hackerrank",
    "race","color","gender","sex","origin","disability","identity","veteran","applicants",
    "life","day","ability","world","record","notice","customers"
}

# Generic domain terms that are too broad to be actionable skills
GENERIC_DOMAIN_TERMS = {
    "frontend", "backend", "fullstack", "full-stack", "full stack",
    "ui", "ux", "devops", "cloud", "web", "mobile", "desktop",
    "software", "development", "engineering", "programming", "coding"
}

def extract_skills_simple(text_raw: str) -> set[str]:
    t = preprocess_text(text_raw)
    tokens = set(t.split())
    tokens |= {tok.replace(".", "") for tok in tokens}
    tokens = {apply_aliases(tok) for tok in tokens if tok not in NOISE_TOKENS and len(tok) > 2}
    return {s for s in TECH_SKILLS if s in tokens}

# -----------------------------
# Deduplication helper
# -----------------------------
def dedupe_normalized(norm_list: List[Tuple[str, str, float]]) -> List[Tuple[str, str, float]]:
    """Deduplicate by (category, skill)"""
    seen = set()
    deduped = []
    for skill, cat, score in norm_list:
        key = (skill.lower(), cat.lower())
        if key not in seen:
            seen.add(key)
            deduped.append((skill, cat, score))
    return deduped

# -----------------------------
# Main scoring function
# -----------------------------
def calculate_match_score_text(
    resume_text_raw: str,
    jd_sections: Dict[str, List[str]],
    jd_skills_extracted: Optional[List[str]] = None,
    debug: bool = False,
    jd_full_text: str = ""
):
    if not resume_text_raw or not resume_text_raw.strip():
        return {
            "ats_score": 0.0,
            "summary": "Resume text could not be extracted.",
            "responsibility_score": 0.0,
            "skills_score": 0.0,
            "common_skills": [],
            "missing_skills": [],
            "jd_skills_used": [],
            "raw_section_scores": {}
        }

    resume_text_norm = preprocess_text(resume_text_raw)
    _, resume_chunks_emb = embed_chunks(resume_text_raw, chunk_size=220, overlap=40) if USE_SEMANTIC_SCORE else ([], torch.zeros(0))

    def join(name: str) -> str:
        return "\n".join(jd_sections.get(name, []) or [])

    jd_resp_raw, jd_skills_raw = join("responsibilities"), join("skills")

    # ✅ NEW: If no skills section found, extract from full text
    if not jd_skills_raw.strip() and jd_full_text:
        logger.warning("Skills section empty, extracting from full JD text")
        jd_skill_terms = extract_skills_simple(jd_full_text)
    else:
        # Extract skills from jd_skills_extracted - these might be full sentences, so extract technical skills from them
        if jd_skills_extracted:
            # jd_skills_extracted contains raw text from JD skills section (could be sentences)
            # Extract technical skills from each item, then combine
            extracted_skills = set()
            for item in jd_skills_extracted:
                if isinstance(item, str):
                    # Extract technical skills from this sentence/item
                    skills_from_item = extract_skills_simple(item)
                    extracted_skills.update(skills_from_item)
            jd_skill_terms = extracted_skills if extracted_skills else extract_skills_simple(jd_skills_raw)
        else:
            jd_skill_terms = extract_skills_simple(jd_skills_raw)

    resp_combined, resp_tfidf, resp_sem = section_match(resume_text_norm, resume_chunks_emb, jd_resp_raw)
    skills_combined, skills_tfidf, skills_sem = section_match(resume_text_norm, resume_chunks_emb, jd_skills_raw)

    #ats_score = (0.5 * resp_combined) + (0.5 * skills_combined)

    # -----------------------------
    # Skill Extraction & Normalization
    # -----------------------------
    resume_skills = extract_skills_simple(resume_text_raw)
    logger.info(f"🔍 Resume skills extracted: {len(resume_skills)} skills")
    
    # Extract skills from jd_skills_extracted - filter to only technical skills
    if jd_skills_extracted:
        # jd_skills_extracted contains raw text from JD skills section (could be sentences)
        # Extract technical skills from each item, then combine
        extracted_skills = set()
        for item in jd_skills_extracted:
            if isinstance(item, str):
                # Extract technical skills from this sentence/item
                skills_from_item = extract_skills_simple(item)
                extracted_skills.update(skills_from_item)
        jd_skill_terms = extracted_skills if extracted_skills else extract_skills_simple(jd_skills_raw)
    else:
        jd_skill_terms = extract_skills_simple(jd_skills_raw)
    
    logger.info(f"🔍 JD skills extracted: {len(jd_skill_terms)} skills, sample: {list(jd_skill_terms)[:10]}")
   
    common = sorted(list(resume_skills & jd_skill_terms))[:30]
    missing = sorted(list(jd_skill_terms - resume_skills))[:30]
    logger.info(f"🔍 Common skills: {len(common)}, Missing skills (before filters): {len(missing)}, sample: {missing[:10]}")
    
    # Filter missing skills to remove any that look like job descriptions (safety check)
    # Keep only short technical terms (max 30 chars) that are actual skills
    # Exclude generic domain terms (too broad, not actionable)
    missing = [m for m in missing if len(m) <= 30 and m not in NOISE_TOKENS and m not in GENERIC_DOMAIN_TERMS]
    
    # Additional filter using skill normalizer: exclude skills that normalize poorly
    # BUT: Keep skills that are in TECH_SKILLS (they're known valid skills)
    # Only filter out skills that are NOT in TECH_SKILLS AND normalize very poorly
    if missing:
        logger.info(f"🔍 Missing skills before normalization: {missing[:10]}")
        missing_norm = normalize_skills(missing, threshold=0.4)
        # Keep skills that:
        # 1. Are in TECH_SKILLS (known valid technical skills) - check lowercase, OR
        # 2. Normalize to a specific category (not "other"), OR
        # 3. Have any similarity score (>= 0.1) - very lenient to avoid filtering out valid skills
        missing_before = len(missing)
        missing = [m for m, (_, cat, score) in zip(missing, missing_norm) 
                   if m.lower() in TECH_SKILLS or cat != "other" or score >= 0.1]
        logger.info(f"🔍 Missing skills after normalization filter: {missing[:10]} (was {missing_before}, now {len(missing)})")

    # Normalize both resume and JD skills
    resume_norm = normalize_skills(list(resume_skills))
    jd_norm = normalize_skills(list(jd_skill_terms))


    normalized_overlap = []
    normalized_missing = []

    resume_cats = {c for (_, c, s) in resume_norm if s >= 0.6}
    jd_cats = {c for (_, c, s) in jd_norm if s >= 0.6}

    '''
    # Contextual overlap (category-based)
    for r, rc, rs in resume_norm:
        for j, jc, js in jd_norm:
            if rc != "other" and rc == jc:
                normalized_overlap.append((f"{r} ↔ {j}", rc, 1.0))
    '''

    # Contextual overlap (category-based) - avoid duplicates
    seen_pairs = set()
    for r, rc, rs in resume_norm:
        for j, jc, js in jd_norm:
            if rc != "other" and rc == jc:
                # Create normalized pair key (sorted to avoid A↔B vs B↔A duplicates)
                pair_key = tuple(sorted([r.lower(), j.lower()]))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    normalized_overlap.append((f"{r} ↔ {j}", rc, 1.0))
                

    # Contextual missing (JD categories not present in resume)
    # Only include actual technical skills, not job description sentences
    for j, jc, js in jd_norm:
        if jc not in resume_cats and jc != "other":
            # Filter out long sentences and job description phrases
            if len(j) <= 30 and j not in NOISE_TOKENS and j not in GENERIC_DOMAIN_TERMS:
                # Additional filter: exclude if it looks like a sentence/phrase
                if not any(phrase in j.lower() for phrase in [
                    'experience with', 'working with', 'familiar with', 'comfortable with',
                    'you will', "you'll", 'collaborate', 'mentor', 'improve workflows',
                    'ability to', 'strong', 'excellent', 'good', 'knowledge of'
                ]):
                    normalized_missing.append((j, jc, js))

    normalized_overlap = dedupe_normalized(normalized_overlap)
    normalized_missing = dedupe_normalized(normalized_missing)
    
    # Fallback: if normalized_missing is empty but we have missing skills from direct comparison,
    # include some from the direct missing list (they passed initial filters)
    if not normalized_missing and missing:
        # Take top missing skills that are short and not generic
        for m in missing[:10]:  # Limit to top 10
            if len(m) <= 30 and m not in GENERIC_DOMAIN_TERMS:
                # Quick check: if it's a known tech skill or looks like one
                if any(char.isalnum() for char in m) and not any(phrase in m.lower() for phrase in [
                    'experience', 'working', 'familiar', 'comfortable', 'you', 'collaborate'
                ]):
                    normalized_missing.append((m, "other", 0.5))  # Default category and score

    # --- FIX: Only remove EXACT matches, not contextual ---
    # Get skills from normalized_overlap that are from JD side
    covered_jd_terms = set()
    for pair, cat, score in normalized_overlap:
        parts = pair.split("↔")
        if len(parts) == 2:
            resume_skill, jd_skill = parts[0].strip().lower(), parts[1].strip().lower()
            # Only mark as covered if it's an exact match
            if resume_skill == jd_skill:
                covered_jd_terms.add(jd_skill)

    # Keep skills that aren't exactly matched
    missing = [m for m in missing if m.lower() not in covered_jd_terms]

    # -----------------------------
    # Rebalanced ATS formula
    # -----------------------------
    direct_skill_score = min(100.0, (len(common) / max(1, len(jd_skill_terms))) * 100.0)
    contextual_skill_score = min(100.0, (len(normalized_overlap) / max(1, len(jd_norm))) * 100.0)
    all_matched_skills = sorted({
        r.strip().lower()
        for (pair, _, _) in normalized_overlap
        for r in [pair.split("↔")[0]]  # only resume-side skill
    } | {c.strip().lower() for c in common})

     # -----------------------------
    # YoE scoring with ranges
    # -----------------------------
    '''
    resume_yoe = extract_years_of_experience(resume_text_raw, source="resume")
    jd_text_combined = jd_resp_raw + " " + jd_skills_raw
    jd_yoe = extract_years_of_experience(jd_text_combined, source="jd")

    yoe_score = 0.0
    if isinstance(jd_yoe, tuple):
        low, high = jd_yoe
        if low <= resume_yoe <= high:
            yoe_score = 100.0
        elif resume_yoe < low and low > 0:
            yoe_score = min((resume_yoe / low) * 100.0, 100.0)
        elif resume_yoe > high:
            yoe_score = 100.0
    elif isinstance(jd_yoe, float) and jd_yoe > 0:
        yoe_score = min((resume_yoe / jd_yoe) * 100.0, 100.0)

    ats_score = (
        (0.30 * resp_combined) +
        (0.35 * direct_skill_score) +
        (0.25 * contextual_skill_score) +
        (0.10 * yoe_score)
    )
    '''

    # -----------------------------
    # IMPROVED YoE scoring
    # -----------------------------
    resume_yoe = extract_years_of_experience(resume_text_raw, source="resume")
    jd_text_combined = jd_resp_raw + " " + jd_skills_raw
    # Use full text if available for better extraction
    if jd_full_text:
        jd_text_combined = jd_full_text
    
    jd_yoe = extract_years_of_experience(jd_text_combined, source="jd")

    # Calculate score with improved logic
    yoe_score = 0.0
    
    if resume_yoe == 0 and jd_yoe == 0:
        yoe_score = 100.0  # Both don't specify
    elif jd_yoe == 0 or jd_yoe == 0.0:
        yoe_score = 100.0  # JD doesn't require specific YoE
    elif resume_yoe == 0 or resume_yoe == 0.0:
        yoe_score = 50.0  # Resume doesn't show experience
    elif isinstance(jd_yoe, tuple):
        # JD has range (e.g., 3-5 years)
        low, high = jd_yoe
        
        if low <= resume_yoe <= high:
            yoe_score = 100.0  # Perfect fit
        elif resume_yoe < low:
            shortage = low - resume_yoe
            if shortage <= 1:
                yoe_score = 90.0
            elif shortage <= 2:
                yoe_score = 75.0
            else:
                yoe_score = max(40.0, 100.0 - (shortage * 15))
        else:  # resume_yoe > high
            overage = resume_yoe - high
            if overage <= 2:
                yoe_score = 95.0
            elif overage <= 5:
                yoe_score = 85.0
            else:
                yoe_score = max(60.0, 100.0 - (overage * 5))
    else:
        # JD has single value (e.g., "5 years minimum")
        jd_min = float(jd_yoe)
        
        if resume_yoe >= jd_min:
            overage = resume_yoe - jd_min
            if overage <= 2:
                yoe_score = 100.0
            elif overage <= 5:
                yoe_score = 90.0
            else:
                yoe_score = max(70.0, 100.0 - (overage * 4))
        else:
            shortage = jd_min - resume_yoe
            if shortage <= 1:
                yoe_score = 85.0
            elif shortage <= 2:
                yoe_score = 70.0
            else:
                yoe_score = max(30.0, 100.0 - (shortage * 20))

    # Adjust weights based on whether semantic matching is enabled
    # When semantic is disabled, TF-IDF scores are typically lower, so we:
    # 1. Give more weight to direct skill matching (most reliable)
    # 2. Give more weight to YoE (objective measure)
    # 3. Boost TF-IDF scores slightly to compensate
    if USE_SEMANTIC_SCORE:
        # Original weights with semantic matching
        ats_score = (
            (0.30 * resp_combined) +
            (0.35 * direct_skill_score) +
            (0.25 * contextual_skill_score) +
            (0.10 * yoe_score)
        )
    else:
        # Adjusted weights without semantic matching - more emphasis on direct skills and YoE
        # Boost TF-IDF scores slightly to compensate for lower semantic scores
        resp_boosted = min(100.0, resp_combined * 1.4)  # Boost TF-IDF by 40%
        skills_boosted = min(100.0, skills_combined * 1.4)  # Boost TF-IDF by 40%
        resp_combined_adj = (resp_boosted + resp_combined) / 2  # Average of boosted and original
        skills_combined_adj = (skills_boosted + skills_combined) / 2
        
        ats_score = (
            (0.20 * resp_combined_adj) +  # Reduced from 0.30
            (0.50 * direct_skill_score) +  # Increased from 0.35 (most reliable)
            (0.15 * contextual_skill_score) +  # Reduced from 0.25
            (0.15 * yoe_score)  # Increased from 0.10 (objective measure)
        )
    
    
    # -----------------------------
    # Skill Gap Analysis
    # -----------------------------
    high_priority_cats = {"backend_frameworks", "databases", "cloud_platforms", "api_development"}
    critical_gaps = []
    recommended_gaps = []

    for m in missing:
        # Find category from jd_norm
        cat = next((jc for (j, jc, js) in jd_norm if j == m), "other")
        if cat in high_priority_cats:
            critical_gaps.append(m)
        else:
            recommended_gaps.append(m)

    covered_categories = sorted({c for (_, c, s) in resume_norm if s >= 0.6})
    

    return {
        "ats_score": round(ats_score, 2),
        "responsibility_score": round(resp_combined, 2),
        "skills_score": round(skills_combined, 2),
        "common_skills": common,
        "missing_skills": missing,

        "jd_skills_used": sorted(list(jd_skill_terms))[:50],
        "normalized_overlap": normalized_overlap,
        "normalized_missing": normalized_missing,
        "direct_skill_score": round(direct_skill_score, 2),
        "contextual_skill_score": round(contextual_skill_score, 2),
        "all_matched_skills": all_matched_skills,
        
        "years_experience_resume": resume_yoe,
        "years_experience_jd": jd_yoe,
        "yoe_score": round(yoe_score, 2),
        "skill_gap_analysis": {
            "critical_gaps": critical_gaps,
            "recommended_gaps": recommended_gaps,
            "covered_categories": covered_categories
        },
        "summary": (
            f"ATS Score: {ats_score:.2f}% "
            f"(Responsibilities: {resp_combined:.1f}% [T:{resp_tfidf:.1f}/S:{resp_sem:.1f}], "
            f"Skills: {skills_combined:.1f}% [T:{skills_tfidf:.1f}/S:{skills_sem:.1f}], "
            f"Skills Overlap: {len(common)} direct, {len(normalized_overlap)} contextual. "
            f"Resume YoE={resume_yoe}, JD YoE={jd_yoe}, YoE Score={yoe_score:.1f}"
            f"{' [Fast Mode: TF-IDF only]' if not USE_SEMANTIC_SCORE else ''}"
        ),
        "raw_section_scores": {
            "responsibilities": {"combined": resp_combined, "tfidf": resp_tfidf, "semantic": resp_sem},
            "skills": {"combined": skills_combined, "tfidf": skills_tfidf, "semantic": skills_sem},
        }
    }

