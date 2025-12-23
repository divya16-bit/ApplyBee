// popup.js (type=module)
console.log("🔥 POPUP running");

const BACKEND_BASE = "https://applybee.up.railway.app";

// ============ TIMEOUT CONFIGURATION ============
const REQUEST_TIMEOUT = 2 * 60 * 1000; // 2 minutes in milliseconds
const POLLING_INTERVAL = 2000; // Poll every 2 seconds (more frequent updates)

function $(id) { return document.getElementById(id); }

// ============ XSS PROTECTION ============
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function sanitizeHtml(text) {
  if (!text) return '';
  // Remove potentially dangerous HTML tags
  return escapeHtml(text);
}

// ============ POLLING STATE ============
let currentRequestId = null;
let pollingInterval = null;
let pollingStartTime = null;

// ============ PDF EXTRACTION ============
async function extractPDFText(file) {
  if (!window.pdfjsLib) {
    console.error("❌ pdfjsLib not loaded. Check if libs/pdf.min.js is loaded correctly.");
    throw new Error("pdfjsLib not loaded");
  }
  try {
    pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('libs/pdf.worker.min.js');
  } catch (e) {
    console.error("❌ Failed to set PDF worker:", e);
    throw e;
  }

  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;

  let full = "";
  for (let i = 1; i <= pdf.numPages; ++i) {
    const page = await pdf.getPage(i);
    const txt = await page.getTextContent();
    const pageText = txt.items.map(i => i.str).join(" ");
    full += pageText + "\n\n";
  }
  return full.trim();
}

// ============ MESSAGE HELPERS ============
async function sendBgMessage(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
      } else {
        resolve(resp);
      }
    });
  });
}

// ============ FORMAT TIME ============
function formatTime(ms) {
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
}

// ============ POLLING MECHANISM ============
function startPolling(requestId) {
  currentRequestId = requestId;
  pollingStartTime = Date.now();
  
  // Poll every 3 seconds
  pollingInterval = setInterval(async () => {
    await checkRequestStatus();
  }, POLLING_INTERVAL);
  
  console.log(`🔄 Started polling for request: ${requestId}`);
}

function stopPolling() {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
  currentRequestId = null;
  pollingStartTime = null;
  console.log("🛑 Stopped polling");
}

async function checkRequestStatus() {
  if (!currentRequestId) return;
  
  const status = $("status");
  const elapsed = Date.now() - pollingStartTime;
  const elapsedFormatted = formatTime(elapsed);
  const remainingMs = REQUEST_TIMEOUT - elapsed;
  const remainingFormatted = formatTime(remainingMs);
  
      // Check if we've exceeded timeout on client side
      if (elapsed >= REQUEST_TIMEOUT) {
        stopPolling();
        status.innerHTML = `<div class="error">Request timed out after 2 minutes. Please try again.</div>`;
        return;
      }
  
  try {
    const response = await sendBgMessage({
      type: "CHECK_REQUEST_STATUS",
      requestId: currentRequestId
    });
    
    console.log(`📊 Poll response (${elapsedFormatted}):`, response.status);
    
    if (response.status === 'processing') {
      // Still processing - update UI with elapsed time
      updateLoadingUI(elapsedFormatted, remainingFormatted);
      return;
    }
    
    // Request completed (success or error)
    stopPolling();
    
    if (response.status === 'complete' && response.ok) {
      console.log(`✅ Request completed in ${response.elapsed || elapsedFormatted}s`);
      // Get current JD URL to store with score
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const currentJdUrl = tabs && tabs[0] ? tabs[0].url : null;
      await chrome.storage.local.set({ 
        last_score_result: response.data,
        last_score_jd_url: currentJdUrl  // Store JD URL with score
      });
      displayScoreResult(response.data);
    } else if (response.status === 'error') {
      console.log(`❌ Request failed: ${response.error}`);
      status.innerHTML = `<div class="error">Score request failed: ${response.error || 'Unknown error'}</div>`;
    } else if (response.status === 'not_found') {
      status.innerHTML = `<div class="error">Request not found. Please try again.</div>`;
    }
    
  } catch (err) {
    console.error("Polling error:", err);
    // Don't stop polling on transient errors, just log
  }
}

