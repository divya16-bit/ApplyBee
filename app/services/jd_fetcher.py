# app/services/jd_fetcher.py
import logging
import re
import urllib.parse
from time import sleep
from typing import Optional, Tuple, Dict, List

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_RELEVANT_CHARS = 8000
FETCHER_VERSION = "v1.5-greenhouse-cleanup"

# Legacy keywords kept for potential future use; classification now uses HEADER_PATTERNS
SECTION_KEYS = {
    "responsibilities": [
        "responsibilit", "what you will do", "what you'll do", "what you’ll do",
        "you will", "day to day", "role"
    ],
    "skills": [
        "requirement", "qualification", "what you bring", "skills",
        "experience", "what we're looking for", "what we’re looking for"
    ],
    "bonus_skills": [
        "bonus skills", "nice to have", "preferred", "bonus", "good to have", "plus"
    ],
}

# Stricter header patterns with word boundaries and normalization for ’ vs '
HEADER_PATTERNS = {
    "responsibilities": [
        re.compile(r"\b(responsibilit(y|ies)|what\s+(you|you['’]ll)\s+do|day[-\s]?to[-\s]?day)\b", re.I),
    ],
    "skills": [
        re.compile(r"\b(requirements?|qualifications?|what\s+you\s+bring|skills|what\s+we['’]re\s+looking\s+for|what\s+we\s+are\s+looking\s+for)\b", re.I),
        re.compile(r"\b(you\s+will\s+thrive|ideal\s+candidate|who\s+you\s+are)\b", re.I),
    ],
    "bonus_skills": [
        re.compile(r"\b(nice\s+to\s+have|preferred|good\s+to\s+have|bonus|plus)\b", re.I),
    ],
}

BONUS_FLAG_RE = re.compile(r"\b(nice to have|preferred|bonus|plus)\b", re.I)

# Noise filter to drop EEO, social links, notices, etc.
NOISE_RE = re.compile(
    r"(equal opportunity|affirmative action|\beeo\b|disabilit|veteran|"
    r"notice to prospective|we never ask for payment|credit check|background check|"
    r"e-?verify|pay transparency|"
    r"linkedin\s*\||instagram|life@|blog\s*\||\bx\s*\|)",
    re.I,
)


def is_allowed_job_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme not in {"http", "https"}:
            return False
        host = (p.hostname or "").lower()
        return host.endswith(".greenhouse.io") or host in {"greenhouse.io", "boards.greenhouse.io", "grnh.se"}
    except Exception:
        return False


def parse_greenhouse_path(url: str) -> Tuple[Optional[str], Optional[str]]:
    p = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(p.query)
    gh_jid = (q.get("gh_jid") or [None])[0]
    parts = [x for x in p.path.strip("/").split("/") if x]
    if len(parts) >= 3 and parts[1] in {"job", "jobs"}:
        return parts[0], parts[2]
    if gh_jid and len(parts) >= 1:
        return parts[0], gh_jid
    return None, None


def fetch_from_greenhouse_api(board_token: str, job_id: str, timeout: int = 20) -> Optional[str]:
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?content=true"
    try:
        r = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        html = data.get("content")
        if not html and isinstance(data.get("job_post"), dict):
            html = data["job_post"].get("content")
        return html
    except Exception as e:
        logger.warning("Greenhouse API fetch failed (%s): %s", api_url, e)
        return None


