// background.js
console.log("🔥 Background script running");

const BACKEND_BASE = "https://applybee.up.railway.app";

// ============ TIMEOUT CONFIGURATION ============
const REQUEST_TIMEOUT = 2 * 60 * 1000; // 2 minutes in milliseconds
const KEEP_ALIVE_INTERVAL = 20 * 1000;  // Ping every 20 seconds

// ============ KEEP SERVICE WORKER ALIVE ============
let keepAliveInterval = null;
let keepAliveCount = 0;

function startKeepAlive() {
  if (keepAliveInterval) return;
  
  keepAliveCount = 0;
  console.log("🔄 Starting keep-alive (15 min timeout)...");
  
  keepAliveInterval = setInterval(() => {
    keepAliveCount++;
    const elapsed = Math.round((keepAliveCount * KEEP_ALIVE_INTERVAL) / 1000);
    console.log(`💓 Keep-alive ping #${keepAliveCount} (${elapsed}s elapsed)`);
    
    // Multiple methods to keep service worker alive
    chrome.runtime.getPlatformInfo(() => {});
    
    // Also ping storage to ensure activity
    chrome.storage.local.get("keep_alive_ping", () => {
      chrome.storage.local.set({ keep_alive_ping: Date.now() });
    });
    
  }, KEEP_ALIVE_INTERVAL);
}

function stopKeepAlive() {
  if (keepAliveInterval) {
    clearInterval(keepAliveInterval);
    keepAliveInterval = null;
    console.log(`🛑 Stopped keep-alive after ${keepAliveCount} pings`);
    keepAliveCount = 0;
  }
}

// ============ REQUEST STATE MANAGEMENT ============
const pendingRequests = new Map();

async function saveRequestState(requestId, state) {
  try {
    await chrome.storage.local.set({ [`request_${requestId}`]: state });
    console.log(`💾 Saved request state: ${requestId} -> ${state.status}`);
  } catch (e) {
    console.error("Failed to save request state:", e);
  }
}

async function getRequestState(requestId) {
  try {
    const result = await chrome.storage.local.get(`request_${requestId}`);
    return result[`request_${requestId}`] || null;
  } catch (e) {
    console.error("Failed to get request state:", e);
    return null;
  }
}

async function clearRequestState(requestId) {
  try {
    await chrome.storage.local.remove(`request_${requestId}`);
    console.log(`🧹 Cleared request state: ${requestId}`);
  } catch (e) {
    console.error("Failed to clear request state:", e);
  }
}

// ============ FETCH WITH TIMEOUT (20 MINUTES) ============
async function fetchWithTimeout(url, options = {}, timeout = REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    console.log(`⏰ Request timeout after ${timeout / 1000}s`);
    controller.abort();
  }, timeout);
  
  options.signal = controller.signal;

  console.log(`🌐 Starting fetch to ${url} (timeout: ${timeout / 1000}s)`);
  const startTime = Date.now();

  try {
    const res = await fetch(url, options);
    clearTimeout(timeoutId);
    
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    console.log(`✅ Fetch completed in ${elapsed}s, status: ${res.status}`);
    
    const contentType = res.headers.get("content-type") || "";
    let data;
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      data = await res.text();
    }
    return { ok: res.ok, status: res.status, data };
    
  } catch (err) {
    clearTimeout(timeoutId);
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    
    if (err.name === 'AbortError') {
      console.error(`❌ Request aborted after ${elapsed}s`);
      return { ok: false, error: `Request timed out after ${elapsed} seconds` };
    }
    
    console.error(`❌ Fetch error after ${elapsed}s:`, err);
    return { ok: false, error: err.message || err.toString() };
  }
}