function updateLoadingUI(elapsed, remaining) {
  const status = $("status");
  const elapsedMs = Date.now() - pollingStartTime;
  const progressPercent = Math.min((elapsedMs / REQUEST_TIMEOUT) * 100, 100);
  
  status.innerHTML = `
    <div class="loading-container">
      <div class="loading-header">
        <div class="loading-spinner-large"></div>
        <div class="loading-title">Analyzing Resume Compatibility</div>
        <div class="loading-subtitle">Comparing your skills with job requirements...</div>
      </div>
      
      <div class="loading-steps">
        <div class="step-item">
          <div class="step-icon">📄</div>
          <div class="step-text">Parsing resume & extracting skills</div>
        </div>
        <div class="step-item">
          <div class="step-icon">🔍</div>
          <div class="step-text">Analyzing job description</div>
        </div>
        <div class="step-item">
          <div class="step-icon">⚖️</div>
          <div class="step-text">Calculating compatibility score</div>
        </div>
        <div class="step-item">
          <div class="step-icon">📊</div>
          <div class="step-text">Identifying missing skills</div>
        </div>
      </div>
      
      <div class="loading-progress-section">
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${progressPercent}%"></div>
          </div>
          <div class="progress-text">${Math.round(progressPercent)}%</div>
        </div>
        
        <div class="loading-time-info">
          <div class="time-item">
            <span class="time-label">⏱️ Elapsed:</span>
            <span class="time-value">${elapsed}</span>
          </div>
          <div class="time-item">
            <span class="time-label">⏳ Remaining:</span>
            <span class="time-value">${remaining}</span>
          </div>
        </div>
      </div>
      
      <div class="loading-hint">
        💡 This typically takes 30-60 seconds. You can close this popup - we'll save the result.
      </div>
      
      <button id="cancelRequest" class="cancel-btn">✕ Cancel Request</button>
    </div>
  `;
  
  // Add cancel handler
  const cancelBtn = $("cancelRequest");
  if (cancelBtn) {
    cancelBtn.onclick = cancelCurrentRequest;
  }
}

async function cancelCurrentRequest() {
  if (currentRequestId) {
    console.log("🚫 User cancelled request:", currentRequestId);
    await sendBgMessage({
      type: "CANCEL_REQUEST",
      requestId: currentRequestId
    });
  }
  stopPolling();
  $("status").innerHTML = `<div style="text-align: center; color: #666; padding: 16px;">Request cancelled</div>`;
}

// ============ CHECK FOR PENDING REQUEST ON POPUP OPEN ============
async function checkPendingRequest() {
  try {
    const all = await chrome.storage.local.get(null);
    const pendingKeys = Object.keys(all).filter(k => k.startsWith('request_'));
    
    console.log("🔍 Checking for pending requests:", pendingKeys);
    
    for (const key of pendingKeys) {
      const state = all[key];
      const requestId = key.replace('request_', '');
      
      if (state.status === 'processing') {
        const elapsed = Date.now() - state.startTime;
        
        // If less than 20 minutes old, resume polling
        if (elapsed < REQUEST_TIMEOUT) {
          console.log(`🔄 Resuming polling for pending request: ${requestId} (${formatTime(elapsed)} elapsed)`);
          currentRequestId = requestId;
          pollingStartTime = state.startTime;
          
          // Update UI immediately
          updateLoadingUI(formatTime(elapsed), formatTime(REQUEST_TIMEOUT - elapsed));
          
          // Start polling
          pollingInterval = setInterval(async () => {
            await checkRequestStatus();
          }, POLLING_INTERVAL);
          
          return true;
        } else {
          // Too old, clean up
          console.log(`🧹 Cleaning up expired request: ${requestId}`);
          await chrome.storage.local.remove(key);
        }
      } else if (state.status === 'complete') {
        // We have a result! Display it
        console.log(`📊 Found completed request: ${requestId}`);
        displayScoreResult(state.data);
        await chrome.storage.local.remove(key);
        // Get current JD URL to store with score
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const currentJdUrl = tabs && tabs[0] ? tabs[0].url : null;
        await chrome.storage.local.set({ 
          last_score_result: state.data,
          last_score_jd_url: currentJdUrl  // Store JD URL with score
        });
        return true;
      } else if (state.status === 'error') {
        console.log(`❌ Found failed request: ${requestId}`);
        $("status").innerHTML = `<div class="error">Previous request failed: ${state.error}</div>`;
        await chrome.storage.local.remove(key);
        return true;
      }
    }
  } catch (e) {
    console.error("Error checking pending requests:", e);
  }
  
  return false;
}

