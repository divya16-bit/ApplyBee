# services/score_engine.py
from typing import Dict, Any, List
from app.services import matcher
from app.services.skill_normalizer import normalize_skills
from loguru import logger
from app.services.llm_client import call_gpt_model

async def compute_resume_score(parsed_resume: Dict[str, Any],
                               jd_sections: Dict[str, List[str]],
                               jd_full_text: str = "") -> Dict[str, Any]:
    """
    Compute scores using your existing matcher.calculate_match_score_text under the hood.
    parsed_resume: dict, expected to contain 'raw_text' key (resume text)
    jd_sections: { responsibilities: [...], skills: [...], bonus_skills: [...] }
    jd_full_text: raw JD string (optional)
    Returns a dict with keys matching ScoreResponse fields.
    """
    # Ensure resume text available
    resume_text_raw = parsed_resume.get("raw_text", "")
    if not resume_text_raw:
        # fallback to empty string - matcher will return 0 scores
        resume_text_raw = ""

    # Call the heavy matcher in a thread context via calculate_match_score_text (it's synchronous)
    # matcher.calculate_match_score_text expects: resume_text_raw, jd_sections, jd_skills_extracted list, debug, jd_full_text
    # We will extract jd_skills_extracted from jd_sections['skills']
    jd_skills_extracted = jd_sections.get("skills", []) if isinstance(jd_sections, dict) else []

    # call matcher function
    try:
        result = matcher.calculate_match_score_text(
            resume_text_raw=resume_text_raw,
            jd_sections=jd_sections,
            jd_skills_extracted=jd_skills_extracted,
            jd_full_text=jd_full_text,
            debug=False
        )
    except Exception as e:
        logger.error(f"matcher.calculate_match_score_text failed: {e}")
        raise

    # Format the returned result into the ScoreResponse-compatible dict
    out = {
        "score": float(result.get("ats_score", 0.0)),
        "ats_score": float(result.get("ats_score", 0.0)),
        "responsibility_score": float(result.get("responsibility_score", 0.0)),
        "skills_score": float(result.get("skills_score", 0.0)),
        "common_skills": result.get("common_skills", []),
        "missing_skills": result.get("missing_skills", []),
        "summary": result.get("summary", ""),
        "years_experience_resume": result.get("years_experience_resume"),
        "years_experience_jd": result.get("years_experience_jd"),
        "yoe_score": result.get("yoe_score", 0.0),
        # Optionally include normalized insights
        "normalized_overlap": result.get("normalized_overlap", []),
        "normalized_missing": result.get("normalized_missing", []),
        "direct_skill_score": result.get("direct_skill_score", 0.0),
        "contextual_skill_score": result.get("contextual_skill_score", 0.0),
        "all_matched_skills": result.get("all_matched_skills", []),
    }

    # Optional: get short natural-language explanation using LLM
    try:
        explanation_prompt = f"""Summarize why this resume scored {out['score']} for the given job.
Resume summary: {parsed_resume.get('raw_text', '')[:1500]}
JD summary: {jd_full_text[:1500]}
Return a short (2-3 sentence) actionable explanation listing top matched skills and top missing skills.
"""
        explanation = await call_gpt_model(explanation_prompt)
        out["explanation"] = explanation
    except Exception as e:
        logger.debug(f"LLM explanation generation failed: {e}")
        out["explanation"] = out.get("summary", "")

    return out
