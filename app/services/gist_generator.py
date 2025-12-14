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
# Helper functions
# -------------------------
def trim_text(text: str, max_chars: int = 4000) -> str:
    """Safely trim long text to avoid model overload."""
    if not text:
        return ""
    text = str(text).strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text

def safe_parse_gist_output(response_text: str) -> Dict[str, str]:
    """
    Safely parse LLM output; handles non-JSON text by attempting fallback parsing.
    Returns dict of question -> answer mappings.
    """
    if not response_text:
        return {}
    
    try:
        # Try direct JSON parse first
        return json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning("⚠️ LLM returned non-JSON output — attempting fallback parsing")
        
        # Try to extract JSON from markdown code blocks
        json_str = response_text.strip()
        if json_str.startswith("```"):
            json_str = re.sub(r'```json\s*', '', json_str)
            json_str = re.sub(r'```\s*', '', json_str)
            json_str = json_str.strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON object in response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Fallback: parse line-by-line for key-value pairs
        gist_dict = {}
        for line in response_text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Look for "key": "value" or key: value patterns
            if ':' in line:
                # Try JSON-like format first
                if '"' in line or "'" in line:
                    try:
                        # Try to parse as JSON line
                        if line.startswith('"') or line.startswith("'"):
                            # Might be a JSON object line
                            pass
                    except:
                        pass
                
                # Simple key-value parsing
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip().strip('"').strip("'").strip(',')
                    value = parts[1].strip().strip(',').strip('"').strip("'")
                    if key and value and value.lower() != 'null':
                        gist_dict[key] = value
        
        if gist_dict:
            logger.info(f"✅ Fallback parsing extracted {len(gist_dict)} answers")
            return gist_dict
        
        # Last resort: return empty dict
        logger.warning("⚠️ Could not parse LLM output, returning empty dict")
        return {}

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
    """Detect if question expects yes/no answer"""
    lbl = (label or "").lower()
    # More specific patterns for yes/no questions
    yes_no_patterns = [
        "do you", "have you", "are you", "would you", "can you",
        "yes/no", "yes or no", "select yes or no",
        "do you have experience", "have you worked with",
        "are you authorized", "are you eligible", "are you legally",
        "will you", "would you be willing", "are you available"
    ]
    # Exclude questions that are clearly NOT yes/no (like salary, why, what, how)
    if any(x in lbl for x in ["what", "why", "how", "salary", "expectation", "tell us", "describe", "explain"]):
        return False
    return any(x in lbl for x in yes_no_patterns)

def is_long_form_question(label: str) -> bool:
    """Detect if question expects a paragraph/long answer"""
    lbl = (label or "").lower()
    long_form_patterns = [
        "why", "what are", "tell us", "describe", "explain", "share",
        "cover letter", "motivation", "why do you want", "why are you interested",
        "what makes you", "how do you", "what experience", "what skills",
        "salary expectation", "compensation expectation", "tell me about",
        "additional information", "anything else", "other comments"
    ]
    return any(x in lbl for x in long_form_patterns)