// ============ DISPLAY SCORE RESULT ============
function displayScoreResult(data) {
  const status = $("status");
  console.log("📊 Full backend response:", data);
  
  const score = data.score ?? data.resume_score ?? 0;
  let missingSkills = data.missing_skills || data.missingSkills || [];
  const normalizedMissing = data.normalized_missing || [];
  const commonSkills = data.common_skills || data.commonSkills || [];
  const explanation = data.explanation || data.summary || "";

  // Filter and format missing skills
  missingSkills = missingSkills
    .map(skill => skill.trim())
    .filter(skill => {
      if (skill.length > 50) return false;
      if (skill.toLowerCase().includes('experience with') ||
        skill.toLowerCase().includes('working with') ||
        skill.toLowerCase().includes('familiar with') ||
        skill.toLowerCase().includes('comfortable with') ||
        skill.toLowerCase().includes('you will') ||
        skill.toLowerCase().includes('you\'ll') ||
        skill.toLowerCase().includes('collaborate') ||
        skill.toLowerCase().includes('mentor') ||
        skill.toLowerCase().includes('improve workflows')) {
        return false;
      }
      return true;
    })
    .slice(0, 30);

  // Use normalized_missing if available
  if (normalizedMissing.length > 0) {
    const normalizedSkills = normalizedMissing
      .map(item => {
        if (Array.isArray(item) && item.length > 0) {
          return (item[0] || '').trim();
        }
        if (typeof item === 'string') {
          return item.trim();
        }
        return '';
      })
      .filter(skill => {
        if (!skill || skill.length === 0 || skill.length > 50) return false;
        if (skill.toLowerCase().includes('experience with') ||
          skill.toLowerCase().includes('working with') ||
          skill.toLowerCase().includes('familiar with') ||
          skill.toLowerCase().includes('comfortable with') ||
          skill.toLowerCase().includes('you will') ||
          skill.toLowerCase().includes('you\'ll') ||
          skill.toLowerCase().includes('collaborate') ||
          skill.toLowerCase().includes('mentor') ||
          skill.toLowerCase().includes('improve workflows')) {
          return false;
        }
        return true;
      })
      .slice(0, 30);

    if (normalizedSkills.length > 0) {
      missingSkills = normalizedSkills;
    }
  }

  const roundedScore = Math.round(score * 10) / 10;

  let html = `<div class="score-display">`;
  html += `<div class="score-label">Resume Compatibility</div>`;
  html += `<div class="score-value">${roundedScore}%</div>`;
  html += `</div>`;

  if (explanation) {
    const safeExplanation = escapeHtml(explanation);
    html += `<div style="margin: 12px 0; padding: 12px; background: #f0f7ff; border-radius: 6px; font-size: 12px; line-height: 1.5; color: #333;">`;
    html += `<strong>💡 Analysis:</strong><br>${safeExplanation}`;
    html += `</div>`;
  }

  if (commonSkills.length > 0) {
    html += `<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #e0e0e0;">`;
    html += `<div style="font-weight: 600; color: #4CAF50; margin-bottom: 8px;">✓ Matched Skills (${commonSkills.length}):</div>`;
    html += `<div style="display: flex; flex-wrap: wrap; gap: 6px;">`;
    commonSkills.slice(0, 10).forEach(skill => {
      const safeSkill = escapeHtml(skill);
      html += `<span style="padding: 4px 8px; background: #e8f5e9; color: #2e7d32; border-radius: 4px; font-size: 11px;">${safeSkill}</span>`;
    });
    if (commonSkills.length > 10) {
      html += `<span style="padding: 4px 8px; color: #666; font-size: 11px;">+${commonSkills.length - 10} more</span>`;
    }
    html += `</div></div>`;
  }

  if (missingSkills.length > 0) {
    html += `<div class="missing-skills">`;
    html += `<div class="missing-skills-title">⚠️ Missing Skills (${missingSkills.length}):</div>`;
    html += `<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;">`;
    missingSkills.forEach(skill => {
      const displaySkill = escapeHtml(skill.charAt(0).toUpperCase() + skill.slice(1));
      html += `<span style="padding: 6px 12px; background: #fff3e0; border-left: 3px solid #ff9800; border-radius: 4px; font-size: 12px; color: #e65100;">${displaySkill}</span>`;
    });
    html += `</div></div>`;
  } else if (commonSkills.length === 0) {
    html += `<div class="success-message">✓ All required skills found in your resume!</div>`;
  }

  status.innerHTML = html;
}

