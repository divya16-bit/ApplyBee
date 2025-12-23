// utils/autofill.js
export async function autofillFields(fields, answersMap, parsed_resume, resumeFile = null) {
  try {
    console.log("autofill: starting", fields.length, Object.keys(answersMap || {}).length);

    // helper to set value on element
    const setValue = async (el, val, resumeFile) => {
      try {
        if (!el) return false;
        // Handle file inputs - try to upload resume file
        if (el.type === "file") {
          if (resumeFile && resumeFile.data) {
            try {
              // Convert base64 back to blob
              const binaryString = atob(resumeFile.data);
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              const blob = new Blob([bytes], { type: resumeFile.type || 'application/pdf' });
              const file = new File([blob], resumeFile.name, { type: resumeFile.type || 'application/pdf' });
              
              // Create a DataTransfer object and set the file
              const dataTransfer = new DataTransfer();
              dataTransfer.items.add(file);
              el.files = dataTransfer.files;
              
              // Trigger change event
              el.dispatchEvent(new Event('change', { bubbles: true }));
              el.dispatchEvent(new Event('input', { bubbles: true }));
              
              console.log(`✅ File uploaded: ${resumeFile.name}`);
              return true;
            } catch (fileErr) {
              console.warn("⚠️ Could not programmatically set file:", fileErr);
              // Fallback: at least trigger click to help user
              el.click();
              return false;
            }
          } else {
            // No file available, trigger click to help user select
            console.log("ℹ️ No resume file available, triggering file picker");
            el.click();
            return false;
          }
        }
        if (el.tagName.toLowerCase() === "select") {
          // For select dropdowns, try multiple matching strategies
          const valLower = (val || "").toLowerCase().trim();
          const valNum = parseFloat(valLower);
          
          // Strategy 1: Exact text match (case-insensitive)
          let opt = Array.from(el.options).find(o => {
            const optText = (o.text || "").toLowerCase().trim();
            const optValue = (o.value || "").toLowerCase().trim();
            return optText === valLower || optValue === valLower || 
                   optText.includes(valLower) || valLower.includes(optText);
          });
          
          // Strategy 2: For numeric values (like YoE), try to match ranges
          if (!opt && !isNaN(valNum) && valNum > 0) {
            opt = Array.from(el.options).find(o => {
              const optText = (o.text || "").toLowerCase();
              // Extract numbers from option text (e.g., "5-7 years" -> [5, 7], "5 years" -> [5])
              const numbers = optText.match(/\d+/g);
              if (numbers) {
                const nums = numbers.map(n => parseInt(n));
                // Check if valNum falls within any range
                if (nums.length === 2) {
                  // Range like "5-7 years" or "5 to 7 years"
                  return valNum >= nums[0] && valNum <= nums[1];
                } else if (nums.length === 1) {
                  // Single number like "5 years" - match if within 2 years
                  return Math.abs(valNum - nums[0]) <= 2;
                }
              }
              // Also check if option text contains the number as a standalone word
              const numPattern = new RegExp(`\\b${valNum}\\b`);
              return numPattern.test(optText);
            });
          }
          
          // Strategy 3: For country/location fields, try word-by-word matching
          if (!opt && valLower.split(/\s+/).length > 1) {
            const valWords = valLower.split(/\s+/).filter(w => w.length > 2);
            opt = Array.from(el.options).find(o => {
              const optText = (o.text || "").toLowerCase();
              // Check if all significant words from value appear in option
              return valWords.every(word => optText.includes(word)) || 
                     optText.split(/\s+/).some(optWord => valWords.includes(optWord));
            });
          }
          
          // Strategy 4: Partial match as fallback
          if (!opt) {
            opt = Array.from(el.options).find(o => {
              const optText = (o.text || "").toLowerCase();
              return optText.includes(valLower) || valLower.includes(optText);
            });
          }
          
          if (opt) {
            el.value = opt.value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
          }
          return false;
        }
        el.focus();
        el.value = val;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      } catch (e) {
        return false;
      }
    };

    // helper find candidate element for a single field object
    const findElementForField = (fieldObj) => {
      const label = (fieldObj.label_text || "").toLowerCase();
      // 1. id or name contains label tokens
      if (fieldObj.id) {
        const el = document.getElementById(fieldObj.id);
        if (el) return el;
      }
      if (fieldObj.name) {
        const byName = document.querySelector(`[name="${fieldObj.name}"]`);
        if (byName) return byName;
      }
      // 2. find by placeholder/aria-label
      if (fieldObj.placeholder) {
        const el = Array.from(document.querySelectorAll('input,textarea,select')).find(e => (e.placeholder || "").toLowerCase().includes(fieldObj.placeholder.toLowerCase()));
        if (el) return el;
      }
      // 3. query by label text: find label with text and its control
      const labels = Array.from(document.querySelectorAll('label'));
      for (const lab of labels) {
        if ((lab.innerText || "").toLowerCase().includes(label)) {
          const forId = lab.getAttribute('for');
          if (forId) {
            const el = document.getElementById(forId);
            if (el) return el;
          }
          // maybe input inside label
          const inside = lab.querySelector('input,textarea,select');
          if (inside) return inside;
        }
      }
      // 4. fallback: nearest input with similar placeholder/aria-label
      const tokens = label.split(/\s+/).slice(0,4);
      const allInputs = Array.from(document.querySelectorAll('input,textarea,select')).filter(i => i.offsetParent !== null);
      // rank inputs by token overlap with id/name/placeholder/aria-label/label_text
      let best = null;
      let bestScore = 0;
      for (const i of allInputs) {
        const text = ((i.id||"") + " " + (i.name||"") + " " + (i.placeholder||"") + " " + (i.getAttribute('aria-label')||"")).toLowerCase();
        let score = 0;
        for (const t of tokens) {
          if (t && text.includes(t)) score += 1;
        }
        if (score > bestScore) {
          bestScore = score;
          best = i;
        }
      }
      if (best && bestScore > 0) return best;
      return null;
    };

    let filledCount = 0;
    for (const f of fields) {
      const lbl = f.label_text || f.aria_label || f.placeholder || f.name || f.id || "(no-label)";
      const candidateAnswer = answersMap[lbl] !== undefined ? answersMap[lbl] : (answersMap[lbl.trim()] || "");

      const el = findElementForField(f);
      if (!el) continue;

      // For file inputs, allow even without candidateAnswer (will use resumeFile)
      if (el.type === "file") {
        const ok = await setValue(el, "", resumeFile);
        if (ok) filledCount += 1;
        continue;
      }

      // For other fields, need candidateAnswer
      if (!candidateAnswer) continue;

      const val = (candidateAnswer || "").toString().trim();
      if (!val) continue;

      const ok = await setValue(el, val, resumeFile);
      if (ok) filledCount += 1;
    }

    // fallback: try to fill some common global fields by scanning keywords
    if (filledCount === 0 && parsed_resume) {
      const fallbackMap = {};
      if (parsed_resume.raw_text) {
        // extract email/phone quickly
        const em = parsed_resume.raw_text.match(/[\w\.-]+@[\w\.-]+\.\w+/);
        const ph = parsed_resume.raw_text.match(/(\+?\d{1,3}[\s-]?)?(\d{6,12})/);
        if (em) fallbackMap["email"] = em[0];
        if (ph) fallbackMap["phone"] = ph[0];
      }
      for (const f of fields) {
        const key = (f.label_text||"").toLowerCase();
        if (key.includes("email") && fallbackMap.email) {
          const el = document.getElementById(f.id) || document.querySelector(`[name="${f.name}"]`);
          if (el && setValue(el, fallbackMap.email)) filledCount++;
        }
        if (key.includes("phone") && fallbackMap.phone) {
          const el = document.getElementById(f.id) || document.querySelector(`[name="${f.name}"]`);
          if (el && setValue(el, fallbackMap.phone)) filledCount++;
        }
      }
    }

    console.log(`Autofill: filled ${filledCount} fields (fallback used: ${filledCount === 0})`);
    return filledCount > 0;
  } catch (e) {
    console.error("autofillFields error:", e);
    return false;
  }
}

export function fallbackFill(fields, parsed_resume) {
  console.log("⚡ fallbackFill some common fields from resume");
  const mapping = {};
  if (parsed_resume && parsed_resume.raw_text) {
    const txt = parsed_resume.raw_text;
    const em = txt.match(/[\w\.-]+@[\w\.-]+\.\w+/);
    const ph = txt.match(/(\+?\d{1,3}[\s-]?)?(\d{6,12})/);
    if (em) mapping.email = em[0];
    if (ph) mapping.phone = ph[0];
  }
  // try to fill email / phone
  for (const f of fields) {
    const key = (f.label_text||"").toLowerCase();
    if (key.includes("email") && mapping.email) {
      const el = document.getElementById(f.id) || document.querySelector(`[name="${f.name}"]`);
      if (el) {
        el.value = mapping.email;
        el.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
    if (key.includes("phone") && mapping.phone) {
      const el = document.getElementById(f.id) || document.querySelector(`[name="${f.name}"]`);
      if (el) {
        el.value = mapping.phone;
        el.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }
  }
  console.log("⚡ Fallback done");
}



