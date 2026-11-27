const site = SITE_CONFIG[location.hostname];
let lastBusy;
let lastUrl;
let timer;
let firstChange;
let active = true;

function report(type) {
  chrome.runtime.sendMessage({ type }).catch(() => {
    // Reloading the extension invalidates content scripts in already-open tabs.
    lastBusy = undefined;
  });
}

function check() {
  timer = undefined;
  firstChange = undefined;
  const selectors = site.selectors.join(",");
  const candidates = document.querySelectorAll(`${selectors},button[aria-label]`);
  const busy = Array.from(candidates).some((button) => {
    const label = (button.getAttribute("aria-label") || "").trim();
    return (button.matches(selectors) || site.label.test(label))
      && !site.ignoreLabel?.test(label)
      && !button.disabled
      && button.getClientRects().length > 0
      && getComputedStyle(button).visibility === "visible";
  });
  if (busy !== lastBusy || location.href !== lastUrl) {
    lastBusy = busy;
    lastUrl = location.href;
    report(busy ? "busy" : "idle");
  }
}

function scheduleCheck() {
  if (!active) return;
  const now = performance.now();
  firstChange ??= now;
  clearTimeout(timer);
  // A long stream of DOM mutations must still allow a check to run.
  timer = setTimeout(check, Math.max(0, Math.min(300, firstChange + 600 - now)));
}

new MutationObserver(scheduleCheck).observe(document.documentElement, {
  subtree: true,
  childList: true,
  attributes: true,
  attributeFilter: ["aria-label", "data-testid", "disabled", "hidden", "style", "class"],
});
window.navigation?.addEventListener("navigatesuccess", scheduleCheck);
window.addEventListener("pagehide", () => {
  active = false;
  clearTimeout(timer);
  firstChange = undefined;
  lastBusy = undefined;
  report("idle");
});
window.addEventListener("pageshow", () => {
  active = true;
  scheduleCheck();
});
scheduleCheck();
