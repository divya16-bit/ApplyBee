// contentScript.js (loader)
console.log("🔥 Loader injected");

(async () => {
  try {
    const moduleUrl = chrome.runtime.getURL("contentScriptModule.js");
    await import(moduleUrl);
    console.log("✨ Module loaded");
  } catch (err) {
    console.error("FAILED TO LOAD MODULE:", err);
  }
})();




