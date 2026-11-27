// Supported hostname list and per-site generation controls.
// These selectors are fixture-tested only. Check live sites when a Stop button changes.
const SITE_CONFIG = {
  // Claude's response stop button.
  "claude.ai": {
    selectors: ['button[aria-label="Stop response"]'],
    label: /^stop (?:response|generating|generation|streaming)$/i,
  },
  // ChatGPT and its legacy hostname share the same controls.
  "chatgpt.com": {
    selectors: ['button[data-testid="stop-button"]', 'button[aria-label*="Stop"]'],
    label: /^stop(?: (?:response|generating|generation|streaming))?$/i,
    ignoreLabel: /recording|reading|sharing|voice/i,
  },
  // Gemini's English accessibility label varies with the UI rollout.
  "gemini.google.com": {
    selectors: ['button[aria-label="Stop response"]', 'button[aria-label="Stop generating"]'],
    label: /^stop (?:response|generating|generation|streaming)$/i,
  },
};
SITE_CONFIG["chat.openai.com"] = SITE_CONFIG["chatgpt.com"];

const SUPPORTED_SITES = Object.keys(SITE_CONFIG);