def html_to_text_preserve_lists(html: str, include_divs: bool = False) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "aside", "nav"]):
        tag.decompose()
    tags = ["h1", "h2", "h3", "h4", "p", "li", "blockquote"]
    if include_divs:
        tags.append("div")
    lines = []
    for el in soup.find_all(tags):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        if el.name == "li":
            lines.append(f"- {txt}")
        else:
            lines.append(txt)
    text = "\n".join(lines)
    text = re.sub(r"[•·▪–—➤▶■□►]", "-", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def classify_header(text: str) -> Optional[str]:
    t = " ".join(text.strip().lower().replace("’", "'").split())
    for sec, pats in HEADER_PATTERNS.items():
        if any(p.search(t) for p in pats):
            return sec
    return None


def _find_following_list(header):
    # If header is inside a <p> or <div> (common on GH), step up
    node = header
    if header.name in ("strong", "b") and header.parent and header.parent.name in ("p", "div"):
        node = header.parent

    # Walk a few next siblings, stop at next header-like block
    for idx, sib in enumerate(node.next_siblings):
        name = getattr(sib, "name", None)
        if name in ("ul", "ol"):
            return sib
        # Stop if we hit another header or a paragraph/div that contains a bold/strong title
        if name in ("h1", "h2", "h3", "h4") or (name in ("p", "div") and getattr(sib, "find", lambda *_: None)(["strong", "b"])):
            break
        if idx > 6:  # don't look too far
            break
    return None


def extract_sections_from_html(html: str) -> Dict[str, List[str]]:
    out = {"responsibilities": [], "skills": [], "bonus_skills": []}
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "aside", "nav"]):
        tag.decompose()

    # Only header-like tags; avoid <p> to reduce false positives
    header_candidates = soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"])

    seen_lists = set()  # avoid assigning same UL/OL twice

    for h in header_candidates:
        header_text = h.get_text(" ", strip=True)
        if not header_text:
            continue
        sec = classify_header(header_text)
        if not sec:
            continue

        list_node = _find_following_list(h)
        if not list_node:
            continue
        if id(list_node) in seen_lists:
            continue
        seen_lists.add(id(list_node))

        for li in list_node.find_all("li", recursive=True):
            txt = li.get_text(" ", strip=True)
            if not txt or NOISE_RE.search(txt):
                continue
            if BONUS_FLAG_RE.search(txt):
                out["bonus_skills"].append(txt)
            else:
                out[sec].append(txt)




    # ✅ NEW: Fallback - if skills section is empty, scan ALL lists for skill-like content
    if not out["skills"]:
        logger.warning("No skills found via headers, attempting fallback extraction")
        all_lists = soup.find_all(["ul", "ol"])
        for ul in all_lists:
            if id(ul) in seen_lists:
                continue
            for li in ul.find_all("li", recursive=False):
                txt = li.get_text(" ", strip=True)
                if not txt or NOISE_RE.search(txt):
                    continue
                # Heuristic: if contains skill-related keywords, add to skills
                if re.search(r"\b(experience|years|knowledge|proficient|familiar|strong|background|degree|bachelor|master)\b", txt, re.I):
                    if txt not in out["skills"]:
                        out["skills"].append(txt)


    # Global scan for bonus-like bullets anywhere (keep, but filter noise)
    for li in soup.find_all("li"):
        txt = li.get_text(" ", strip=True)
        if txt and not NOISE_RE.search(txt) and BONUS_FLAG_RE.search(txt):
            if txt not in out["bonus_skills"]:
                out["bonus_skills"].append(txt)

    # Dedup + limit
    for k in out:
        seen, dedup = set(), []
        for item in out[k]:
            item = re.sub(r"\s+", " ", item).strip()
            low = item.lower()
            if item and low not in seen:
                seen.add(low)
                dedup.append(item[:300])
        out[k] = dedup[:120]

    # ✅ NEW: Log what was extracted
    logger.info(f"Extracted sections - R:{len(out['responsibilities'])}, S:{len(out['skills'])}, B:{len(out['bonus_skills'])}")    
    
    return out


