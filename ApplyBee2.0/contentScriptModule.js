// contentScriptModule.js
console.log("🔥 contentScriptModule running");

import { isGreenhouse, extractFields } from "./utils/detect.js";
import { autofillFields, fallbackFill } from "./utils/autofill.js";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("📩 ContentScript received:", msg);

  if (msg.type === "CHECK_PAGE") {
    sendResponse({ ok: true, url: window.location.href, isGreenhouse: isGreenhouse(window.location.href) });
    return;
  }

  if (msg.type === "RESUME_SCORE") {
    chrome.runtime.sendMessage({
      type: "BG_RESUME_SCORE",
      payload: { parsed_resume: msg.parsed_resume, jd_url: window.location.href }
    }, (resp) => {
      sendResponse(resp);
    });
    return true;
  }

  if (msg.type === "AUTOFILL") {
    // Use async/await pattern with proper response handling
    (async () => {
      try {
        const parsed_resume = msg.parsed_resume || {};
        const resume_file = msg.resume_file || null;
        console.log("🔎 AUTOFILL_REQUEST, parsed_resume present:", !!parsed_resume, "resume_file present:", !!resume_file);

        // 1) extract fields on the page (full objects)
        const fields = extractFields();
        console.log("📝 Extracted fields (objects):", fields);

        if (!fields || fields.length === 0) {
          console.warn("⚠️ No fields found on page");
          sendResponse({ status: "error", message: "No form fields found on this page" });
          return;
        }

        // Convert to simple label list for backend API
        const labels = fields.map(f => f.label_text || f.aria_label || f.placeholder || f.name || f.id || "(no-label)");

        // 2) call background to get gists
        const payload = {
          parsed_resume,
          job_description: "",
          job_url: window.location.href,
          fields: labels
        };

        // Use Promise wrapper for chrome.runtime.sendMessage
        const bgResp = await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage({ type: "BG_GENERATE_GISTS", payload }, (response) => {
            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else {
              resolve(response);
            }
          });
        });

        console.log("📤 Payload sending to background -> backend:", payload);
        if (!bgResp || !bgResp.ok) {
          console.warn("No gists received:", bgResp);
          fallbackFill(fields, parsed_resume);
          sendResponse({ status: "error", message: "No gists from backend" });
          return;
        }

        const answers = (bgResp.data && bgResp.data.answers) ? bgResp.data.answers : bgResp.data;
        console.log("📨 Answers from backend:", answers);

            // 3) perform autofill using utils/autofill.js (pass both field objects + answers mapping + resume file)
            const result = await autofillFields(fields, answers, parsed_resume, resume_file);
            console.log("✅ Autofill result:", result);
            sendResponse({ status: result ? "autofill_complete" : "autofill_partial" });
      } catch (err) {
        console.error("AUTOFILL error:", err);
        try {
          sendResponse({ status: "error", message: err.message || String(err) });
        } catch (e) {
          // Response channel might be closed, log it
          console.error("Failed to send error response:", e);
        }
      }
    })();
    return true; // keep response channel open for async response
  }
});

