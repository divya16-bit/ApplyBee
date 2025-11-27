
import json
from loguru import logger
from app.services.llm_client import call_gpt_model


# ✅ Helper: safely trim long text to avoid model overload
def trim_text(text: str, max_chars: int = 4000) -> str:
    """
    Trims text safely if it exceeds token limits (~4k chars).
    """
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text


# ✅ Helper: safely parse Gemma/LLM output (handles non-JSON text)
def safe_parse_gist_output(response_text: str):
    """
    Safely parse Gemma's output; fallback to key-value dict if not valid JSON.
    """
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        logger.warning("⚠️ LLM returned non-JSON output — attempting fallback parsing")

        gist_dict = {}
        for line in response_text.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                # 🔥 Clean up quotes and commas 🔥
                key = key.strip().strip('"').strip("'")
                value = value.strip().strip(',').strip('"').strip("'")
                if value.lower() != 'null':  # Skip null values
                    gist_dict[key] = value
                #gist_dict[key.strip()] = value.strip()
        if gist_dict:
            return gist_dict

        # last resort
        return {"summary": response_text.strip() or "No structured output."}



# Expanded fallback answers — covers LinkedIn, GitHub, location, etc.
FALLBACK_GISTS = {
    "work authorization": "Authorized to work in India",
    "notice period": "Immediate",
    "availability": "Immediate",
    "salary": "As per company standards",
    "expected salary": "As per industry standards",
    "visa": "Not applicable (Indian Citizen)",
    "relocation": "Yes, open to relocation",
    "employment type": "Full-time",
    "why do you want to work": "Excited about the role and the company’s impact in technology.",
    "cover letter": (
        "I'm passionate about technology and eager to contribute to your mission. "
        "My background in software engineering and automation aligns well with this opportunity."
    ),
    # 👇 newly added useful fallbacks
    "location": "India",
    "city": "",
    "state": "",
    "country": "India",
}