def parse_sections_from_text(text: str) -> Dict[str, List[str]]:
    # Heuristic text-only parser (fallback if HTML structure fails)
    out = {"responsibilities": [], "skills": [], "bonus_skills": []}
    txt = text.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[•·▪–—➤▶■□►]", "-", txt)
    lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]
    current = None
    for ln in lines:
        if NOISE_RE.search(ln):
            continue
        if len(ln) < 120 and (":" not in ln) and (ln.isupper() or ln.istitle()):
            sec = classify_header(ln)
            if sec:
                current = sec
                continue
        is_bullet = ln.startswith(("-", "*"))
        content = ln.lstrip("-* ").strip() if is_bullet else ln
        if not content or NOISE_RE.search(content):
            continue
        if BONUS_FLAG_RE.search(content):
            out["bonus_skills"].append(content)
            continue
        if current == "responsibilities":
            out["responsibilities"].append(content)
        elif current == "bonus_skills":
            out["bonus_skills"].append(content)
        else:
            out["skills"].append(content)

    # Fallback heuristics
    if not out["responsibilities"]:
        out["responsibilities"] = [
            ln.lstrip("- ").strip()
            for ln in lines
            if re.search(r"\b(you will|build|design|own|lead|implement|deliver)\b", ln, re.I)
            and not NOISE_RE.search(ln)
        ][:60]
    if not out["skills"]:
        out["skills"] = [
            ln.lstrip("- ").strip()
            for ln in lines
            if re.search(r"\b(require|must|experience|proficien|knowledge|background)\b", ln, re.I)
            and not BONUS_FLAG_RE.search(ln)
            and not NOISE_RE.search(ln)
        ][:120]

    # Dedup + limit
    for k in out:
        seen, dedup = set(), []
        for item in out[k]:
            item = re.sub(r"\s+", " ", item).strip()
            low = item.lower()
            if item and low not in seen:
                seen.add(low)
                dedup.append(item[:300])
        out[k] = dedup[:120]
    return out


def extract_main_container_text(html: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "aside", "nav"]):
        tag.decompose()
    candidates = [
        ("#content", soup.select_one("#content")),
        ("div.opening", soup.select_one("div.opening")),
        ("div.opening-body", soup.select_one("div.opening-body")),
        ("div.job__description", soup.select_one("div.job__description")),
        ("section#content", soup.select_one("section#content")),
        ("section.content", soup.select_one("section.content")),
        ("div.content", soup.select_one("div.content")),
        ("div.section.page", soup.select_one("div.section.page")),
        ("div.section-wrapper.page", soup.select_one("div.section-wrapper.page")),
        ("[data-automation-id='jobDescription']", soup.select_one("[data-automation-id='jobDescription']")),
    ]
    best_txt, best_html, best_sel, best_len = None, None, None, 0
    for sel, node in candidates:
        if not node:
            continue
        node_html = str(node)
        txt = html_to_text_preserve_lists(node_html)
        if txt and len(txt) > best_len and len(txt) > 200:
            best_txt, best_html, best_sel, best_len = txt, node_html, sel, len(txt)
    if best_txt:
        return best_txt, best_html, best_sel
    # Fallback: largest div
    best_txt, best_html, best_len = None, None, 0
    for div in soup.find_all("div"):
        node_html = str(div)
        txt = html_to_text_preserve_lists(node_html)
        if txt and len(txt) > best_len and len(txt) > 200:
            best_txt, best_html, best_len = txt, node_html, len(txt)
    if best_txt:
        return best_txt, best_html, "fallback-largest-div"
    return None, None, None


def _relevant_snippet_from_sections(sections: Dict[str, List[str]]) -> str:
    lines = sections.get("responsibilities", []) + sections.get("skills", []) + sections.get("bonus_skills", [])
    lines = [ln for ln in lines if not NOISE_RE.search(ln)]
    text = "\n".join(lines).strip()
    if len(text) > MAX_RELEVANT_CHARS:
        text = text[:MAX_RELEVANT_CHARS]
    return text


