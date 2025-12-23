# Chrome Web Store - Permissions Justification for ApplyBee

## Required Permissions Explanation

### 1. **"scripting"** Permission

**Why We Need It:**
The `scripting` permission is required to programmatically inject the content script into Greenhouse.io job application pages when the user clicks the "Autofill Form" button.

**Specific Use Case:**
- When users click "Autofill Form", the extension needs to ensure the content script is loaded on the page
- If the content script fails to load automatically (due to page navigation or timing issues), we use `chrome.scripting.executeScript()` as a fallback mechanism to inject it programmatically
- This ensures reliable functionality and better user experience

**Code Location:** `popup.js` line ~681
```javascript
await chrome.scripting.executeScript({
  target: { tabId: tab.id },
  files: ["contentScript.js"]
});
```

**User Benefit:**
- Ensures the auto-fill feature works reliably even if the page loads slowly or uses dynamic content
- Provides seamless experience without requiring page refreshes
- Only executes on Greenhouse.io domains (restricted by host_permissions)

---

### 2. **"storage"** Permission

**Why We Need It:**
To store the user's uploaded resume data locally in their browser for the duration of their session.

**Specific Use Cases:**
- Store parsed resume text after user uploads their resume file
- Store resume file (base64 encoded) for automatic file upload during form filling
- Temporarily cache resume score results for the current job posting
- Store request state for long-running API calls

**User Benefit:**
- Resume is stored locally (never sent to third parties except our secure backend API)
- Users don't need to re-upload resume for each job application
- Faster form filling experience

**Data Stored:**
- Resume text content (parsed from PDF/DOCX)
- Resume file (base64 encoded, for file upload)
- Current job URL and score results (temporary)
- Request IDs for tracking API calls (temporary)

---

### 3. **"tabs"** Permission

**Why We Need It:**
To get information about the current active tab (URL) to determine if the user is on a Greenhouse.io job page.

**Specific Use Cases:**
- Check the current tab's URL when user clicks "Get Resume Score" to extract the job description URL
- Verify user is on a Greenhouse.io job application page before enabling autofill
- Get tab ID to communicate with content script

**User Benefit:**
- Automatically detects job posting URLs
- Prevents errors by only working on supported pages
- Seamless integration with job browsing workflow

**What We Access:**
- Current tab URL only (read-only)
- Tab ID for message passing
- Only accessed when user actively clicks extension buttons

---

### 4. **"activeTab"** Permission

**Why We Need It:**
Complements the `tabs` permission to access the currently active tab when the user explicitly clicks the extension icon.

**Specific Use Cases:**
- Allows the extension to interact with the page the user is currently viewing
- Required for sending messages to the content script in the active tab
- Enables form field detection and auto-filling functionality

**User Benefit:**
- Extension only activates when user explicitly clicks it (user-initiated action)
- No background monitoring or tracking
- Respects user privacy - only works on pages user explicitly chooses

---

## Host Permissions Justification

### **"https://*.greenhouse.io/*"** (and subdomains)

**Why We Need It:**
- To inject content scripts on Greenhouse.io job posting pages
- To detect and extract form fields from Greenhouse application forms
- To auto-fill job application forms
- To extract job description URLs from the page

**User Benefit:**
- Core functionality requires access to Greenhouse.io pages
- Limited only to Greenhouse domains (no access to other websites)
- Users control when to use it (only when they click "Autofill")

---

### **"https://applybee.up.railway.app/*"**

**Why We Need It:**
- To send resume data and job URLs to our backend API for analysis
- To receive resume compatibility scores and skill analysis
- To get AI-generated answers for form fields

**User Benefit:**
- Enables resume scoring and matching functionality
- Provides intelligent form filling suggestions
- All data is sent over HTTPS (encrypted)

**What Data is Sent:**
- Resume text content (parsed from user's uploaded file)
- Job description URL (to fetch job requirements)
- Form field labels (to generate appropriate answers)

**Privacy Note:**
- User resume data is only sent when they explicitly click "Get Resume Score"
- Data is processed securely on our backend
- We do not store or share user data with third parties

---

## Privacy & Security Commitment

1. **Local Storage Only:** Resume data is stored locally in the user's browser
2. **User-Initiated Actions:** All features require explicit user action (button clicks)
3. **Limited Scope:** Only accesses Greenhouse.io pages and our API
4. **No Tracking:** We do not track user browsing behavior or collect analytics
5. **Secure Transmission:** All API communication uses HTTPS encryption
6. **No Third-Party Sharing:** User data is never shared with third parties

---

## Summary for Chrome Web Store Review

**All permissions are:**
- ✅ Necessary for core functionality
- ✅ Limited to specific domains only
- ✅ User-initiated (no background tracking)
- ✅ Transparent about what data is accessed
- ✅ Used responsibly for stated features only

**The extension:**
- Helps users save time on job applications
- Only works on Greenhouse.io job pages
- Stores data locally (user's browser)
- Requires explicit user action for all features
- Does not track or monitor user activity

