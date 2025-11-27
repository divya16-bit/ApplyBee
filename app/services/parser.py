import re
import pdfplumber
import docx
from loguru import logger
 

def parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"
    return text.strip()


def parse_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs]).strip()


def parse_resume(file_path: str) -> dict:
    """
    Unified resume parser → extracts key info + raw text.
    Compatible with .pdf and .docx
    """
    text = ""
    if file_path.lower().endswith(".pdf"):
        text = parse_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        text = parse_docx(file_path)
    else:
        raise ValueError("Unsupported file type: only PDF and DOCX supported")

    logger.info(f"📄 Resume text extracted ({len(text)} chars). Now parsing fields...")

    # --- Extract structured data ---
    name = extract_name(text)
    email = extract_email(text)
    phone = extract_phone(text)
    linkedin = extract_linkedin(text)
    github = extract_github(text)
    portfolio = extract_portfolio(text)
    location = extract_location(text)
    summary = extract_summary_snippet(text)
    skills = extract_skills(text)

    parsed = {
        "first_name": name.split()[0] if name else "",
        "last_name": name.split()[1] if name and len(name.split()) > 1 else "",
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "portfolio": portfolio,
        "location": location,
        "skills": skills,
        "summary": summary,
        "raw_text": text,
    }

    logger.success(f"✅ Resume parsed: {parsed}")
    return parsed


# --- Utility extractors ---

def extract_email(text: str) -> str:
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    match = re.search(r'(\+?\d[\d\s\-\(\)]{8,}\d)', text)
    return match.group(0) if match else ""


def extract_linkedin(text: str) -> str:
    """Extract LinkedIn profile URL."""
    match = re.search(r'(https?://(www\.)?linkedin\.com/in/[^\s,•]+)', text, re.IGNORECASE)
    if match:
        # Clean up common trailing characters
        url = match.group(0).rstrip('.,;)')
        return url
    return ""


def extract_github(text: str) -> str:
    """Extract GitHub profile link."""
    match = re.search(r'(https?://(www\.)?github\.com/[^\s,•]+)', text, re.IGNORECASE)
    if match:
        # Clean up common trailing characters
        url = match.group(0).rstrip('.,;)')
        return url
    return ""


def extract_portfolio(text: str) -> str:
    """Extract personal portfolio or blog URL (excluding LinkedIn/GitHub)."""
    # Look for URLs in the first 500 characters (header area)
    header = text[:500]
    urls = re.findall(r'(https?://[^\s,•]+)', header)
    
    for url in urls:
        # Skip social media and common platforms
        if not re.search(r'(linkedin|github|facebook|twitter|instagram)', url, re.IGNORECASE):
            return url.rstrip('.,;)')
    
    # If nothing in header, search full text
    urls = re.findall(r'(https?://[^\s,•]+)', text)
    for url in urls:
        if not re.search(r'(linkedin|github|facebook|twitter|instagram)', url, re.IGNORECASE):
            return url.rstrip('.,;)')
    
    return ""


def extract_location(text: str) -> str:
    """
    Extract probable location or city.
    Handles multiple formats:
    - "Bengaluru • email@example.com"
    - "Location: Bangalore, Karnataka"
    - "Based in Mumbai"
    """
    # Strategy 1: Look for location keywords
    match = re.search(
        r'(?:location|based in|address|city|residence)[:\s-]*([A-Za-z\s,]+?)(?:\n|•|\||$)',
        text,
        re.IGNORECASE
    )
    if match:
        location = match.group(1).strip()
        # Clean up: take first part if comma-separated
        location = location.split(',')[0].strip()
        if 2 <= len(location) <= 50:  # Reasonable length
            return location
    
    # Strategy 2: Look for city near contact info (first 5 lines)
    lines = [line.strip() for line in text.splitlines()[:5] if line.strip()]
    
    # Extended city list with variations
    cities = {
        # City name: Standardized output
        "bengaluru": "Bengaluru, Karnataka, India",
        "bangalore": "Bengaluru, Karnataka, India",
        "mumbai": "Mumbai, Maharashtra, India",
        "pune": "Pune, Maharashtra, India",
        "hyderabad": "Hyderabad, Telangana, India",
        "chennai": "Chennai, Tamil Nadu, India",
        "delhi": "Delhi, India",
        "new delhi": "New Delhi, India",
        "noida": "Noida, Uttar Pradesh, India",
        "gurgaon": "Gurgaon, Haryana, India",
        "gurugram": "Gurugram, Haryana, India",
        "kolkata": "Kolkata, West Bengal, India",
        "ahmedabad": "Ahmedabad, Gujarat, India",
        "jaipur": "Jaipur, Rajasthan, India",
        "chandigarh": "Chandigarh, India",
        "kochi": "Kochi, Kerala, India",
        "indore": "Indore, Madhya Pradesh, India",
        "bhubaneswar": "Bhubaneswar, Odisha, India",
        "visakhapatnam": "Visakhapatnam, Andhra Pradesh, India",
        "lucknow": "Lucknow, Uttar Pradesh, India",
        "jalandhar": "Jalandhar, Punjab, India",
    }
    
    # Check first few lines for city names
    for line in lines:
        line_lower = line.lower()
        for city_key, city_full in cities.items():
            # Use word boundary to avoid partial matches
            if re.search(rf'\b{city_key}\b', line_lower):
                logger.debug(f"📍 Found location: {city_full} from line: {line}")
                return city_full
    
    # Strategy 3: Search entire text as fallback
    text_lower = text.lower()
    for city_key, city_full in cities.items():
        if re.search(rf'\b{city_key}\b', text_lower):
            logger.debug(f"📍 Found location: {city_full} in text")
            return city_full
    
    return ""