// ============ RESUME SCORE REQUEST HANDLER ============
async function handleResumeScoreRequest(requestId, payload) {
  const parsed_resume = payload.parsed_resume || {};
  const resume_text = parsed_resume.raw_text || "";
  const jd_url = payload.jd_url || "";

  console.log("═══════════════════════════════════════════");
  console.log("🟢 Starting /resume-score request");
  console.log("📋 Request ID:", requestId);
  console.log("📄 Resume length:", resume_text.length, "chars");
  console.log("🔗 JD URL:", jd_url);
  console.log("⏱️ Timeout:", REQUEST_TIMEOUT / 1000, "seconds");
  console.log("═══════════════════════════════════════════");

  const requestBody = {
    parsed_resume: parsed_resume,
    jd_url: jd_url
  };

  // Start keep-alive BEFORE the fetch
  startKeepAlive();

  // Update state to processing
  await saveRequestState(requestId, {
    status: 'processing',
    startTime: Date.now(),
    jd_url: jd_url
  });

  const startTime = Date.now();

  try {
    const res = await fetchWithTimeout(
      `${BACKEND_BASE}/resume-score`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody)
      },
      REQUEST_TIMEOUT
    );

    const elapsed = Math.round((Date.now() - startTime) / 1000);

    if (!res.ok) {
      console.warn(`❌ Backend /resume-score error after ${elapsed}s:`, res);
      await saveRequestState(requestId, {
        status: 'error',
        error: res.data || res.error || 'Unknown error',
        completedTime: Date.now(),
        elapsed: elapsed
      });
      return { ok: false, status: res.status, data: res.data || res.error };
    }

    // Success - save result
    console.log(`✅ Backend /resume-score success after ${elapsed}s`);
    await saveRequestState(requestId, {
      status: 'complete',
      data: res.data,
      completedTime: Date.now(),
      elapsed: elapsed
    });

    return { ok: true, status: res.status, data: res.data };

  } catch (e) {
    const elapsed = Math.round((Date.now() - startTime) / 1000);
    console.error(`❌ Background fetch failed after ${elapsed}s:`, e);
    
    await saveRequestState(requestId, {
      status: 'error',
      error: e.message || e.toString(),
      completedTime: Date.now(),
      elapsed: elapsed
    });
    
    return { ok: false, error: e.message || e.toString() };

  } finally {
    stopKeepAlive();
    pendingRequests.delete(requestId);
    console.log("═══════════════════════════════════════════");
    console.log("🏁 Request completed:", requestId);
    console.log("═══════════════════════════════════════════");
  }
}