def fetch_job_description(url: str, retries: int = 3, delay: int = 2):
    if "127.0.0.1:8000/fetch_jd" in url:
        return {
            "url": url,
            "job_description_full": "Error occurred.",
            "job_description_relevant": "",
            "jd_sections": {},
            "debug": f"{FETCHER_VERSION} recursion-guard",
        }
    if not is_allowed_job_url(url):
        return {
            "url": url,
            "job_description_full": "",
            "job_description_relevant": "",
            "jd_sections": {},
            "debug": f"{FETCHER_VERSION} url-not-allowed",
        }

    headers = DEFAULT_HEADERS.copy()
    board_token, job_id = parse_greenhouse_path(url)

    resolved_url = url
    resolved_html = None
    if not (board_token and job_id):
        try:
            r0 = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            resolved_url = r0.url
            resolved_html = r0.text
        except Exception as e:
            logger.warning("Failed to resolve redirects for %s: %s", url, e)
        board_token, job_id = parse_greenhouse_path(resolved_url)

    # API path
    if board_token and job_id:
        api_html = fetch_from_greenhouse_api(board_token, job_id)
        if api_html is not None:
            api_text = html_to_text_preserve_lists(api_html, include_divs=True)
            if not api_text or len(api_text) < 80:
                soup = BeautifulSoup(api_html, "html.parser")
                for tag in soup(["script", "style", "noscript", "header", "footer", "form", "aside", "nav"]):
                    tag.decompose()
                api_text2 = soup.get_text("\n", strip=True)
                api_text2 = re.sub(r"[•·▪–—➤▶■□►]", "-", api_text2)
                api_text2 = re.sub(r"\n{3,}", "\n\n", api_text2).strip()
                if len(api_text2) > len(api_text):
                    api_text = api_text2

            sections = extract_sections_from_html(api_html)
            if not any(sections.values()):
                sections = parse_sections_from_text(api_text)
            rel = _relevant_snippet_from_sections(sections)

            return {
                "url": resolved_url,
                "job_description_full": api_text,      # TEXT ONLY
                "job_description_relevant": rel,
                "jd_sections": sections,
                "job_description_html": api_html,       # optional
                "debug": f"{FETCHER_VERSION} source=api board={board_token} job={job_id} api_html_len={len(api_html)} text_len={len(api_text)} secs={{r:{len(sections['responsibilities'])},s:{len(sections['skills'])},b:{len(sections['bonus_skills'])}}}",
            }

    # HTML fallback
    for attempt in range(1, retries + 1):
        try:
            if resolved_html is None:
                resp = requests.get(resolved_url, headers=headers, timeout=30)
                resp.raise_for_status()
                html = resp.text
            else:
                html = resolved_html
                resolved_html = None

            full_text, container_html, selector_used = extract_main_container_text(html)
            if not full_text:
                if attempt < retries:
                    sleep(delay)
                    continue
                return {
                    "url": resolved_url,
                    "job_description_full": "Job description not found.",
                    "job_description_relevant": "",
                    "jd_sections": {},
                    "debug": f"{FETCHER_VERSION} no-selector",
                }

            sections = extract_sections_from_html(container_html or html)
            if not any(sections.values()):
                sections = parse_sections_from_text(full_text)
            rel = _relevant_snippet_from_sections(sections)

            return {
                "url": resolved_url,
                "job_description_full": full_text,       # TEXT ONLY
                "job_description_relevant": rel,
                "jd_sections": sections,
                "job_description_html": container_html,  # optional
                "debug": f"{FETCHER_VERSION} source=html selector={selector_used} secs={{r:{len(sections['responsibilities'])},s:{len(sections['skills'])},b:{len(sections['bonus_skills'])}}}",
            }

        except requests.exceptions.RequestException as e:
            logger.warning("Fetch attempt failed: %s", e)
            if attempt < retries:
                sleep(delay)
            else:
                return {
                    "url": resolved_url,
                    "job_description_full": "Error occurred.",
                    "job_description_relevant": "",
                    "jd_sections": {},
                    "debug": f"{FETCHER_VERSION} error={e}",
                }