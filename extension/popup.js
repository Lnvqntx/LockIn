const form = document.querySelector("form");
const enabled = document.querySelector("#enabled");
const port = document.querySelector("#port");
const save = document.querySelector("#save");
const status = document.querySelector("#status");
const tabs = document.querySelector("#tabs");
const error = document.querySelector("#error");
let savedPort;
let initialized = false;
let updating = false;

async function request(message) {
  const response = await chrome.runtime.sendMessage(message);
  if (!response || response.error) throw new Error(response?.error || "Extension worker unavailable.");
  return response;
}

function render(snapshot) {
  enabled.checked = snapshot.enabled;
  if (!initialized) port.value = snapshot.port;
  savedPort = snapshot.port;
  if (!initialized) {
    enabled.disabled = port.disabled = save.disabled = false;
    initialized = true;
  }
  status.textContent = snapshot.enabled
    ? (snapshot.connected ? "Connected" : "Not connected")
    : "Disabled";
  const items = snapshot.busyTabs.map(({ tab, source }) => `${source} · Tab ${tab}`);
  tabs.replaceChildren(...(items.length ? items : ["None"]).map((text) => {
    const li = document.createElement("li");
    li.textContent = text;
    return li;
  }));
}

async function refresh() {
  if (updating) return;
  try {
    const snapshot = await request({ type: "status" });
    if (!updating) render(snapshot);
  } catch (cause) {
    error.textContent = cause.message;
  }
}

async function update(nextPort) {
  updating = true;
  error.textContent = "";
  enabled.disabled = port.disabled = save.disabled = true;
  try {
    render(await request({ type: "settings", enabled: enabled.checked, port: nextPort }));
  } catch (cause) {
    error.textContent = cause.message;
  } finally {
    enabled.disabled = port.disabled = save.disabled = false;
    updating = false;
  }
}

enabled.addEventListener("change", () => update(savedPort));
form.addEventListener("submit", (event) => {
  event.preventDefault();
  update(port.valueAsNumber);
});
refresh();
setInterval(refresh, 1000);