// ============ MESSAGE LISTENER ============
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("📩 Background received:", msg.type);

  // -------- GENERATE GISTS --------
  if (msg.type === "BG_GENERATE_GISTS") {
    (async () => {
      try {
        startKeepAlive();
        const payload = msg.payload || {};
        const url = `${BACKEND_BASE}/get-gist`;
        console.log("🟢 Calling backend /get-gist", url);

        const res = await fetchWithTimeout(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume: payload.parsed_resume?.raw_text || payload.parsed_resume || "",
            jd: payload.job_description || "",
            labels: payload.fields || payload.labels || []
          })
        }, REQUEST_TIMEOUT);

        stopKeepAlive();

        if (!res.ok) {
          console.warn("❌ Backend /get-gist error:", res);
          sendResponse({ ok: false, status: res.status, data: res.data || res.error });
          return;
        }

        sendResponse({ ok: true, status: res.status, data: res.data });
      } catch (e) {
        stopKeepAlive();
        console.error("background fetch failed:", e);
        sendResponse({ ok: false, error: e.message || e.toString() });
      }
    })();
    return true;
  }

  // -------- START RESUME SCORE (Non-blocking) --------
  if (msg.type === "BG_RESUME_SCORE") {
    const requestId = `score_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    console.log("🆕 New resume score request:", requestId);
    
    // Store reference to pending request
    pendingRequests.set(requestId, { startTime: Date.now() });
    
    // Start the async operation WITHOUT waiting for it
    handleResumeScoreRequest(requestId, msg.payload || {})
      .then(result => {
        console.log(`✅ Request ${requestId} completed:`, result.ok ? 'success' : 'failed');
        
        // Try to notify popup if it's still listening
        chrome.runtime.sendMessage({
          type: "SCORE_RESULT",
          requestId: requestId,
          result: result
        }).catch(() => {
          console.log("📭 Popup not available, result saved to storage");
        });
      })
      .catch(err => {
        console.error(`❌ Request ${requestId} error:`, err);
      });

    // Immediately respond with request ID
    sendResponse({ 
      ok: true, 
      requestId: requestId,
      status: 'processing',
      message: 'Request started. Polling for results...',
      timeout: REQUEST_TIMEOUT
    });
    return true;
  }

  // -------- CHECK REQUEST STATUS --------
  if (msg.type === "CHECK_REQUEST_STATUS") {
    (async () => {
      const { requestId } = msg;
      const state = await getRequestState(requestId);
      
      if (!state) {
        // Check if it's still in pending requests (in memory)
        if (pendingRequests.has(requestId)) {
          const pending = pendingRequests.get(requestId);
          const elapsed = Date.now() - pending.startTime;
          sendResponse({ 
            status: 'processing',
            elapsed: elapsed,
            message: `Processing for ${Math.round(elapsed / 1000)}s...`
          });
        } else {
          sendResponse({ status: 'not_found' });
        }
        return;
      }
      
      if (state.status === 'complete') {
        await clearRequestState(requestId);
        sendResponse({ 
          status: 'complete', 
          ok: true,
          data: state.data,
          elapsed: state.elapsed
        });
      } else if (state.status === 'error') {
        await clearRequestState(requestId);
        sendResponse({ 
          status: 'error', 
          ok: false,
          error: state.error,
          elapsed: state.elapsed
        });
      } else {
        // Still processing
        const elapsed = Date.now() - state.startTime;
        sendResponse({ 
          status: 'processing',
          elapsed: elapsed,
          message: `Processing for ${Math.round(elapsed / 1000)}s...`
        });
      }
    })();
    return true;
  }

  // -------- CANCEL REQUEST --------
  if (msg.type === "CANCEL_REQUEST") {
    (async () => {
      const { requestId } = msg;
      console.log("🚫 Cancelling request:", requestId);
      await clearRequestState(requestId);
      pendingRequests.delete(requestId);
      stopKeepAlive();
      sendResponse({ ok: true });
    })();
    return true;
  }

  return false;
});

// ============ CLEANUP ON STARTUP ============
chrome.runtime.onStartup.addListener(async () => {
  console.log("🚀 Extension started, cleaning up old requests...");
  const all = await chrome.storage.local.get(null);
  const oldRequests = Object.keys(all).filter(k => k.startsWith('request_'));
  if (oldRequests.length > 0) {
    await chrome.storage.local.remove(oldRequests);
    console.log(`🧹 Cleaned up ${oldRequests.length} old request states`);
  }
});

// ============ HANDLE SERVICE WORKER TERMINATION ============
// This helps recover from unexpected terminations
self.addEventListener('activate', (event) => {
  console.log("🔄 Service worker activated");
});

self.addEventListener('install', (event) => {
  console.log("📦 Service worker installed");
  self.skipWaiting();
});








/*
// background.js
console.log("🔥 Background script running");

const BACKEND_BASE = "https://applybee.up.railway.app"; // update if needed

// helper with timeout (milliseconds)
async function fetchWithTimeout(url, options = {}, timeout = 300000) { // default 5 minutes
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  options.signal = controller.signal;

  try {
    const res = await fetch(url, options);
    clearTimeout(id);
    const contentType = res.headers.get("content-type") || "";
    let data;
    if (contentType.includes("application/json")) {
      data = await res.json();
    } else {
      data = await res.text();
    }
    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    clearTimeout(id);
    return { ok: false, error: err.message || err.toString() };
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("📩 Background received:", msg);

  if (msg.type === "BG_GENERATE_GISTS") {
    (async () => {
      try {
        const payload = msg.payload || {};
        const url = `${BACKEND_BASE}/get-gist`;
        console.log("🟢 Calling backend /get-gist", url, payload);

        const res = await fetchWithTimeout(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume: payload.parsed_resume?.raw_text || payload.parsed_resume || "",
            jd: payload.job_description || "",
            labels: payload.fields || payload.labels || []
          })
        }, 300000); // 5 minutes

        if (!res.ok) {
          console.warn("❌ Backend /get-gist error:", res);
          sendResponse({ ok: false, status: res.status, data: res.data || res.error });
          return;
        }

        // success
        sendResponse({ ok: true, status: res.status, data: res.data });
      } catch (e) {
        console.error("background fetch failed:", e);
        sendResponse({ ok: false, error: e.message || e.toString() });
      }
    })();
    return true; // keep response channel open
  }

  if (msg.type === "BG_RESUME_SCORE") {
    (async () => {
      try {
        const payload = msg.payload || {};
        const url = `${BACKEND_BASE}/resume-score`;
        
        // Extract resume data - parsed_resume is an object with { filename, raw_text }
        const parsed_resume = payload.parsed_resume || {};
        const resume_text = parsed_resume.raw_text || "";
        const jd_url = payload.jd_url || "";
        
        console.log("🟢 Calling backend /resume-score", url);
        console.log("📤 Sending payload:", {
          has_resume: !!resume_text,
          resume_length: resume_text.length,
          jd_url: jd_url,
          filename: parsed_resume.filename || "unknown"
        });

        const requestBody = {
          parsed_resume: parsed_resume, // Send full object with filename and raw_text
          jd_url: jd_url
        };

        const res = await fetchWithTimeout(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody)
        }, 300000); // 5 minutes

        if (!res.ok) {
          console.warn("❌ Backend /resume-score error:", res);
          sendResponse({ ok: false, status: res.status, data: res.data || res.error });
          return;
        }

        sendResponse({ ok: true, status: res.status, data: res.data });
      } catch (e) {
        console.error("background fetch failed:", e);
        sendResponse({ ok: false, error: e.message || e.toString() });
      }
    })();
    return true;
  }

});

*/


