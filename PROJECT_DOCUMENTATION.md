# ApplyBee Project Documentation

**Version:** 1.0  
**Last Updated:** January 2025

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Extension Structure (ApplyBee2.0)](#extension-structure-applybee20)
4. [Backend Structure (NextJob)](#backend-structure-nextjob)
5. [Data Flow](#data-flow)
6. [API Documentation](#api-documentation)
7. [Key Components](#key-components)
8. [Development Guide](#development-guide)
9. [Adding New Features](#adding-new-features)
10. [Testing & Debugging](#testing--debugging)
11. [Deployment](#deployment)
12. [Security & Privacy](#security--privacy)

---

## Project Overview

ApplyBee is a Chrome extension that automates job application filling for Greenhouse.io job boards. It provides two main features:

1. **Resume Scoring**: Analyzes how well a resume matches a job description using AI/ML techniques
2. **Auto-Fill**: Automatically fills application forms with information extracted from the user's resume

### Tech Stack

- **Extension (Frontend)**: Vanilla JavaScript, Chrome Extension Manifest V3
- **Backend**: FastAPI (Python), PyTorch, Sentence Transformers
- **Storage**: Chrome Storage API (local)
- **PDF Processing**: pdf.js (Mozilla)

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│  Chrome Browser │
│                 │
│  ┌───────────┐  │
│  │  Popup UI │  │◄─── User Interface
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │ Background│  │◄─── Service Worker (API calls)
│  │  Script   │  │
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │  Content  │  │◄─── Injected into job pages
│  │  Script   │  │
│  └─────┬─────┘  │
└────────┼────────┘
         │
         │ HTTPS
         │
┌────────▼─────────────────────────┐
│   Backend API (Railway.app)      │
│                                   │
│  ┌──────────┐    ┌──────────┐   │
│  │  Score   │    │   Gist   │   │
│  │  Router  │    │  Router  │   │
│  └────┬─────┘    └────┬─────┘   │
│       │               │          │
│  ┌────▼───────────────▼─────┐  │
│  │      Services Layer      │  │
│  │  - Score Engine          │  │
│  │  - Gist Generator        │  │
│  │  - Matcher               │  │
│  │  - LLM Client            │  │
│  │  - JD Fetcher            │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

### Communication Flow

1. **User uploads resume** → Popup → Chrome Storage
2. **User clicks "Get Resume Score"** → Popup → Background → Backend API
3. **Backend processes** → Returns score → Background → Popup (via polling)
4. **User clicks "Autofill"** → Popup → Content Script
5. **Content Script** → Extracts form fields → Background → Backend API (get gists)
6. **Backend returns answers** → Content Script → Fills form fields

---

## Extension Structure (ApplyBee2.0)

### Directory Structure

```
ApplyBee2.0/
├── manifest.json              # Extension configuration
├── popup.html                 # Popup UI HTML
├── popup.js                   # Popup logic (resume upload, UI)
├── popup.css                  # Popup styling (bumblebee theme)
├── background.js              # Service worker (API communication)
├── contentScript.js           # Loader script (injected into pages)
├── contentScriptModule.js     # Main content script logic
├── assets/
│   └── icon.png              # Extension icon (🐝 themed)
├── libs/
│   ├── pdf.min.js            # PDF.js library
│   └── pdf.worker.min.js     # PDF.js worker
└── utils/
    ├── api.js                # API helper functions
    ├── detect.js             # Form field detection
    └── autofill.js           # Autofill logic
```

### Key Files

#### `manifest.json`

Defines the extension's permissions, content scripts, and metadata.

**Key Permissions:**
- `scripting`: Inject scripts into pages
- `storage`: Store resume data locally
- `tabs`: Access current tab URL
- `activeTab`: Access active tab content

**Content Scripts:**
- Injected into `*.greenhouse.io` pages
- Runs at `document_end` to ensure DOM is ready

**Web Accessible Resources:**
- Content script modules and utilities
- PDF processing libraries

#### `popup.js`

**Responsibilities:**
- Handle resume file upload (PDF/DOCX)
- Extract text from PDF using pdf.js
- Manage UI state (loading, scores, errors)
- Communicate with background script
- Store resume data in Chrome Storage
- Clear scores when popup is closed/reopened

**Key Functions:**
- `extractPDFText(file)`: Extracts text from PDF files
- `initPopup()`: Initializes popup UI on open
- `handleResumeUpload()`: Processes uploaded resume
- `handleScoreClick()`: Initiates resume scoring
- `handleAutofillClick()`: Triggers autofill process
- `startPolling(requestId)`: Polls background for score completion
- `updateLoadingUI()`: Updates loading progress UI

**Storage Keys:**
- `parsed_resume`: Extracted resume text and metadata
- `resume_file`: Base64-encoded resume file
- `last_score_result`: Most recent score result
- `last_score_jd_url`: JD URL associated with last score
- `request_${requestId}`: Request state for polling

#### `background.js`

**Responsibilities:**
- Make API calls to backend (keeps service worker alive)
- Manage request states (processing/complete/error)
- Handle long-running requests (2-minute timeout)
- Keep service worker alive during requests

**Key Functions:**
- `handleResumeScoreRequest()`: Sends resume to `/resume-score` endpoint
- `handleGenerateGistsRequest()`: Sends fields to `/get-gist` endpoint
- `fetchWithTimeout()`: HTTP fetch with timeout handling
- `startKeepAlive()`: Keeps service worker alive during long requests
- `saveRequestState()` / `getRequestState()`: Manage request state persistence

**Request State Management:**
- States: `processing`, `complete`, `error`
- Stored in Chrome Storage for persistence
- Polled by popup to check completion

#### `contentScript.js`

**Purpose:** Loader script that imports the main content script module.

**Why:** Chrome extensions require non-module scripts to be loaded first. This loader imports the ES6 module.

#### `contentScriptModule.js`

**Responsibilities:**
- Listen for messages from popup/background
- Extract form fields from the page
- Coordinate autofill process
- Handle page detection (Greenhouse.io)

**Message Types:**
- `CHECK_PAGE`: Verify page is a Greenhouse job page
- `AUTOFILL`: Trigger autofill process
- `RESUME_SCORE`: Forward score request to background

**Key Functions:**
- Message listener handles all communication
- Calls `extractFields()` from `utils/detect.js`
- Calls `autofillFields()` from `utils/autofill.js`

#### `utils/detect.js`

**Purpose:** Extract form field information from the DOM.

**Key Functions:**
- `isGreenhouse(url)`: Check if URL is a Greenhouse job page
- `extractFields()`: Find all input/textarea/select elements
- `getLabelForElement(el)`: Extract label text for a form field (multiple strategies)

**Label Detection Strategies:**
1. `label[for="id"]` attribute
2. Parent `<label>` element
3. `aria-labelledby` attribute
4. Preceding sibling element
5. `placeholder` or `aria-label` attribute
6. Nearest heading/strong text above

**Field Object Structure:**
```javascript
{
  tag: "input" | "textarea" | "select",
  name: string | null,
  id: string | null,
  placeholder: string | null,
  type: string | null,
  aria_label: string | null,
  label_text: string,  // Extracted label (e.g., "First Name*")
  element: null  // Not serialized when sending to backend
}
```

#### `utils/autofill.js`

**Purpose:** Fill form fields with answers from backend.

**Key Functions:**
- `autofillFields(fields, answers, parsed_resume, resume_file)`: Main autofill function
- `setValue(el, val, resume_file)`: Set value on a form element
- `findElementForField(field)`: Find DOM element for a field object

**Input Type Handling:**
- **Text inputs**: Direct value assignment + events
- **Select dropdowns**: Find matching option, set selectedIndex, dispatch events
- **File inputs**: Create File object from base64 resume data
- **Textareas**: Same as text inputs

**Select Matching Strategies:**
1. Exact text match (case-insensitive)
2. Numeric range matching (for YoE: "7" matches "5-7 years")
3. Word-by-word matching (for locations: "United States" matches "USA")
4. Partial match (fallback)

**Events Dispatched:**
- `input` event (for React compatibility)
- `change` event (standard HTML)
- `blur` event (trigger validation)

#### `utils/api.js`

**Purpose:** API helper functions (currently minimal, mostly handled in background.js).

**Note:** Most API calls are made directly from `background.js` or through message passing.

---

## Backend Structure (NextJob)

### Directory Structure

```
NextJob/app/
├── main.py                    # FastAPI app entry point
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container configuration
├── routers/
│   ├── score_api.py          # Resume scoring endpoints
│   └── gist_api.py           # Autofill answer generation
├── services/
│   ├── score_engine.py       # Score computation orchestration
│   ├── gist_generator.py     # Answer generation for form fields
│   ├── matcher.py            # Resume-JD matching logic
│   ├── llm_client.py         # OpenAI GPT API client
│   ├── jd_fetcher.py         # Job description fetching/scraping
│   └── skill_normalizer.py   # Skill name normalization
├── models/
│   ├── score_models.py       # Pydantic models for scoring
│   └── gist_models.py        # Pydantic models for gists
└── templates/
    └── index.html            # (If used for web UI)
```

### Key Files

#### `main.py`

**Purpose:** FastAPI application setup and configuration.

**Features:**
- CORS middleware (allows Chrome extension origins)
- Router registration (`score_router`, `gist_router`)
- Health check endpoint (`/health`)

**CORS Configuration:**
- Allows all origins (`*`) with regex for `chrome-extension://` origins
- Necessary because Chrome extensions have dynamic origin URLs

#### `routers/score_api.py`

**Endpoint:** `POST /resume-score`

**Request Model:**
```python
class ScoreRequest(BaseModel):
    parsed_resume: Dict[str, Any]  # Resume data (must have 'raw_text')
    jd_url: Optional[str] = None   # Job description URL
    job_description: Optional[str] = ""  # Direct JD text
```

**Response Model:**
```python
class ScoreResponse(BaseModel):
    success: bool
    detail: Optional[str] = None
    score: Optional[float] = None
    # Plus fields from score_engine result
```

**Process:**
1. Receives resume and JD URL/text
2. Fetches JD from URL if provided (using `jd_fetcher`)
3. Calls `score_engine.compute_resume_score()`
4. Returns score and detailed breakdown

**Timeouts:**
- Backend timeout: ~2 minutes (900 seconds)
- Extended for long-running semantic matching

#### `routers/gist_api.py`

**Endpoint:** `POST /get-gist`

**Request Model:**
```python
class GetGistRequest(BaseModel):
    resume: str              # Resume text
    jd: Optional[str] = ""   # Job description text
    labels: List[str]        # Form field labels (e.g., ["First Name*", "Email*"])
```

**Response Model:**
```python
class GetGistResponse(BaseModel):
    success: bool
    detail: str
    answers: Dict[str, str]  # {"First Name*": "John Doe", "Email*": "john@example.com"}
```

**Process:**
1. Receives resume text, JD text, and field labels
2. Calls `gist_generator.generate_gist_for_labels()`
3. Returns dictionary of label → answer mappings

#### `services/score_engine.py`

**Function:** `compute_resume_score(parsed_resume, jd_sections, jd_full_text)`

**Purpose:** Orchestrate resume scoring using the matcher service.

**Process:**
1. Extracts resume text from `parsed_resume['raw_text']`
2. Extracts skills from `jd_sections['skills']`
3. Calls `matcher.calculate_match_score_text()`
4. Formats result into response structure
5. Optionally generates LLM explanation

**Returns:**
```python
{
    "score": float,              # Overall ATS score
    "ats_score": float,          # Same as score
    "responsibility_score": float,
    "skills_score": float,
    "yoe_score": float,
    "common_skills": List[str],
    "missing_skills": List[str],
    "summary": str,
    "years_experience_resume": int,
    "years_experience_jd": int,
    "explanation": str,          # LLM-generated explanation
    # ... more fields
}
```

#### `services/gist_generator.py`

**Function:** `generate_gist_for_labels(parsed_resume, jd_data, labels)`

**Purpose:** Generate answers for form field labels using resume data and optionally LLM.

**Process:**
1. **Basic Extraction**: Uses regex and heuristics to extract:
   - Email (`extract_email()`)
   - Phone (`extract_phone()`)
   - Name (`extract_name_from_text()`)
   - Location (`extract_location()`)
   - Country (`extract_country()`)
   - Years of Experience (`extract_years_of_experience()`)
   - Links (`extract_links()`)

2. **Label Matching**: For each label, tries to match against:
   - Known field patterns (name, email, phone, etc.)
   - Resume data directly
   - LLM generation (fallback for complex questions)

3. **LLM Generation**: For labels not matched by extraction:
   - Constructs prompt with resume and JD context
   - Calls `llm_client.call_gpt_model()`
   - Parses JSON response (with fallback parsing)

**Extraction Functions:**
- `extract_email()`: Regex pattern for email addresses
- `extract_phone()`: Regex pattern for phone numbers (international format support)
- `extract_location()`: Extracts city, state, country (avoids work experience sections)
- `extract_country()`: Extracts country (uses phone code detection + location extraction)
- `extract_years_of_experience()`: Calculates YoE from employment date ranges
- `extract_links()`: Finds URLs (LinkedIn, GitHub, etc.)

**LLM Prompt Structure:**
```
Generate answers for these form fields based on the resume and job description.
Resume: [resume text]
Job Description: [JD text]
Fields: [list of labels]
Return JSON: {"Field Label": "Answer", ...}
```

#### `services/matcher.py`

**Function:** `calculate_match_score_text(resume_text_raw, jd_sections, jd_skills_extracted, jd_full_text, debug)`

**Purpose:** Core matching algorithm that compares resume to job description.

**Process:**
1. Extracts skills from resume
2. Normalizes skill names (using `skill_normalizer`)
3. Compares resume skills to JD skills
4. Calculates responsibility match (if JD sections provided)
5. Calculates YoE match
6. Computes overall ATS score

**Scoring Components:**
- **Skills Score**: Direct + contextual skill matching
- **Responsibility Score**: Semantic matching of responsibilities (if enabled)
- **YoE Score**: Years of experience match
- **Overall Score**: Weighted combination of above

**Configuration:**
- Environment variables control semantic matching:
  - `MATCHER_SEMANTIC_SCORE=0`: Disable (fast, 5-30 seconds)
  - `MATCHER_SEMANTIC_SCORE=1`: Enable (slow, 20-30 minutes)

#### `services/llm_client.py`

**Purpose:** Interface to OpenAI GPT API for answer generation.

**Function:** `call_gpt_model(prompt, model="gpt-4", temperature=0.3)`

**Features:**
- Async OpenAI API calls
- Error handling and retries
- Configurable model and temperature
- Token limit handling

#### `services/jd_fetcher.py`

**Purpose:** Fetch and parse job descriptions from Greenhouse.io URLs.

**Function:** `fetch_job_description(jd_url)`

**Process:**
1. Fetches HTML from URL
2. Parses with BeautifulSoup
3. Extracts JD sections:
   - Skills (required/bonus)
   - Responsibilities
   - Requirements
   - Full text

**Returns:**
```python
{
    "jd_sections": {
        "skills": List[str],
        "bonus_skills": List[str],
        "responsibilities": List[str]
    },
    "job_description_full": str
}
```

#### `services/skill_normalizer.py`

**Purpose:** Normalize skill names for accurate matching.

**Function:** `normalize_skills(skills)`

**Process:**
- Maps variations to canonical names (e.g., "React.js" → "React")
- Handles abbreviations (e.g., "JS" → "JavaScript")
- Removes common suffixes/prefixes

---

## Data Flow

### Resume Upload Flow

```
1. User selects PDF file in popup
   ↓
2. popup.js: extractPDFText() extracts text using pdf.js
   ↓
3. popup.js: Converts file to base64 (chunked for large files)
   ↓
4. popup.js: Stores in Chrome Storage:
   - parsed_resume: { raw_text, filename }
   - resume_file: { data: base64, filename, type }
   ↓
5. UI shows success message
```

### Resume Scoring Flow

```
1. User clicks "Get Resume Score" button
   ↓
2. popup.js: Gets current tab URL (JD URL)
   ↓
3. popup.js: Sends message to background:
   { type: "BG_RESUME_SCORE", payload: { parsed_resume, jd_url } }
   ↓
4. background.js: Generates request ID
   ↓
5. background.js: Saves request state: { status: "processing" }
   ↓
6. background.js: Starts keep-alive interval (pings every 20s)
   ↓
7. background.js: POST /resume-score to backend:
   {
     parsed_resume: { raw_text, filename },
     jd_url: "https://..."
   }
   ↓
8. Backend: Fetches JD from URL (jd_fetcher)
   ↓
9. Backend: Computes score (score_engine → matcher)
   ↓
10. Backend: Returns:
    {
      success: true,
      score: 85.5,
      ats_score: 85.5,
      common_skills: [...],
      missing_skills: [...],
      explanation: "..."
    }
   ↓
11. background.js: Saves request state: { status: "complete", data: {...} }
   ↓
12. background.js: Stops keep-alive
   ↓
13. popup.js: Polls every 2s for request status
   ↓
14. popup.js: When status === "complete", displays score in UI
   ↓
15. popup.js: Stores score in Chrome Storage:
    - last_score_result: {...}
    - last_score_jd_url: "https://..."
```

### Autofill Flow

```
1. User clicks "Autofill" button
   ↓
2. popup.js: Gets parsed_resume and resume_file from storage
   ↓
3. popup.js: Gets current tab
   ↓
4. popup.js: Sends message to content script:
   { type: "AUTOFILL", parsed_resume, resume_file }
   ↓
5. contentScriptModule.js: Extracts form fields (detect.js)
   ↓
6. contentScriptModule.js: Converts fields to label list:
   ["First Name*", "Email*", "Phone*", ...]
   ↓
7. contentScriptModule.js: Sends to background:
   { type: "BG_GENERATE_GISTS", payload: {
       parsed_resume,
       job_description: "",
       job_url: "...",
       fields: [...]
     }
   }
   ↓
8. background.js: POST /get-gist to backend:
   {
     resume: "...",
     jd: "",
     labels: ["First Name*", "Email*", ...]
   }
   ↓
9. Backend: gist_generator generates answers:
   - Extracts email, phone, name, etc. (regex)
   - For complex fields, uses LLM
   ↓
10. Backend: Returns:
    {
      success: true,
      answers: {
        "First Name*": "John Doe",
        "Email*": "john@example.com",
        "Phone*": "+1234567890",
        ...
      }
    }
   ↓
11. contentScriptModule.js: Receives answers
   ↓
12. contentScriptModule.js: Calls autofillFields(fields, answers, parsed_resume, resume_file)
   ↓
13. autofill.js: For each field:
    - Finds DOM element (findElementForField)
    - Sets value (setValue):
      * Text inputs: el.value = answer + events
      * Selects: Find option, set selectedIndex + events
      * Files: Create File object from base64 + dispatch
   ↓
14. Form is filled
```

---

## API Documentation

### Backend Base URL

```
https://applybee.up.railway.app
```

### Endpoints

#### `POST /resume-score`

**Description:** Compute resume score against job description.

**Request:**
```json
{
  "parsed_resume": {
    "raw_text": "Resume text content...",
    "filename": "resume.pdf"
  },
  "jd_url": "https://job-boards.greenhouse.io/company/jobs/12345"
}
```

**Response:**
```json
{
  "success": true,
  "detail": "Score computed",
  "score": 85.5,
  "ats_score": 85.5,
  "responsibility_score": 80.0,
  "skills_score": 90.0,
  "yoe_score": 85.0,
  "common_skills": ["React", "JavaScript", "Python"],
  "missing_skills": ["TypeScript", "Docker"],
  "summary": "Strong match with most required skills...",
  "explanation": "This resume scores 85.5% because...",
  "years_experience_resume": 7,
  "years_experience_jd": 5,
  "normalized_overlap": [...],
  "normalized_missing": [...],
  "direct_skill_score": 85.0,
  "contextual_skill_score": 90.0,
  "all_matched_skills": [...]
}
```

**Timeout:** ~2 minutes (900 seconds)

**Error Response:**
```json
{
  "detail": "Error message here"
}
```

#### `POST /get-gist`

**Description:** Generate answers for form field labels.

**Request:**
```json
{
  "resume": "Resume text content...",
  "jd": "Job description text...",
  "labels": ["First Name*", "Email*", "Phone*", "Years of Experience*"]
}
```

**Response:**
```json
{
  "success": true,
  "detail": "Gists generated",
  "answers": {
    "First Name*": "John Doe",
    "Email*": "john@example.com",
    "Phone*": "+1234567890",
    "Years of Experience*": "7"
  }
}
```

**Timeout:** ~30 seconds (typical)

**Error Response:**
```json
{
  "detail": "Gist generation failed: Error message"
}
```

#### `GET /health`

**Description:** Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## Key Components

### Chrome Extension Components

#### Message Passing

**Popup ↔ Background:**
```javascript
// Popup → Background
chrome.runtime.sendMessage({ type: "BG_RESUME_SCORE", payload: {...} }, (response) => {
  // Handle response
});

// Background → Popup (via storage events or polling)
// Popup polls background for status updates
```

**Popup ↔ Content Script:**
```javascript
// Popup → Content Script
chrome.tabs.sendMessage(tabId, { type: "AUTOFILL", parsed_resume: {...} }, (response) => {
  // Handle response
});

// Content Script → Background
chrome.runtime.sendMessage({ type: "BG_GENERATE_GISTS", payload: {...} }, (response) => {
  // Handle response
});
```

#### Chrome Storage Structure

```javascript
{
  // Resume data
  "parsed_resume": {
    raw_text: "Resume text...",
    filename: "resume.pdf"
  },
  
  // Resume file (base64)
  "resume_file": {
    data: "base64encodeddata...",
    filename: "resume.pdf",
    type: "application/pdf"
  },
  
  // Score results
  "last_score_result": {
    score: 85.5,
    common_skills: [...],
    // ... full score response
  },
  "last_score_jd_url": "https://job-boards.greenhouse.io/...",
  
  // Request states (for polling)
  "request_score_1234567890": {
    status: "processing" | "complete" | "error",
    startTime: 1234567890,
    data: {...},
    error: "..."
  },
  
  // Keep-alive ping
  "keep_alive_ping": 1234567890
}
```

### Backend Components

#### Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...

# Matcher Configuration
MATCHER_SEMANTIC_SCORE=0          # 0 = fast mode, 1 = semantic (slow)
MATCHER_SEMANTIC_NORMALIZER=1     # Use skill normalization
MATCHER_SEMANTIC=""               # Legacy flag

# Server Configuration
PORT=8000                         # Server port (usually set by Railway)
```

#### Request/Response Models

**Score Models** (`models/score_models.py`):
```python
class ScoreRequest(BaseModel):
    parsed_resume: Dict[str, Any]
    jd_url: Optional[str] = None
    job_description: Optional[str] = ""

class ScoreResponse(BaseModel):
    success: bool
    detail: Optional[str] = None
    score: Optional[float] = None
    # ... additional fields
```

**Gist Models** (`models/gist_models.py`):
```python
class GetGistRequest(BaseModel):
    resume: str
    jd: Optional[str] = ""
    labels: List[str]

class GetGistResponse(BaseModel):
    success: bool
    detail: str
    answers: Dict[str, str]
```

---

## Development Guide

### Prerequisites

**Extension Development:**
- Chrome browser (latest version)
- Text editor (VS Code recommended)
- Basic knowledge of JavaScript, HTML, CSS

**Backend Development:**
- Python 3.9+
- pip
- (Optional) Docker for containerized deployment

### Setup Extension (ApplyBee2.0)

1. **Clone/Download the extension folder:**
   ```bash
   cd ApplyBee2.0
   ```

2. **Load in Chrome:**
   - Open Chrome
   - Go to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked"
   - Select the `ApplyBee2.0` folder

3. **Verify Installation:**
   - Extension icon should appear in toolbar
   - Click icon to open popup
   - Popup should show upload form

4. **Development Workflow:**
   - Make changes to files
   - Go to `chrome://extensions/`
   - Click reload icon on extension card
   - Test changes

### Setup Backend (NextJob)

1. **Navigate to backend directory:**
   ```bash
   cd NextJob/app
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   **Note:** PyTorch installation may take time. Requirements file uses CPU-only version.

4. **Set environment variables:**
   ```bash
   # Create .env file
   echo "OPENAI_API_KEY=sk-..." > .env
   echo "MATCHER_SEMANTIC_SCORE=0" >> .env
   ```

5. **Run server:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

6. **Test endpoints:**
   - Health: `http://localhost:8000/health`
   - API docs: `http://localhost:8000/docs`

### Local Testing

1. **Update extension backend URL:**
   In `popup.js` and `background.js`, change:
   ```javascript
   const BACKEND_BASE = "http://localhost:8000";  // Instead of Railway URL
   ```

2. **Test flow:**
   - Upload resume in extension popup
   - Visit a Greenhouse job page
   - Click "Get Resume Score" (should hit local backend)
   - Click "Autofill" (should fill form)

3. **Check logs:**
   - Extension: Open DevTools → Console (for popup) or Service Worker (for background)
   - Backend: Terminal output (with uvicorn --reload)

---

## Adding New Features

### Adding a New Form Field Type

**Scenario:** You want to support a new type of form field (e.g., date pickers).

1. **Update `utils/detect.js`:**
   - Add selector for new field type in `extractFields()`:
     ```javascript
     const selectors = Array.from(document.querySelectorAll("input, textarea, select, input[type='date']"));
     ```

2. **Update `utils/autofill.js`:**
   - Add handling in `setValue()` function:
     ```javascript
     if (el.type === "date") {
       // Parse answer to YYYY-MM-DD format
       el.value = formatDateForInput(val);
       el.dispatchEvent(new Event('change', { bubbles: true }));
       return true;
     }
     ```

3. **Test:**
   - Create test page with date input
   - Verify detection and filling work

### Adding a New Resume Field Extractor

**Scenario:** You want to extract "GitHub username" from resumes.

1. **Update `services/gist_generator.py`:**

   ```python
   def extract_github_username(text: str):
       """Extract GitHub username from resume text."""
       # Pattern: github.com/username or @username
       pattern = r'(?:github\.com/|@)([\w-]+)'
       match = re.search(pattern, text, re.IGNORECASE)
       return match.group(1) if match else None
   ```

2. **Add to label matching logic:**

   ```python
   # In generate_gist_for_labels()
   label_lower = label.lower()
   
   if "github" in label_lower:
       github_username = extract_github_username(resume_text)
       if github_username:
           answers[label] = f"https://github.com/{github_username}"
           continue
   ```

3. **Test:**
   - Test with resumes containing GitHub links
   - Verify extraction and matching work

### Adding a New API Endpoint

**Scenario:** You want to add a `/resume-parse` endpoint that only parses resumes.

1. **Create router file** (`routers/parse_api.py`):

   ```python
   from fastapi import APIRouter
   from pydantic import BaseModel
   
   router = APIRouter()
   
   class ParseRequest(BaseModel):
       resume_text: str
   
   class ParseResponse(BaseModel):
       success: bool
       parsed_data: dict
   
   @router.post("/resume-parse", response_model=ParseResponse)
   async def parse_resume_endpoint(req: ParseRequest):
       # Your parsing logic here
       parsed_data = {...}
       return ParseResponse(success=True, parsed_data=parsed_data)
   ```

2. **Register router** in `main.py`:

   ```python
   from routers.parse_api import router as parse_router
   
   app.include_router(parse_router, prefix="")
   ```

3. **Add endpoint to extension:**

   ```javascript
   // In background.js
   async function handleParseRequest(payload) {
     const response = await fetchWithTimeout(`${BACKEND_BASE}/resume-parse`, {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ resume_text: payload.resume_text })
     });
     return response;
   }
   ```

### Adding Support for a New Job Board

**Scenario:** You want to support Workday job applications (not just Greenhouse).

1. **Update `manifest.json`:**
   - Add Workday domains to `host_permissions` and `content_scripts.matches`

2. **Update `utils/detect.js`:**
   - Add `isWorkday(url)` function
   - Update `extractFields()` if Workday uses different field structures

3. **Update `utils/autofill.js`:**
   - Add Workday-specific field filling logic if needed

4. **Test:**
   - Load extension on Workday job page
   - Verify field detection and filling work

---

## Testing & Debugging

### Extension Debugging

#### Popup Debugging

1. **Open popup DevTools:**
   - Right-click extension icon
   - Select "Inspect popup"
   - Console shows `popup.js` logs

2. **Common Issues:**
   - **"pdfjsLib not loaded"**: Check `libs/pdf.min.js` is in `web_accessible_resources`
   - **"Could not establish connection"**: Content script not injected, check `manifest.json` matches
   - **Storage errors**: Check Chrome Storage permissions

#### Background Script Debugging

1. **Open Service Worker DevTools:**
   - Go to `chrome://extensions/`
   - Find ApplyBee extension
   - Click "service worker" link (under "Inspect views")
   - Console shows `background.js` logs

2. **Check Request States:**
   ```javascript
   // In Service Worker console
   chrome.storage.local.get(null, (data) => {
     console.log("All storage:", data);
   });
   ```

#### Content Script Debugging

1. **Open Page DevTools:**
   - On the job page, press F12
   - Console shows `contentScript.js` and `contentScriptModule.js` logs

2. **Check if Content Script Loaded:**
   - Look for "🔥 Loader injected" and "🔥 contentScriptModule running" in console

3. **Test Field Extraction:**
   ```javascript
   // In Page DevTools console
   // Import detect function (if available in global scope, or test directly)
   // Or check content script logs for extracted fields
   ```

### Backend Debugging

#### Local Development

1. **Run with debug logging:**
   ```bash
   uvicorn main:app --reload --log-level debug
   ```

2. **Check logs:**
   - Terminal shows all request/response logs
   - `loguru` logger provides structured logging

3. **Test endpoints directly:**
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # Score endpoint
   curl -X POST http://localhost:8000/resume-score \
     -H "Content-Type: application/json" \
     -d '{"parsed_resume": {"raw_text": "..."}, "jd_url": "..."}'
   ```

#### Production Debugging (Railway)

1. **View logs:**
   - Railway dashboard → Deployments → Logs

2. **Common Issues:**
   - **Timeout errors**: Increase timeout or optimize code
   - **Memory errors**: Check for memory leaks in long-running requests
   - **API key errors**: Verify environment variables are set

### Common Problems & Solutions

#### Problem: Autofill not working

**Symptoms:** Fields not filling, or wrong values filled.

**Debugging Steps:**
1. Check content script logs for field extraction
2. Check background script logs for gist generation response
3. Verify answers match field labels exactly
4. Check if fields are detected correctly (may be hidden/disabled)

**Solutions:**
- Update `getLabelForElement()` in `detect.js` if labels not extracted correctly
- Improve answer matching in `gist_generator.py`
- Add delays in `autofill.js` if React components need time to render

#### Problem: Resume score timeout

**Symptoms:** Score request times out after 2 minutes.

**Debugging Steps:**
1. Check backend logs for slow operations
2. Verify `MATCHER_SEMANTIC_SCORE=0` for fast mode
3. Check JD fetching time

**Solutions:**
- Disable semantic scoring (set `MATCHER_SEMANTIC_SCORE=0`)
- Optimize matcher code
- Increase timeout (not recommended, optimize instead)

#### Problem: PDF extraction fails

**Symptoms:** "pdfjsLib not loaded" error or empty text extracted.

**Debugging Steps:**
1. Verify `libs/pdf.min.js` exists and is in `web_accessible_resources`
2. Check PDF file is not corrupted
3. Test with different PDF files

**Solutions:**
- Ensure PDF.js libraries are properly included
- Handle different PDF formats (some may be images, require OCR)

---

## Deployment

### Extension Deployment

#### Chrome Web Store Submission

1. **Prepare extension:**
   - Ensure all files are present
   - Test thoroughly
   - Remove debug logs (optional, but recommended)

2. **Create ZIP file:**
   ```bash
   cd ApplyBee2.0
   zip -r ../ApplyBee-extension.zip . -x "*.git*" "*.md" "__MACOSX*"
   ```

3. **Submit to Chrome Web Store:**
   - Go to [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
   - Create new item
   - Upload ZIP file
   - Fill in store listing (description, screenshots, etc.)
   - Provide privacy policy URL (see `PRIVACY_POLICY.html`)
   - Justify permissions (see `PERMISSIONS_JUSTIFICATION.md`)
   - Submit for review

4. **Update Backend URL:**
   - Ensure `BACKEND_BASE` in `popup.js` and `background.js` points to production URL
   - Or use environment-specific configuration

### Backend Deployment

#### Railway.app Deployment

1. **Prepare repository:**
   - Ensure `Dockerfile` or `Procfile` is present
   - Set environment variables in Railway dashboard

2. **Deploy:**
   - Connect GitHub repository to Railway
   - Railway detects Python app and builds automatically
   - Set environment variables:
     - `OPENAI_API_KEY`
     - `MATCHER_SEMANTIC_SCORE=0`
     - `PORT` (auto-set by Railway)

3. **Verify deployment:**
   - Check health endpoint: `https://your-app.railway.app/health`
   - Test score endpoint with sample data

#### Alternative: Docker Deployment

1. **Build image:**
   ```bash
   cd NextJob/app
   docker build -t applybee-backend .
   ```

2. **Run container:**
   ```bash
   docker run -p 8000:8000 \
     -e OPENAI_API_KEY=sk-... \
     -e MATCHER_SEMANTIC_SCORE=0 \
     applybee-backend
   ```

---

## Security & Privacy

### Extension Security

#### Content Security Policy (CSP)

Defined in `manifest.json`:
```json
"content_security_policy": {
  "extension_pages": "script-src 'self'; object-src 'self'"
}
```

**What it does:**
- Prevents inline scripts in extension pages
- Only allows scripts from extension bundle
- Prevents XSS attacks

#### XSS Protection

In `popup.js`, user input is sanitized:
```javascript
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
```

**Usage:**
- Filenames are escaped before display
- Resume text is not rendered directly in HTML

#### Permissions

**Justification** (see `PERMISSIONS_JUSTIFICATION.md`):
- `scripting`: Inject content scripts for autofill
- `storage`: Store resume data locally (not sent to external servers except backend)
- `tabs`: Get current tab URL for JD matching
- `activeTab`: Access page content for field extraction

### Backend Security

#### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"^chrome-extension://.*$"
)
```

**Note:** In production, consider restricting `allow_origins` to specific extension IDs.

#### API Key Security

- `OPENAI_API_KEY` stored as environment variable (never in code)
- Backend validates API key before making LLM calls
- Rate limiting recommended (can use `slowapi` middleware)

#### Data Handling

- Resume data is only stored in Chrome Storage (client-side)
- Backend processes data but doesn't store it (stateless)
- JD URLs are fetched but not stored

### Privacy Policy

See `PRIVACY_POLICY.html` for user-facing privacy policy.

**Key Points:**
- Resume data stored locally in Chrome Storage
- Only sent to backend for processing (not stored)
- JD URLs fetched for scoring only
- No tracking or analytics

---

## Future Enhancements

### Potential Features

1. **Multi-job board support:**
   - Workday, Lever, Greenhouse (already supported)
   - Generic form detection for any job board

2. **Resume optimization suggestions:**
   - AI-powered recommendations to improve resume based on JD
   - Skill gap analysis with actionable tips

3. **Application tracking:**
   - Track applied jobs
   - Store scores and application dates
   - Dashboard to view application history

4. **Cover letter generation:**
   - Generate personalized cover letters based on resume + JD
   - Multiple templates/styles

5. **Batch application:**
   - Apply to multiple jobs at once
   - Queue management for bulk applications

### Technical Improvements

1. **Caching:**
   - Cache JD fetching results
   - Cache score computations for same resume+JD pairs

2. **Performance:**
   - Optimize matcher for faster scoring
   - Parallel processing for multiple fields

3. **Error handling:**
   - Better error messages for users
   - Retry logic for failed requests

4. **Testing:**
   - Unit tests for extractors
   - Integration tests for autofill
   - E2E tests for full flow

---

## Contributing

### Code Style

**JavaScript:**
- Use ES6+ features
- Prefer `const`/`let` over `var`
- Use async/await for async operations
- Add comments for complex logic

**Python:**
- Follow PEP 8
- Use type hints where possible
- Add docstrings to functions
- Use `loguru` for logging

### Git Workflow

1. Create feature branch: `git checkout -b feature/new-feature`
2. Make changes and commit: `git commit -m "Add new feature"`
3. Push to remote: `git push origin feature/new-feature`
4. Create pull request

### Documentation Updates

- Update this documentation when adding new features
- Add code comments for complex functions
- Update API documentation if endpoints change

---

## Support & Resources

### Documentation Files

- `README.md`: Quick start guide
- `PERMISSIONS_JUSTIFICATION.md`: Chrome Web Store permission explanations
- `DATA_COLLECTION_DISCLOSURE.md`: Data collection details
- `PRIVACY_POLICY.html`: Privacy policy template
- `HOW_TO_HOST_PRIVACY_POLICY.md`: Guide for hosting privacy policy

### External Resources

- [Chrome Extension Documentation](https://developer.chrome.com/docs/extensions/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PDF.js Documentation](https://mozilla.github.io/pdf.js/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

---

## Conclusion

This documentation provides a comprehensive guide to understanding, developing, and maintaining the ApplyBee project. For questions or issues, refer to the debugging section or review the code comments in relevant files.

**Last Updated:** January 2025  
**Version:** 1.0

