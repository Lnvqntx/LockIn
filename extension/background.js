importScripts("sites.js");

const DEFAULTS = { enabled: true, port: 8765 };
const SOURCES = new Set(SUPPORTED_SITES);
const PING_INTERVAL = 20_000;
const MAX_RECONNECT_DELAY = 10_000;

let settings;
let busyTabs;
let socket;
let reconnectTimer;
let pingTimer;
let connectTimer;
let reconnectDelay = 500;

const ready = Promise.all([
  chrome.storage.local.get(DEFAULTS),
  chrome.storage.session.get({ busyTabs: [] }),
]).then(([saved, session]) => {
  settings = saved;
  busyTabs = new Map(session.busyTabs);
  connect();
});

function send(type, state) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(state ? { type, source: state.source, tab: state.tab } : { type }));
  }
}

function reconnect() {
  clearTimeout(reconnectTimer);
  if (!settings.enabled) return;
  reconnectTimer = setTimeout(async () => {
    // Refreshing settings also resets Chrome's service worker idle timer during backoff.
    await chrome.storage.local.get(DEFAULTS);
    connect();
  }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
}

function connect() {
  if (!settings.enabled || socket) return;
  let connection;
  try {
    connection = new WebSocket(`ws://127.0.0.1:${settings.port}`);
  } catch {
    reconnect();
    return;
  }
  socket = connection;
  connectTimer = setTimeout(() => connection.close(), 8_000);
  let lastPong = Date.now();

  connection.addEventListener("open", () => {
    if (socket !== connection) return;
    clearTimeout(connectTimer);
    reconnectDelay = 500;
    lastPong = Date.now();
    send("ping");
    for (const state of busyTabs.values()) send("busy", state);
    pingTimer = setInterval(() => {
      if (Date.now() - lastPong > 45_000) connection.close();
      else send("ping");
    }, PING_INTERVAL);
  });
  connection.addEventListener("message", ({ data }) => {
    if (socket !== connection) return;
    try {
      if (JSON.parse(data)?.type === "pong") lastPong = Date.now();
    } catch {
      // Ignore malformed replies.
    }
  });
  connection.addEventListener("close", () => {
    if (socket !== connection) return;
    socket = undefined;
    clearTimeout(connectTimer);
    clearInterval(pingTimer);
    reconnect();
  });
}

function restartConnection() {
  clearTimeout(reconnectTimer);
  clearTimeout(connectTimer);
  clearInterval(pingTimer);
  const oldSocket = socket;
  socket = undefined;
  oldSocket?.close();
  reconnectDelay = 500;
  connect();
}

function storeBusyTabs() {
  return chrome.storage.session.set({ busyTabs: [...busyTabs] });
}

function clearTab(tab, documentId) {
  const state = busyTabs.get(tab);
  if (!state || (documentId && state.documentId !== documentId)) return;
  busyTabs.delete(tab);
  send("idle", state);
  return storeBusyTabs();
}

function setBusy(tab, source, documentId) {
  const previous = busyTabs.get(tab);
  if (previous?.source === source && previous.documentId === documentId) return;
  const state = { tab, source, documentId };
  busyTabs.set(tab, state);
  send("busy", state);
  if (previous && previous.source !== source) send("idle", previous);
  return storeBusyTabs();
}

function snapshot() {
  return {
    ...settings,
    connected: socket?.readyState === WebSocket.OPEN,
    busyTabs: Array.from(busyTabs.values(), ({ tab, source }) => ({ tab, source })),
  };
}

async function handleMessage(message, sender) {
  await ready;
  if (!message || typeof message.type !== "string") return;
  if (sender.url === chrome.runtime.getURL("popup.html")) {
    if (message.type === "settings") {
      const { enabled, port } = message;
      if (typeof enabled !== "boolean" || !Number.isInteger(port) || port < 1 || port > 65535) {
        throw new Error("Enter a port from 1 to 65535.");
      }
      const changed = enabled !== settings.enabled || port !== settings.port;
      settings = { enabled, port };
      await chrome.storage.local.set(settings);
      if (changed) restartConnection();
    }
    if (message.type === "settings" || message.type === "status") return snapshot();
  }

  if (!sender.url || sender.frameId !== 0 || !Number.isInteger(sender.tab?.id)) return;
  const origin = new URL(sender.url);
  if (origin.protocol !== "https:" || !SOURCES.has(origin.hostname)) return;
  if (message.type === "busy" && sender.documentLifecycle === "active") {
    await setBusy(sender.tab.id, origin.hostname, sender.documentId);
  } else if (message.type === "idle") {
    await clearTab(sender.tab.id, sender.documentId);
  }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  handleMessage(message, sender).then(respond, (error) => respond({ error: error.message }));
  return true;
});
chrome.tabs.onRemoved.addListener((tab) => ready.then(() => clearTab(tab)));
chrome.tabs.onReplaced.addListener((_, removed) => ready.then(() => clearTab(removed)));
chrome.tabs.onUpdated.addListener((tab, change) => {
  if (change.status === "loading" || change.url) ready.then(() => clearTab(tab));
});