async def generate_gist(parsed_resume: dict, jd_data: dict, form_fields: list) -> dict:
    """
    Generates short, relevant answers for each form field using:
      1. Parsed resume values (preferred)
      2. LLM-generated gist answers
      3. Fallback defaults (if both missing)
    """
    gist_answers = {}

    try:
        logger.info("🧠 Generating gist answers from resume + JD + detected form fields...")

        # Normalize field list
        normalized_questions = []
        for f in form_fields:
            if isinstance(f, dict):
                q = f.get("aria_label") or f.get("label_text") or f.get("placeholder") or f.get("name")
                if q:
                    normalized_questions.append(q)
            elif isinstance(f, str):
                normalized_questions.append(f)
        form_fields = normalized_questions

        # --- STEP 1: Try direct matches from resume ---
        resume_map = {
            "First Name": parsed_resume.get("first_name"),
            "Last Name": parsed_resume.get("last_name"),
            "Email": parsed_resume.get("email"),
            "Phone": parsed_resume.get("phone"),
            "LinkedIn Profile": parsed_resume.get("linkedin"),
            "Website / Github Profile": parsed_resume.get("github") or parsed_resume.get("portfolio"),
            "linkedin": parsed_resume.get("linkedin"),
            "github": parsed_resume.get("github"),
            "portfolio": parsed_resume.get("portfolio"),
            "website": parsed_resume.get("website") or parsed_resume.get("github"),
            "location": parsed_resume.get("location") or "India",
            "email": parsed_resume.get("email"),
            "phone": parsed_resume.get("phone"),
            "name": f"{parsed_resume.get('first_name', '')} {parsed_resume.get('last_name', '')}".strip(),
        }

        # Add direct field matches
        for q in form_fields:
            # Exact match first
            if q in resume_map and resume_map[q]:
                gist_answers[q] = resume_map[q]
                continue
            
            # Case-insensitive partial match
            q_lower = q.lower()
            for key, val in resume_map.items():
                if val and key.lower() in q_lower:
                    gist_answers[q] = val
                    break

        logger.debug(f"📄 Prefilled from resume: {list(gist_answers.keys())}")

        # --- STEP 2: Handle experience/skill-based questions ---
        # Extract years of experience from resume
        import re
        resume_text = parsed_resume.get("raw_text", "")
        
        # Try to find years of experience
        years_match = re.search(r'(\d+)[-+]?\s*years?\s+(?:of\s+)?experience', resume_text.lower())
        total_years = years_match.group(1) if years_match else None
        
        # Calculate from work history dates if available
        if not total_years:
            dates = re.findall(r'20\d{2}', resume_text)
            if len(dates) >= 2:
                total_years = str(int(max(dates)) - int(min(dates)))
        
        if not total_years:
            # Default based on Senior title
            if 'senior' in resume_text.lower():
                total_years = "5-7"
            else:
                total_years = "3-5"

        # Add experience-based answers
        for q in form_fields:
            if q in gist_answers:
                continue
                
            q_lower = q.lower()
            
            # Years of experience questions
            if "total" in q_lower and "years" in q_lower and "experience" in q_lower:
                gist_answers[q] = f"{total_years} years" if total_years else "5-7 years"
            
            # Technology-specific experience (React, Python, etc.)
            elif "experience in" in q_lower or "experience with" in q_lower:
                # Check if technology is in resume
                tech_keywords = ["react", "python", "javascript", "node", "vue", "angular"]
                for tech in tech_keywords:
                    if tech in q_lower:
                        if tech in resume_text.lower():
                            gist_answers[q] = "Yes"
                        else:
                            gist_answers[q] = "No"
                        break
            
            # Unit testing / QA questions
            elif "test" in q_lower and "unit" in q_lower:
                if "test" in resume_text.lower():
                    gist_answers[q] = "Yes"
                else:
                    gist_answers[q] = "Yes"  # Default to Yes for senior developers
            
            # AI/Tools questions
            elif "ai" in q_lower and "tool" in q_lower:
                gist_answers[q] = "Yes"
            
            # Relocation questions
            elif "relocat" in q_lower:
                if "bangalore" in q_lower or "bengaluru" in q_lower:
                    current_location = parsed_resume.get("location", "").lower()
                    if "bangalore" in current_location or "bengaluru" in current_location:
                        gist_answers[q] = "Already in Bangalore"
                    else:
                        gist_answers[q] = "Yes"
                else:
                    gist_answers[q] = "Open to discussion"
            
            # Notice period
            elif "notice" in q_lower and "period" in q_lower:
                gist_answers[q] = "30 days"
            
            # Salary expectations
            elif "salary" in q_lower or "compensation" in q_lower:
                gist_answers[q] = "As per company standards"
            
            # Current offers
            elif "current offer" in q_lower or "other offer" in q_lower:
                gist_answers[q] = "No"
            
            # Authorization
            elif "authorization" in q_lower or "authorized" in q_lower:
                gist_answers[q] = "Yes"
            
            # Visa
            elif "visa" in q_lower:
                gist_answers[q] = "Not required (Indian Citizen)"

        logger.debug(f"📊 After heuristics: {list(gist_answers.keys())}")

        # --- STEP 3: LLM-based generation (for remaining fields) ---
        missing_questions = [q for q in form_fields if q not in gist_answers]
        
        if missing_questions:
            logger.info(f"🤖 Asking LLM for {len(missing_questions)} remaining answers...")
            
            # ✅ Trim large inputs before sending to the model
            trimmed_resume = {k: trim_text(str(v)) for k, v in parsed_resume.items()}
            trimmed_jd = {k: trim_text(str(v)) for k, v in jd_data.items()}

            prompt = f"""
You are filling out a job application form on behalf of the candidate.

Candidate: {parsed_resume.get('first_name', '')} {parsed_resume.get('last_name', '')}
Total Experience: {total_years} years

Answer these questions as if you ARE the candidate (first person).
Keep answers SHORT (1-2 sentences max).

Resume Summary:
{trimmed_resume.get('raw_text', '')[:2000]}

Questions:
{json.dumps(missing_questions, indent=2)}

Return ONLY valid JSON: {{"question": "answer", ...}}
"""

            try:
                response_text = await call_gpt_model(prompt)
                ai_output = safe_parse_gist_output(response_text)

                if isinstance(ai_output, dict):
                    for k, v in ai_output.items():
                        if k not in gist_answers and v:
                            gist_answers[k] = v
                            logger.debug(f"  🤖 LLM answered: {k}")
            except Exception as e:
                logger.warning(f"⚠️ LLM gist generation skipped due to: {e}")

        # --- STEP 4: Absolute fallback ---
        if not gist_answers:
            gist_answers = {
                "General Statement": (
                    "I'm excited about this opportunity and confident my experience aligns with the role."
                )
            }

        logger.success(f"🧩 Gist answers ready for {len(gist_answers)} fields.")
        logger.debug(f"📋 Final gist keys: {list(gist_answers.keys())}")
        
        return gist_answers

    except Exception as e:
        logger.error(f"❌ Gist generation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": str(e)}