def extract_name(text: str) -> str:
    """
    Extract name from resume.
    Usually the first line, before contact details.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    if not lines:
        return ""
    
    # Try first line
    first_line = lines[0]
    
    # Clean up: remove special characters
    cleaned = re.sub(r'[•|].*$', '', first_line).strip()
    
    # Name should be 2-4 words, no @ or numbers
    words = cleaned.split()
    if 2 <= len(words) <= 4:
        # Check if it looks like a name (mostly alphabetic)
        if all(re.match(r'^[A-Za-z\.]+$', word) for word in words):
            return cleaned
    
    # Try second line if first failed
    if len(lines) > 1:
        second_line = lines[1]
        cleaned = re.sub(r'[•|].*$', '', second_line).strip()
        words = cleaned.split()
        if 2 <= len(words) <= 4:
            if all(re.match(r'^[A-Za-z\.]+$', word) for word in words):
                return cleaned
    
    return ""


def extract_skills(text: str) -> list:
    """Extract technical skills from resume."""
    common_skills = [
        # Programming Languages
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust",
        "PHP", "Ruby", "Swift", "Kotlin", "Scala", "R",
        
        # Web Technologies
        "React", "Vue.js", "VueJS", "Angular", "Node.js", "Express", "Django",
        "Flask", "FastAPI", "Spring Boot", "ASP.NET", "Laravel",
        
        # Mobile
        "React Native", "Flutter", "Android", "iOS",
        
        # Databases
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "DynamoDB",
        "Oracle", "SQL Server", "Cassandra",
        
        # Cloud & DevOps
        "AWS", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes", "Jenkins",
        "CI/CD", "Terraform", "Ansible",
        
        # Tools & Others
        "Git", "REST API", "GraphQL", "Microservices", "Agile", "Scrum",
        "Machine Learning", "AI", "Deep Learning", "NLP", "Computer Vision",
        "Playwright", "Selenium", "Automation", "Testing", "TDD",
        
        # Frontend
        "HTML", "CSS", "SASS", "Webpack", "Redux", "Next.js", "Nuxt.js",
        
        # State Management
        "Redux", "MobX", "Vuex", "Context API",
    ]
    
    found = []
    text_lower = text.lower()
    
    for skill in common_skills:
        # Use word boundary for exact match
        if re.search(rf'\b{re.escape(skill)}\b', text, re.IGNORECASE):
            if skill not in found:  # Avoid duplicates
                found.append(skill)
    
    return found


def extract_summary_snippet(text: str) -> str:
    """Extract a short professional summary."""
    # Look for summary section
    match = re.search(
        r'(?:summary|about me|profile|objective)[:\s-]*(.*?)(?:skills|experience|education|projects|$)',
        text,
        re.IGNORECASE | re.DOTALL
    )
    
    if match:
        snippet = match.group(1).strip()
        # Clean up whitespace
        snippet = re.sub(r'\s+', ' ', snippet)
        # Limit length
        return snippet[:500]
    
    # Fallback: Use first paragraph after name/title
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 3:
        # Skip first few lines (likely name/title/contact)
        for line in lines[3:8]:
            if len(line) > 50 and not any(x in line.lower() for x in ['http', '@', 'experience', 'education']):
                return line[:500]
    
    return ""