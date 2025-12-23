# ApplyBee - Chrome Extension

Auto-fill Greenhouse job applications with AI-powered resume matching.

## Installation (Development)

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `resume-matcher-extension` folder
5. Extension will appear in your toolbar

## Setup

1. Click the extension icon
2. Upload your resume (PDF or DOCX)
3. Enter your email and phone
4. Click "Save & Continue"

## Usage

1. Visit a Greenhouse job posting
2. Click the extension icon
3. Click "Check Match Score" to see your match
4. Click "Auto-Fill Application" to fill the form
5. Review and submit manually

## Configuration

Update backend URL in `utils/storage.js`:
```javascript
return 'https://applybee.up.railway.app';