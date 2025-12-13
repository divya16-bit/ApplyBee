# services/gist_generator.py
import re
import json
from typing import Dict, List, Any
from loguru import logger

try:
    # If you have existing llm client, use it for fallback LLM generation
    from services.llm_client import call_gpt_model
    _LLM_AVAILABLE = True
except Exception:
    _LLM_AVAILABLE = False

# -------------------------
# Basic extractors (resume)
# -------------------------
_email_re = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
_phone_re = re.compile(r'(\+?\d{1,3}[\s-]?)?(\d{6,12})')
_link_re = re.compile(r'(https?://[^\s]+)')
_name_heuristics_re = re.compile(r'^[A-Z][a-z]+\s+[A-Z][a-z]+')  # naive first-last

def extract_email(text: str):
    m = _email_re.search(text)
    return m.group(0).strip() if m else None

def extract_phone(text: str):
    m = _phone_re.search(text)
    if not m:
        return None
    return re.sub(r'\s+', '', m.group(0))

def extract_links(text: str):
    return _link_re.findall(text or "")

def extract_name_from_text(text: str):
    # Try to find a plausible name near top lines
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return None
    # Look at first 6 lines for a name-like pattern
    for ln in lines[:6]:
        if len(ln.split()) <= 4 and name_like(ln):
            return ln.strip()
    # fallback to regex
    m = _name_heuristics_re.search(text or "")
    return m.group(0).strip() if m else None

def name_like(s: str):
    # Basic check: words start with capital letter and are alphabetic
    parts = s.split()
    if len(parts) < 2 or len(parts) > 4:
        return False
    for p in parts:
        if not p[0].isupper():
            return False
    return True

def extract_years_of_experience(text: str):
    txt = (text or "").lower()
    # Look for patterns like '5 years', '5+ years', '4 yrs', 'total years of experience: 3'
    m = re.search(r'(\d{1,2})(\+)?\s*(?:years|yrs)\b', txt)
    if m:
        return f"{m.group(1)} years"
    # look for date ranges and estimate
    years = re.findall(r'(19|20)\d{2}', text or "")
    if len(years) >= 2:
        try:
            low = int(min(years))
            high = int(max(years))
            est = high - low
            if est > 0:
                return f"{est} years"
        except:
            pass
    # fallback heuristics
    if 'senior' in txt:
        return "5+ years"
    if 'intern' in txt.lower():
        return "0-1 years"
    return None

