// utils/detect.js
export function isGreenhouse(url) {
  try {
    const u = new URL(url);
    return u.hostname.endsWith("greenhouse.io") || u.hostname.endsWith("boards.greenhouse.io") || u.hostname.endsWith("job-boards.greenhouse.io");
  } catch (e) {
    return false;
  }
}

function getLabelForElement(el) {
  // Strategy 1: label[for]
  if (el.id) {
    const lab = document.querySelector(`label[for="${el.id}"]`);
    if (lab && lab.innerText && lab.innerText.trim()) {
      return lab.innerText.trim();
    }
  }
  // Strategy 2: closest parent label
  const parentLabel = el.closest("label");
  if (parentLabel && parentLabel.innerText && parentLabel.innerText.trim()) {
    return parentLabel.innerText.trim();
  }
  // Strategy 3: aria-labelledby
  const aria = el.getAttribute("aria-labelledby");
  if (aria) {
    const ai = document.getElementById(aria);
    if (ai && ai.innerText && ai.innerText.trim()) {
      return ai.innerText.trim();
    }
  }
  // Strategy 4: preceding sibling
  let prev = el.previousElementSibling;
  for (let i = 0; i < 4 && prev; i++, prev = prev.previousElementSibling) {
    if (prev.tagName.toLowerCase() === "label" && prev.innerText.trim()) {
      return prev.innerText.trim();
    }
    if (prev.innerText && prev.innerText.trim().length < 80) {
      // might be a div containing label text
      return prev.innerText.trim();
    }
  }
  // Strategy 5: placeholder / aria-label
  if (el.placeholder && el.placeholder.trim()) {
    return el.placeholder.trim();
  }
  if (el.getAttribute("aria-label")) {
    return el.getAttribute("aria-label").trim();
  }
  // Strategy 6: look for nearest heading or strong text above
  let node = el;
  for (let i = 0; i < 6; i++) {
    node = node.parentElement;
    if (!node) break;
    const heading = node.querySelector("h1,h2,h3,h4,strong,b");
    if (heading && heading.innerText && heading.innerText.trim()) {
      return heading.innerText.trim();
    }
  }
  // fallback
  return "(no-label)";
}

export function extractFields() {
  const selectors = Array.from(document.querySelectorAll("input, textarea, select"));
  const visible = selectors.filter(el => {
    const s = window.getComputedStyle(el);
    return s && s.display !== "none" && s.visibility !== "hidden" && el.offsetParent !== null;
  });

  const fields = visible.map(el => {
    return {
      tag: el.tagName.toLowerCase(),
      name: el.name || null,
      id: el.id || null,
      placeholder: el.placeholder || null,
      type: el.type || null,
      aria_label: el.getAttribute("aria-label") || null,
      label_text: getLabelForElement(el),
      element: null // do NOT serialize DOM element when sending to backend (we keep it for local autofill)
    };
  });

  // Remove duplicates (some pages render hidden duplicates)
  const seen = new Set();
  const out = [];
  for (const f of fields) {
    const key = `${f.id || ""}::${f.name || ""}::${f.label_text || ""}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(f);
    }
  }
  return out;
}