def is_behavioral_question(label: str) -> bool:
    """Detect if question is a behavioral/STAR method question"""
    lbl = (label or "").lower()
    behavioral_patterns = [
        # Direct behavioral question starters
        "describe a time", "describe when", "describe a situation", "describe an example",
        "tell me about a time", "tell us about a time", "tell me when", "tell us when",
        "tell me about when", "tell us about when",
        "give an example", "give me an example", "provide an example",
        "share an example", "share a time", "share an experience",
        "think of a time", "think about a time", "recall a time", "recall when",
        "walk me through", "walk us through",
        "can you think of", "can you describe", "can you tell me",
        "what's a time", "what was a time", "what is a time",
        # Situation-based patterns
        "situation where", "situation in which", "scenario where",
        "example of", "example where", "instance where",
        "time when you", "time where you", "time that you",
        "experience where", "experience when", "experience that",
        # Common behavioral question topics
        "challenge", "difficult situation", "difficult time", "difficult decision",
        "conflict", "disagreement", "mistake", "failure", "error",
        "proud", "accomplishment", "achievement", "success",
        "led", "leadership", "led a team", "leading",
        "contributed", "contribution", "collaborated", "collaboration",
        "problem you solved", "problem solving", "solved a problem",
        "worked under pressure", "pressure", "deadline",
        "handled", "dealt with", "managed", "overcame"
    ]
    return any(x in lbl for x in behavioral_patterns)

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
        # Collect questions that need LLM (after simple extraction)
        llm_questions = []  # List of (label, question_type) tuples

        # First pass: Handle all simple/extractable questions
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

            # Salary / compensation expectations - collect for batch LLM (better answers)
            if re.search(r'salary|compensation|pay|expectation.*role|expected.*salary|salary.*expectation', lbl_norm, re.I):
                if _LLM_AVAILABLE:
                    llm_questions.append((lbl, "salary"))  # Special handling for salary
                else:
                    # Fallback professional answer if LLM not available
                    answers[lbl] = "I'm open to discussing compensation that aligns with market standards and reflects my experience and the value I bring to the role."
                continue
            
            # Notice period / relocation
            if re.search(r'notice period', lbl_norm, re.I):
                answers[lbl] = "30 days"
                continue
            if re.search(r'relocation', lbl_norm, re.I):
                answers[lbl] = "Yes"
                continue

            # Yes/No questions - keep simple (check AFTER salary to avoid conflicts)
            if is_yes_no_question(lbl_norm):
                tech = detect_technology_from_label(lbl_norm)
                if tech:
                    answers[lbl] = "Yes" if tech in resume_text.lower() else "No"
                    continue
                # For general yes/no questions, check if resume has relevant experience
                # Look for keywords in the question and check if they appear in resume
                question_keywords = set(re.findall(r'\w+', lbl_norm.lower()))
                question_keywords.discard('you')
                question_keywords.discard('do')
                question_keywords.discard('have')
                question_keywords.discard('are')
                resume_lower = resume_text.lower()
                # If any significant keywords from question appear in resume, answer Yes
                if any(len(kw) > 3 and kw in resume_lower for kw in question_keywords):
                    answers[lbl] = "Yes"
                else:
                    answers[lbl] = "No"
                continue

            # For behavioral questions, skip token overlap and go straight to LLM for proper STAR answers
            # For other questions, try to match from resume by token overlap with label
            if not is_behavioral_question(lbl_norm):
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

            # If still nothing, collect for batch LLM processing (don't call individually)
            if _LLM_AVAILABLE:
                # Determine question type for batch processing
                if is_behavioral_question(lbl_norm):
                    llm_questions.append((lbl, "behavioral"))
                elif is_long_form_question(lbl_norm):
                    llm_questions.append((lbl, "long_form"))
                else:
                    llm_questions.append((lbl, "short"))
            else:
                # Final absolute fallback (short generic text) if LLM not available
                if re.search(r'cover|why do you want', lbl_norm, re.I):
                    answers[lbl] = "I'm excited about this opportunity and confident my experience aligns with the role."
                else:
                    answers[lbl] = ""

        # ============================================
        # BATCH LLM PROCESSING: ONE call for all remaining questions
        # ============================================
        if _LLM_AVAILABLE and llm_questions:
            try:
                logger.info(f"📤 Batch LLM call for {len(llm_questions)} questions")
                
                # Group questions by type for better prompt organization
                behavioral_questions = [lbl for lbl, qtype in llm_questions if qtype == "behavioral"]
                salary_questions = [lbl for lbl, qtype in llm_questions if qtype == "salary"]
                long_form_questions = [lbl for lbl, qtype in llm_questions if qtype == "long_form"]
                short_questions = [lbl for lbl, qtype in llm_questions if qtype == "short"]
                
                # Trim inputs to avoid token limits
                trimmed_resume = trim_text(resume_text, 3000)
                trimmed_jd = trim_text(jd_text, 2000)
                
                # Build comprehensive batch prompt (similar to previous working version)
                batch_prompt = f"""You are filling out a job application form on behalf of the candidate.

Answer these questions as if you ARE the candidate (first person).
Keep answers SHORT and professional (1-2 sentences for short questions, 2-4 for long-form, 3-5 for behavioral).

Resume Summary:
{trimmed_resume}

Job Description (for context):
{trimmed_jd}

IMPORTANT: Answer ALL questions below. Return your answers in JSON format where the key is the EXACT question text (as shown) and value is the answer string.

QUESTIONS TO ANSWER:"""
                
                # Add behavioral questions with STAR instructions
                if behavioral_questions:
                    batch_prompt += "\n\n=== BEHAVIORAL QUESTIONS (use STAR method - Situation, Task, Action, Result, 3-5 sentences each) ==="
                    for i, q in enumerate(behavioral_questions, 1):
                        batch_prompt += f"\n{i}. {q}"
                
                # Add salary questions
                if salary_questions:
                    batch_prompt += "\n\n=== SALARY QUESTIONS (diplomatic, 1-2 sentences, open to negotiation) ==="
                    for i, q in enumerate(salary_questions, 1):
                        batch_prompt += f"\n{i}. {q}"
                
                # Add long-form questions
                if long_form_questions:
                    batch_prompt += "\n\n=== LONG-FORM QUESTIONS (2-4 sentences each, thoughtful and professional) ==="
                    for i, q in enumerate(long_form_questions, 1):
                        batch_prompt += f"\n{i}. {q}"
                
                # Add short questions
                if short_questions:
                    batch_prompt += "\n\n=== SHORT QUESTIONS (1-2 sentences each, concise) ==="
                    for i, q in enumerate(short_questions, 1):
                        batch_prompt += f"\n{i}. {q}"
                
                batch_prompt += f"""

Return ONLY valid JSON: {{"question": "answer", ...}}
Use the EXACT question text as shown above as the JSON key.

Example format:
{json.dumps({q: "Sample answer" for q in (behavioral_questions[:1] + salary_questions[:1] + long_form_questions[:1] + short_questions[:1]) if q}, indent=2)}
"""

                llm_response = await call_gpt_model(batch_prompt)
                
                # Use safe parsing (handles non-JSON responses gracefully)
                batch_answers = safe_parse_gist_output(llm_response)
                
                # Map answers back to labels (handle slight variations in question text)
                if batch_answers:
                    for lbl, qtype in llm_questions:
                        answer = None
                        # Try exact match first
                        if lbl in batch_answers:
                            answer = batch_answers[lbl]
                        else:
                            # Try case-insensitive match
                            answer = next((batch_answers[k] for k in batch_answers.keys() if k.lower() == lbl.lower()), None)
                            if not answer:
                                # Try partial match (question might be slightly different)
                                answer = next((batch_answers[k] for k in batch_answers.keys() 
                                             if lbl.lower() in k.lower() or k.lower() in lbl.lower() or 
                                             abs(len(k) - len(lbl)) <= 5), None)
                        
                        if answer:
                            max_chars = 500 if qtype in ["behavioral", "long_form"] else 200
                            answers[lbl] = str(answer).strip()[:max_chars]
                        else:
                            # Fallback if question not found in response
                            if qtype == "behavioral":
                                answers[lbl] = "Based on my experience, I have led cross-functional initiatives that delivered measurable results. I focus on clear communication, stakeholder alignment, and iterative delivery to ensure success."
                            elif qtype == "salary":
                                answers[lbl] = "I'm open to discussing compensation that aligns with market standards and reflects my experience and the value I bring to the role."
                            elif re.search(r'cover|why do you want', lbl.lower()):
                                answers[lbl] = "I'm excited about this opportunity and confident my experience aligns with the role."
                            else:
                                answers[lbl] = ""
                    
                    logger.info(f"✅ Batch LLM processed {len([a for a in answers.values() if a])} answers successfully")
                else:
                    logger.warning("⚠️ No answers extracted from LLM response")
                    # Fallback for all questions if parsing returned empty
                    for lbl, qtype in llm_questions:
                        if qtype == "behavioral":
                            answers[lbl] = "Based on my experience, I have led cross-functional initiatives that delivered measurable results."
                        elif qtype == "salary":
                            answers[lbl] = "I'm open to discussing compensation that aligns with market standards and reflects my experience and the value I bring to the role."
                        elif re.search(r'cover|why do you want', lbl.lower()):
                            answers[lbl] = "I'm excited about this opportunity and confident my experience aligns with the role."
                        else:
                            answers[lbl] = ""
            except Exception as parse_error:
                logger.warning(f"Failed to process LLM response: {parse_error}")
                logger.debug(f"Response was: {llm_response[:1000] if 'llm_response' in locals() else 'N/A'}")
                # Fallback for all questions if exception occurred
                for lbl, qtype in llm_questions:
                    if qtype == "behavioral":
                        answers[lbl] = "Based on my experience, I have led cross-functional initiatives that delivered measurable results."
                    elif qtype == "salary":
                        answers[lbl] = "I'm open to discussing compensation that aligns with market standards and reflects my experience and the value I bring to the role."
                    elif re.search(r'cover|why do you want', lbl.lower()):
                        answers[lbl] = "I'm excited about this opportunity and confident my experience aligns with the role."
                    else:
                        answers[lbl] = ""
            except Exception as e:
                logger.error(f"Batch LLM processing failed: {e}")
                # Fallback for all LLM questions
                for lbl, qtype in llm_questions:
                    if qtype == "behavioral":
                        answers[lbl] = "Based on my experience, I have led cross-functional initiatives that delivered measurable results."
                    elif qtype == "salary":
                        answers[lbl] = "I'm open to discussing compensation that aligns with market standards and reflects my experience and the value I bring to the role."
                    elif re.search(r'cover|why do you want', lbl.lower()):
                        answers[lbl] = "I'm excited about this opportunity and confident my experience aligns with the role."
                    else:
                        answers[lbl] = ""

        return answers

    except Exception as e:
        logger.error(f"generate_gist_for_labels error: {e}")
        return {lbl: "" for lbl in labels}