// ============ CHECK RESUME STATUS ============
async function checkResumeStatus() {
  const { parsed_resume } = await chrome.storage.local.get("parsed_resume");
  const status = $("status");

  if (parsed_resume) {
    const safeFilename = escapeHtml(parsed_resume.filename || 'resume');
    status.innerHTML = `<div class="success-message">✓ Resume loaded: <strong>${safeFilename}</strong></div>`;
    // Don't show stored scores - each popup open is a fresh start
    // User needs to click "Get Resume Score" again if they want to see the score
  } else {
    status.innerHTML = `<div style="text-align: center; color: #666; padding: 8px;">Please upload your resume to get started</div>`;
  }
}

// ============ INIT POPUP ============
function initPopup() {
  console.log("🔥 POPUP initPopup called");
  const upload = $("resumeInput");
  const scoreBtn = $("checkScore");
  const autofillBtn = $("autofill");
  const status = $("status");

  console.log("🔍 Elements found:", {
    upload: !!upload,
    scoreBtn: !!scoreBtn,
    autofillBtn: !!autofillBtn,
    status: !!status
  });

  if (!scoreBtn || !autofillBtn) {
    console.error("❌ Buttons not found! Retrying in 100ms...");
    setTimeout(initPopup, 100);
    return;
  }

  // Clear any stored scores when popup opens (fresh start each time)
  chrome.storage.local.remove(["last_score_result", "last_score_jd_url"]);
  
  // Check for pending requests first
  checkPendingRequest().then(hasPending => {
    if (!hasPending) {
      checkResumeStatus();
    }
  });

  // Listen for results from background (push notification)
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "SCORE_RESULT" && msg.requestId === currentRequestId) {
      console.log("📩 Received score result push:", msg);
      stopPolling();
      
      if (msg.result?.ok) {
        // Get current JD URL to store with score
        chrome.tabs.query({ active: true, currentWindow: true }).then(tabs => {
          const currentJdUrl = tabs && tabs[0] ? tabs[0].url : null;
          chrome.storage.local.set({ 
            last_score_result: msg.result.data,
            last_score_jd_url: currentJdUrl  // Store JD URL with score
          });
        });
        displayScoreResult(msg.result.data);
      } else {
        status.innerHTML = `<div class="error">Score request failed: ${msg.result?.error || 'Unknown error'}</div>`;
      }
    }
  });

  // -------- RESUME UPLOAD --------
  upload?.addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    status.innerHTML = `<div class="loading"><div class="loading-spinner"></div><div>Extracting text from file...</div></div>`;
    try {
      // Validate file size (max 10MB)
      const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
      if (f.size > MAX_FILE_SIZE) {
        throw new Error(`File size (${(f.size / 1024 / 1024).toFixed(2)}MB) exceeds maximum allowed size of 10MB`);
      }

      // Validate file type
      const allowedExtensions = ['.pdf', '.docx', '.txt'];
      const fileExtension = '.' + f.name.split('.').pop().toLowerCase();
      
      if (!allowedExtensions.includes(fileExtension)) {
        throw new Error(`File type not supported. Please upload PDF, DOCX, or TXT files only.`);
      }

      let parsed = { filename: escapeHtml(f.name), raw_text: "" };

      if (f.name.toLowerCase().endsWith(".pdf")) {
        parsed.raw_text = await extractPDFText(f);
      } else if (f.name.toLowerCase().endsWith(".txt")) {
        parsed.raw_text = await f.text();
      } else {
        parsed.raw_text = await f.text();
      }

      // Store the file blob for autofill (convert to base64 for storage)
      // Use chunked conversion to avoid "Maximum call stack size exceeded" for large files
      const fileBlob = await f.arrayBuffer();
      const bytes = new Uint8Array(fileBlob);
      
      // Convert to base64 using safe chunked conversion
      // Build string chunk by chunk without using apply() to avoid stack overflow
      const chunkSize = 1024; // 1KB chunks
      const binaryParts = []; // Use array for better performance
      
      // Build binary string character by character in chunks for maximum safety
      for (let i = 0; i < bytes.length; i += chunkSize) {
        const chunkEnd = Math.min(i + chunkSize, bytes.length);
        // Build chunk string using array (faster than string concatenation)
        const chunkChars = [];
        for (let j = i; j < chunkEnd; j++) {
          chunkChars.push(String.fromCharCode(bytes[j]));
        }
        binaryParts.push(chunkChars.join(''));
      }
      const binary = binaryParts.join('');
      const base64 = btoa(binary);
      const fileData = {
        name: escapeHtml(f.name), // Sanitize filename
        type: f.type,
        size: f.size,
        data: base64  // Base64 encoded file data
      };

      await chrome.storage.local.set({ 
        parsed_resume: parsed,
        resume_file: fileData  // Store file for autofill
      });
      // Clear old score when new resume is uploaded (new resume = new scores needed)
      await chrome.storage.local.remove(["last_score_result", "last_score_jd_url"]);
      const safeFilename = escapeHtml(f.name);
      status.innerHTML = `<div class="success-message">✓ Resume saved: <strong>${safeFilename}</strong></div>`;
      console.log("📦 POPUP STORED PARSED RESUME:", parsed);
      console.log("📦 POPUP STORED RESUME FILE:", { name: f.name, size: f.size });
    } catch (err) {
      console.error(err);
      status.innerHTML = `<div class="error">Failed to parse resume: ${err.message}</div>`;
    }
  });

  // -------- CHECK SCORE (NON-BLOCKING) --------
  scoreBtn.addEventListener("click", async () => {
    console.log("📊 Get Resume Score button clicked");
    
    // If already polling, don't start another request
    if (pollingInterval) {
      console.log("⚠️ Already processing a request");
      status.innerHTML = `<div class="error">A request is already in progress. Please wait or cancel it.</div>`;
      return;
    }
    
    status.innerHTML = `<div class="loading"><div class="loading-spinner"></div><div>Starting analysis...</div></div>`;
    const { parsed_resume } = await chrome.storage.local.get("parsed_resume");
    
    if (!parsed_resume) {
      status.innerHTML = `<div class="error">Please upload your resume first</div>`;
      return;
    }

    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs && tabs[0];
      const jd_url = tab ? tab.url : null;

      if (!jd_url || !jd_url.includes("greenhouse.io")) {
        status.innerHTML = `<div class="error">Please navigate to a Greenhouse job page first</div>`;
        return;
      }

      if (!parsed_resume.raw_text) {
        status.innerHTML = `<div class="error">Resume text not found. Please re-upload your resume.</div>`;
        return;
      }

      console.log("📤 Sending to background:", {
        resume_length: parsed_resume.raw_text.length,
        jd_url: jd_url,
        filename: parsed_resume.filename
      });

      // Send to background - this returns immediately with requestId
      const bgResp = await sendBgMessage({
        type: "BG_RESUME_SCORE",
        payload: { parsed_resume, jd_url }
      });
      
      console.log("✅ Background acknowledged request:", bgResp);

      if (bgResp?.ok && bgResp.requestId) {
        // Start polling for results
        startPolling(bgResp.requestId);
        
        // Show initial loading UI
        updateLoadingUI("0s", formatTime(REQUEST_TIMEOUT));
      } else {
        status.innerHTML = `<div class="error">Failed to start request: ${bgResp?.error || 'Unknown error'}</div>`;
      }
      
    } catch (err) {
      console.warn("Score failed:", err);
      status.innerHTML = `<div class="error">Score failed: ${err.message || err}</div>`;
    }
  });

  // -------- AUTOFILL --------
  autofillBtn.addEventListener("click", async () => {
    console.log("✏️ Autofill button clicked");
    status.innerHTML = `<div class="loading"><div class="loading-spinner"></div><div>Preparing autofill...</div></div>`;
    const { parsed_resume, resume_file } = await chrome.storage.local.get(["parsed_resume", "resume_file"]);
    if (!parsed_resume) {
      status.innerHTML = `<div class="error">Please upload your resume first</div>`;
      return;
    }

    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs && tabs[0];
    if (!tab) {
      status.innerHTML = `<div class="error">No active tab found</div>`;
      return;
    }

    // Check if URL is a Greenhouse page
    if (!tab.url || !tab.url.includes("greenhouse.io")) {
      status.innerHTML = `<div class="error">Please navigate to a Greenhouse job application page first</div>`;
      return;
    }

    try {
      // First, verify content script is ready by sending a check message
      // Wait a bit for the module to load if it's still loading
      let contentScriptReady = false;
      
      // Try to check if content script is ready (with retries)
      for (let i = 0; i < 10; i++) { // Increased retries
        try {
          const checkResponse = await Promise.race([
            new Promise((res, rej) => {
              chrome.tabs.sendMessage(tab.id, { type: "CHECK_PAGE" }, (r) => {
                if (chrome.runtime.lastError) {
                  rej(chrome.runtime.lastError);
                } else {
                  res(r);
                }
              });
            }),
            new Promise((_, rej) => setTimeout(() => rej(new Error("Timeout")), 1000)) // 1s timeout
          ]);
          
          // If we got a response, content script is ready
          if (checkResponse && checkResponse.ok) {
            contentScriptReady = true;
            console.log("✅ Content script ready:", checkResponse);
            break;
          }
        } catch (err) {
          console.log(`⏳ Content script check attempt ${i + 1}/10 failed:`, err.message);
          if (i < 9) {
            // Wait longer between retries (300ms)
            await new Promise(resolve => setTimeout(resolve, 300));
          }
        }
      }

      // If content script still not ready, try to inject it programmatically
      if (!contentScriptReady) {
        console.log("⚠️ Content script not responding, attempting programmatic injection...");
        try {
          await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ["contentScript.js"]
          });
          console.log("✅ Content script injected programmatically");
          
          // Wait a bit for the injected script to load
          await new Promise(resolve => setTimeout(resolve, 500));
          
          // Try checking again after injection
          try {
            const checkResponse = await new Promise((res, rej) => {
              chrome.tabs.sendMessage(tab.id, { type: "CHECK_PAGE" }, (r) => {
                if (chrome.runtime.lastError) {
                  rej(chrome.runtime.lastError);
                } else {
                  res(r);
                }
              });
            });
            if (checkResponse && checkResponse.ok) {
              contentScriptReady = true;
              console.log("✅ Content script ready after injection");
            }
          } catch (err) {
            console.warn("⚠️ Content script still not ready after injection:", err);
          }
        } catch (injectErr) {
          console.error("❌ Failed to inject content script:", injectErr);
        }
      }

      if (!contentScriptReady) {
        status.innerHTML = `<div class="error">Content script not ready. Please refresh the page and try again.</div>`;
        return;
      }

      // Now send the autofill message (include resume file for upload)
      const resp = await new Promise((res, rej) => {
        chrome.tabs.sendMessage(tab.id, { 
          type: "AUTOFILL", 
          parsed_resume,
          resume_file: resume_file || null  // Include file data for autofill
        }, (r) => {
          if (chrome.runtime.lastError) {
            console.error("sendMessage error:", chrome.runtime.lastError);
            return rej(chrome.runtime.lastError);
          }
          res(r);
        });
      });

      if (resp?.status === "autofill_complete" || resp?.status === "autofill_partial") {
        status.innerHTML = `<div class="success-message">✓ Form autofilled! Please review and submit manually.</div>`;
      } else if (resp?.status === "error") {
        status.innerHTML = `<div class="error">Autofill error: ${resp?.message || 'Unknown error'}</div>`;
      } else {
        status.innerHTML = `<div class="success-message">✓ Autofill requested. Please check the form.</div>`;
      }
    } catch (err) {
      console.warn("sendMessage error:", err);
      status.innerHTML = `<div class="error">Content script not found. Make sure you're on a Greenhouse job page.</div>`;
    }
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener("DOMContentLoaded", initPopup);
} else {
  initPopup();
}





