# Chrome Web Store - Data Collection Disclosure

## Required Checkboxes for ApplyBee Extension

Based on the extension's functionality, you should check the following categories:

### ✅ **1. Personally identifiable information**
**Why:** The extension extracts and processes personal information from uploaded resumes, including:
- Name (first name, last name)
- Email address
- Phone number
- Resume content (which may contain additional PII)

**How it's used:**
- Extracted from resume when user uploads their file
- Used to auto-fill job application forms
- Sent to backend API for resume scoring (only when user clicks "Get Resume Score")
- Stored locally in browser's chrome.storage.local

**User Control:** 
- Users voluntarily upload their resume
- Data is only processed when user explicitly clicks buttons
- Stored locally (user's own browser)

---

### ✅ **6. Location**
**Why:** The extension extracts location information from resumes, including:
- City, state, country
- Physical address (if present in resume)

**How it's used:**
- Extracted from resume for auto-filling location fields in job applications
- Used to match job location requirements

**Note:** The extension may also receive IP address metadata when making API calls, but this is standard web communication and not actively collected.

---

### ⚠️ **8. User activity** (Optional - Check if you want to be thorough)
**Why:** The extension interacts with form fields on web pages to auto-fill them.

**Important Clarification:**
- The extension DOES interact with form fields (clicks, field detection, value insertion)
- However, this is **user-initiated** and **only on Greenhouse.io pages** when user clicks "Autofill"
- This is NOT background monitoring - it only happens when user explicitly requests it
- No keystroke logging or passive monitoring

**Recommendation:** You can choose to check this or not, depending on how strictly you want to disclose. If checked, you should clarify in your privacy policy that this is user-initiated only.

---

### ✅ **9. Website content**
**Why:** The extension reads content from Greenhouse.io job application pages, including:
- Job descriptions and requirements
- Form field labels and structure
- Page content to detect application forms

**How it's used:**
- To extract job description URLs for resume scoring
- To detect and understand form fields for auto-filling
- To ensure the extension only works on appropriate pages

**Scope:** Only reads content from Greenhouse.io domains (as specified in host_permissions)

---

## Summary - Recommended Checkboxes

### ✅ **Must Check:**
1. ✅ **Personally identifiable information**
6. ✅ **Location**
9. ✅ **Website content**

### ⚠️ **Optional (Consider Checking):**
8. ⚠️ **User activity** (if you want to be thorough about form field interaction)

### ❌ **Do NOT Check:**
2. ❌ Health information
3. ❌ Financial and payment information
4. ❌ Authentication information
5. ❌ Personal communications
7. ❌ Web history

---

## Additional Disclosure Notes

When filling out the form, you'll need to explain:

**"Why do you collect this data?"**
- To provide the core functionality of the extension (resume scoring and auto-filling job applications)
- To match user's resume with job requirements
- To automatically fill form fields with user-provided information

**"How do you use this data?"**
- Resume data is processed by our backend API to calculate compatibility scores
- Personal information is used to populate job application forms
- All data is sent only when user explicitly clicks "Get Resume Score" or "Autofill Form"

**"Do you share this data with third parties?"**
- NO - User data is only sent to our secure backend API (applybee.up.railway.app)
- We do not share, sell, or distribute user data to third parties
- Data is processed securely and used only for the stated purpose

**"User data retention/deletion:"**
- Resume data is stored locally in the user's browser (chrome.storage.local)
- Users can clear this data by uninstalling the extension or clearing browser data
- Backend API processes data for resume scoring but does not store it permanently (clarify based on your actual backend implementation)