# -------------------------
# Matching helpers
# -------------------------
def simple_token_overlap(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    atoks = set(re.findall(r'\w+', a.lower()))
    btoks = set(re.findall(r'\w+', b.lower()))
    if not atoks or not btoks:
        return 0.0
    inter = atoks.intersection(btoks)
    return len(inter) / max(1, min(len(atoks), len(btoks)))

def is_yes_no_question(label: str) -> bool:
    lbl = (label or "").lower()
    return any(x in lbl for x in ["do you", "have you", "are you", "any experience", "experience in", "do you have", "yes/no", "yes or no", "would you"])

def detect_technology_from_label(label: str):
    lbl = (label or "").lower()
    for tech in ["react", "python", "java", "c++", "c#", "node", "javascript", "typescript", "aws", "azure", "docker", "kubernetes"]:
        if tech in lbl:
            return tech
    return None

# -------------------------
# Main generator
# -------------------------
async def generate_gist_for_labels(parsed_resume: Dict[str, Any], jd_data: Dict[str, Any], labels: List[str]) -> Dict[str, str]:
    """
    Generates mapping label -> short answer.
    parsed_resume: {"raw_text": "...", ...}
    jd_data: {"job_description": "..."}
    labels: list[str]
    """
    try:
        resume_text = parsed_resume.get("raw_text", "") if isinstance(parsed_resume, dict) else str(parsed_resume or "")
        jd_text = jd_data.get("job_description", "") if isinstance(jd_data, dict) else str(jd_data or "")

        # Pre-extract some fields
        email = extract_email(resume_text)
        phone = extract_phone(resume_text)
        links = extract_links(resume_text)
        name = extract_name_from_text(resume_text)
        yoe = extract_years_of_experience(resume_text)
        linkedin = None
        github = None
        for l in links:
            if "linkedin.com" in l.lower():
                linkedin = l
            if "github.com" in l.lower():
                github = l

        answers = {}

        for lbl in labels:
            lbl_norm = (lbl or "").strip()
            if not lbl_norm:
                continue

            # Exact/common label matches
            if re.search(r'first\s*name', lbl_norm, re.I) or re.search(r'full\s*name', lbl_norm, re.I) or re.search(r'name', lbl_norm, re.I) and len(lbl_norm) < 40:
                answers[lbl] = name or ""
                continue
            if re.search(r'email', lbl_norm, re.I):
                answers[lbl] = email or ""
                continue
            if re.search(r'phone|mobile|contact', lbl_norm, re.I):
                answers[lbl] = phone or ""
                continue
            if re.search(r'linkedin', lbl_norm, re.I):
                answers[lbl] = linkedin or email or ""
                continue
            if re.search(r'github|portfolio|website', lbl_norm, re.I):
                answers[lbl] = github or ""
                continue
            if re.search(r'years.*experience|total.*years|yoe|years of experience', lbl_norm, re.I):
                answers[lbl] = yoe or ""
                continue

            # Tech / yes-no questions
            if is_yes_no_question(lbl_norm):
                tech = detect_technology_from_label(lbl_norm)
                if tech:
                    answers[lbl] = "Yes" if tech in resume_text.lower() else "No"
                    continue
                # generic fallback yes for safe default
                answers[lbl] = "Yes"
                continue

            # Numeric preference / salary / notice period
            if re.search(r'salary|compensation', lbl_norm, re.I):
                answers[lbl] = "As per company standards"
                continue
            if re.search(r'notice period', lbl_norm, re.I):
                answers[lbl] = "30 days"
                continue
            if re.search(r'relocation', lbl_norm, re.I):
                answers[lbl] = "Yes"
                continue

            # Try to match from resume by token overlap with label
            best_score = 0.0
            best_snippet = ""
            # take top N snippets from resume (split into sentences)
            snippets = re.split(r'[\n\r]+|\.\s+', resume_text)[:200]
            for s in snippets:
                score = simple_token_overlap(lbl_norm, s)
                if score > best_score:
                    best_score = score
                    best_snippet = s
            if best_score >= 0.25:
                # trim snippet to 200 chars
                answers[lbl] = (best_snippet.strip()[:200])
                continue

            # As a last deterministic fallback, try check JD for label-specific hints
            best_score_jd = 0.0
            best_snippet_jd = ""
            jd_snips = re.split(r'[\n\r]+|\.\s+', jd_text or "")[:200]
            for s in jd_snips:
                sc = simple_token_overlap(lbl_norm, s)
                if sc > best_score_jd:
                    best_score_jd = sc
                    best_snippet_jd = s
            if best_score_jd >= 0.25:
                answers[lbl] = best_snippet_jd.strip()[:200]
                continue

            # If still nothing, ask LLM (optional)
            if _LLM_AVAILABLE:
                try:
                    prompt = f"""You are filling a job application question for a candidate.
Candidate resume text:
{resume_text[:3000]}

Question (label): {lbl_norm}
Give a concise (one-liner) answer as the candidate would. If you cannot infer, answer with an empty string.
Return only the answer text."""
                    llm_resp = await call_gpt_model(prompt)
                    # take up to 300 chars
                    if isinstance(llm_resp, str) and llm_resp.strip():
                        answers[lbl] = llm_resp.strip()[:300]
                        continue
                except Exception as e:
                    logger.debug(f"LLM fallback failed for label '{lbl}': {e}")

            # Final absolute fallback (short generic text)
            if re.search(r'cover|why do you want', lbl_norm, re.I):
                answers[lbl] = "I'm excited about this opportunity and confident my experience aligns with the role."
            else:
                answers[lbl] = ""

        return answers

    except Exception as e:
        logger.error(f"generate_gist_for_labels error: {e}")
        return {lbl: "" for lbl in labels}


