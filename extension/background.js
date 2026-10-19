// PHI Companion: reports the active tab's hostname to the local PHI app.
// Privacy: never sends full URLs, titles or page content. Skips incognito content entirely.

const ENDPOINT = "http://127.0.0.1:47615/v1/heartbeat";
const BEAT_MS = 4000;

const swipes = new Map(); // tabId -> Shorts watched in this tab

function isShortsUrl(u) {
  try {
    const url = new URL(u);
    return /(^|\.)youtube\.com$/.test(url.hostname) && url.pathname.startsWith("/shorts/");
  } catch {
    return false;
  }
}

function hostOf(u) {
  try {
    const url = new URL(u);
    return url.protocol === "http:" || url.protocol === "https:" ? url.hostname : "";
  } catch {
    return "";
  }
}

async function activeTab() {
  const win = await chrome.windows.getLastFocused();
  if (!win || !win.focused) return { focused: false };
  const [tab] = await chrome.tabs.query({ active: true, windowId: win.id });
  return { focused: true, tab };
}

async function runCommands(commands) {
  for (const cmd of commands || []) {
    if (cmd.type !== "close") continue;
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab || !tab.url) continue;
    const matches = cmd.match === "shorts"
      ? isShortsUrl(tab.url)
      : hostOf(tab.url) === cmd.match || hostOf(tab.url).endsWith("." + cmd.match);
    if (matches) chrome.tabs.remove(tab.id);
  }
}

async function beat() {
  try {
    const { focused, tab } = await activeTab();
    const body = { active: false, host: "", shorts: false, swipes: 0, audible: false, incognito: false, tabId: 0 };
    if (focused && tab) {
      body.active = true;
      body.incognito = !!tab.incognito;
      body.tabId = tab.id;
      body.audible = !!tab.audible;
      if (!tab.incognito && tab.url) {
        body.host = hostOf(tab.url);
        body.shorts = isShortsUrl(tab.url);
        body.swipes = swipes.get(tab.id) || 0;
      }
    }
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-PHI": "1" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    chrome.action.setBadgeText({ text: "" });
    chrome.action.setTitle({ title: "PHI Companion: connected" });
    await runCommands(data.commands);
  } catch {
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#E53935" });
    chrome.action.setTitle({ title: "PHI Companion: PHI app is not running" });
  }
}

// Calling extension APIs every few seconds keeps the service worker alive;
// the alarm is a safety net that restarts the loop if the worker was suspended.
let timer = null;
function start() {
  if (timer) return;
  beat();
  timer = setInterval(beat, BEAT_MS);
}

chrome.alarms.create("phi-keepalive", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(start);
chrome.runtime.onStartup.addListener(start);
chrome.runtime.onInstalled.addListener(start);
chrome.tabs.onActivated.addListener(beat);
chrome.windows.onFocusChanged.addListener(beat);
chrome.tabs.onRemoved.addListener((id) => swipes.delete(id));
chrome.runtime.onMessage.addListener((msg, sender) => {
  if (msg && msg.type === "swipes" && sender.tab) swipes.set(sender.tab.id, msg.count | 0);
});
start();
