'use strict';

const LOCAL_PORTS = Array.from({length: 10}, (_, i) => 8765 + i);
const LOCAL_HOST = 'http://127.0.0.1';
const MIN_INTERVAL_SECONDS = 120;
const VALUE_PROBE_NAVIGATION_DELAY_MS = 5000;
const WORK_TAB_FRAGMENT = '#simple-evaluator-worktab';
const NORMAL_SEARCH_URL = 'https://cfb.fan/27/players/#simple-evaluator-worktab';
const ALARM_PREFIX = 'simple-evaluator-watch:';
const HEARTBEAT_ALARM = 'simple-evaluator-helper-heartbeat';
const HEARTBEAT_SCHEMA = 'simple-evaluator-browser-helper-heartbeat-v1';
const HEALTH_SCHEMA = 'simple-evaluator-health-v1';
const LOCAL_REQUEST_TIMEOUT_MS = 1200;
let preferredPort = null;
let lastPageDiagnostic = null;

function browserFamily() {
  const ua = String((globalThis.navigator && navigator.userAgent) || '');
  if (/Edg\//.test(ua)) return 'edge';
  if (/OPR\//.test(ua)) return 'opera';
  if (/Chrome\//.test(ua)) return 'chrome';
  return 'chromium';
}

function fromCfbFan(sender) {
  const url = String(sender && sender.url || '');
  return url.startsWith('https://cfb.fan/');
}

function alarmName(tabId) {
  return `${ALARM_PREFIX}${tabId}`;
}

function tabIdFromAlarm(name) {
  if (!String(name).startsWith(ALARM_PREFIX)) return null;
  const n = Number(String(name).slice(ALARM_PREFIX.length));
  return Number.isInteger(n) && n >= 0 ? n : null;
}

function workTabUrl(value) {
  const raw = String(value || '');
  if (!raw.startsWith('https://cfb.fan/')) return raw;
  return NORMAL_SEARCH_URL;
}

async function fetchLocalJson(port, path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), LOCAL_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${LOCAL_HOST}:${port}${path}`, {
      cache: 'no-store',
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function callLocal(path, options = {}) {
  let lastError = null;
  const orderedPorts = preferredPort === null
    ? [...LOCAL_PORTS]
    : [preferredPort, ...LOCAL_PORTS.filter(port => port !== preferredPort)];
  for (const port of orderedPorts) {
    try {
      const health = await fetchLocalJson(port, '/health.json');
      if (!health || health.schema !== HEALTH_SCHEMA || health.ok !== true) {
        lastError = new Error('Unexpected local health response');
        continue;
      }
      const body = path === '/health.json' ? health : await fetchLocalJson(port, path, options);
      if (body && body.schema && String(body.schema).startsWith('simple-evaluator-')) {
        preferredPort = port;
        return body;
      }
      lastError = new Error('Unexpected local app response');
    } catch (error) {
      lastError = error;
      if (preferredPort === port) preferredPort = null;
    }
  }
  throw lastError || new Error('Simple Evaluator local server not found');
}


async function currentBrowserWork() {
  const saved = await callLocal('/browser-watch-next.json');
  if (saved && saved.active && saved.source_url) {
    return {...saved, work_kind: 'saved_watch'};
  }
  try {
    const probe = await callLocal('/value-probe-status.json');
    if (probe && probe.active && probe.current_card_id && probe.source_url) {
      return {
        schema: 'simple-evaluator-browser-work-queue-v1',
        ok: true,
        active: true,
        status: 'DUE',
        due_now: true,
        wait_seconds: 0,
        card_id: String(probe.current_card_id || ''),
        name: probe.current_name || null,
        ovr: probe.current_ovr || null,
        program: probe.current_program || null,
        watch_id: `value-probe-${String(probe.current_card_id || '')}`,
        source_url: String(probe.source_url || ''),
        total_active_card_watches: 1,
        work_kind: 'value_probe',
      };
    }
  } catch (_) {
    // Saved-watch work remains usable if the optional value-probe status is unavailable.
  }
  return saved;
}


async function sendHeartbeat() {
  const manifest = chrome.runtime.getManifest();
  try {
    return await callLocal('/browser-helper-heartbeat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({schema: HEARTBEAT_SCHEMA, version: String(manifest.version || ''), browser_family: browserFamily(), user_agent: String((globalThis.navigator && navigator.userAgent) || '').slice(0, 240), page_diagnostic: lastPageDiagnostic}),
    });
  } catch (_) {
    return null;
  }
}

async function ensureHeartbeatAlarm() {
  const existing = await chrome.alarms.get(HEARTBEAT_ALARM);
  if (!existing) await chrome.alarms.create(HEARTBEAT_ALARM, {periodInMinutes: 1});
  await sendHeartbeat();
}

chrome.runtime.onInstalled.addListener(() => { ensureHeartbeatAlarm(); });
chrome.runtime.onStartup.addListener(() => { ensureHeartbeatAlarm(); });
ensureHeartbeatAlarm();

async function scheduleTab(tabId, intervalSeconds, reset = false) {
  if (!Number.isInteger(tabId)) return null;
  const name = alarmName(tabId);
  const seconds = Math.max(5, Number(intervalSeconds) || MIN_INTERVAL_SECONDS);
  if (!reset) {
    const existing = await chrome.alarms.get(name);
    if (existing) return existing.scheduledTime;
  }
  const when = Date.now() + seconds * 1000;
  await chrome.alarms.create(name, {when});
  return when;
}

async function clearTabSchedule(tabId) {
  if (Number.isInteger(tabId)) await chrome.alarms.clear(alarmName(tabId));
}

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === HEARTBEAT_ALARM) { sendHeartbeat(); return; }
  const tabId = tabIdFromAlarm(alarm.name);
  if (tabId === null) return;
  chrome.tabs.get(tabId, async tab => {
    if (chrome.runtime.lastError || !tab || !String(tab.url || '').startsWith('https://cfb.fan/')) {
      await clearTabSchedule(tabId);
      return;
    }
    try {
      const next = await currentBrowserWork();
      if (!next.active || !next.source_url) {
        await clearTabSchedule(tabId);
        return;
      }
      const waitSeconds = Math.max(5, Number(next.wait_seconds) || 0);
      if (!next.due_now && waitSeconds > 5.25) {
        await scheduleTab(tabId, waitSeconds, true);
        return;
      }
      await clearTabSchedule(tabId);
      chrome.tabs.update(tabId, {url: workTabUrl(next.source_url)}, () => { void chrome.runtime.lastError; });
    } catch (_) {
      // Local app temporarily unavailable: retry only on the normal saved-watch cadence.
      await scheduleTab(tabId, MIN_INTERVAL_SECONDS, true);
    }
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!fromCfbFan(sender) || !message || typeof message !== 'object') {
    sendResponse({ok: false, error: 'Untrusted browser message'});
    return false;
  }
  const tabId = sender.tab && sender.tab.id;


  if (message.type === 'simple-evaluator:page-diagnostic') {
    const raw = message.diagnostic && typeof message.diagnostic === 'object' ? message.diagnostic : {};
    lastPageDiagnostic = {
      stage: String(raw.stage || '').slice(0, 80),
      url: String(raw.url || sender.url || '').slice(0, 500),
      observed_at: String(raw.observed_at || new Date().toISOString()).slice(0, 80),
      detail: String(raw.detail || '').slice(0, 500),
      price_label_count: Number.isFinite(Number(raw.price_label_count)) ? Number(raw.price_label_count) : null,
      overview_label_count: Number.isFinite(Number(raw.overview_label_count)) ? Number(raw.overview_label_count) : null,
      peer_label_count: Number.isFinite(Number(raw.peer_label_count)) ? Number(raw.peer_label_count) : null,
      selected: raw.selected && typeof raw.selected === 'object' ? raw.selected : null,
      market_state: raw.market_state ? String(raw.market_state).slice(0, 40) : null,
      price: Number.isFinite(Number(raw.price)) ? Number(raw.price) : null,
      listing_count: Number.isFinite(Number(raw.listing_count)) ? Number(raw.listing_count) : null,
      next_refresh_at: raw.next_refresh_at ? String(raw.next_refresh_at).slice(0, 80) : null,
    };
    sendHeartbeat().then(() => sendResponse({ok: true})).catch(() => sendResponse({ok: true}));
    return true;
  }

  if (message.type === 'simple-evaluator:get-browser-work') {
    currentBrowserWork()
      .then(result => sendResponse({ok: true, result}))
      .catch(error => sendResponse({ok: false, error: String(error && error.message || error)}));
    return true;
  }

  if (message.type === 'simple-evaluator:get-watch-config') {
    const pageUrl = encodeURIComponent(String(message.url || sender.url || ''));
    callLocal(`/browser-watch-config.json?url=${pageUrl}`)
      .then(async result => {
        if (result.active && !String(result.watch_id || '').startsWith('value-probe-')) result.next_refresh_at = await scheduleTab(tabId, result.interval_seconds, false);
        else await clearTabSchedule(tabId);
        sendResponse({ok: true, result});
      })
      .catch(error => sendResponse({ok: false, error: String(error && error.message || error)}));
    return true;
  }


  if (message.type === 'simple-evaluator:browser-work-stop') {
    clearTabSchedule(tabId)
      .then(() => sendResponse({ok: true, stopped: true, reason: String(message.reason || 'STOPPED').slice(0, 120)}))
      .catch(error => sendResponse({ok: false, error: String(error && error.message || error)}));
    return true;
  }

  if (message.type === 'simple-evaluator:value-probe-rate-limited') {
    callLocal('/value-probe-rate-limited', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_url: String(message.url || sender.url || ''), http_status: 429}),
    })
      .then(async result => {
        await clearTabSchedule(tabId);
        sendResponse({ok: true, result});
        setTimeout(() => {
          chrome.tabs.remove(tabId, () => { void chrome.runtime.lastError; });
        }, 900);
      })
      .catch(error => sendResponse({ok: false, error: String(error && error.message || error)}));
    return true;
  }

  if (message.type === 'simple-evaluator:browser-observation') {
    callLocal('/browser-observation', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({...message.observation, browser_family: browserFamily(), helper_version: String(chrome.runtime.getManifest().version || '')}),
    })
      .then(async result => {
        const probe = result && result.value_probe;
        const cycle = result && result.browser_cycle;
        if (probe) {
          await clearTabSchedule(tabId);
          sendResponse({ok: true, result});
          if (probe.next_source_url) {
            setTimeout(() => {
              chrome.tabs.update(tabId, {url: workTabUrl(probe.next_source_url)}, () => { void chrome.runtime.lastError; });
            }, VALUE_PROBE_NAVIGATION_DELAY_MS);
          } else if (probe.done && cycle && cycle.active && cycle.source_url) {
            const waitMs = Math.max(VALUE_PROBE_NAVIGATION_DELAY_MS, Math.ceil((Number(cycle.wait_seconds) || 0) * 1000));
            if (waitMs <= 30000) {
              setTimeout(() => {
                chrome.tabs.update(tabId, {url: workTabUrl(cycle.source_url)}, () => { void chrome.runtime.lastError; });
              }, waitMs);
            } else {
              await scheduleTab(tabId, Math.ceil(waitMs / 1000), true);
            }
          } else if (probe.done) {
            setTimeout(() => {
              chrome.tabs.remove(tabId, () => { void chrome.runtime.lastError; });
            }, 900);
          }
          return;
        }
        await clearTabSchedule(tabId);
        sendResponse({ok: true, result});
        if (cycle && cycle.active && cycle.source_url) {
          const waitMs = Math.max(VALUE_PROBE_NAVIGATION_DELAY_MS, Math.ceil((Number(cycle.wait_seconds) || 0) * 1000));
          if (waitMs <= 30000) {
            setTimeout(() => {
              chrome.tabs.update(tabId, {url: workTabUrl(cycle.source_url)}, () => { void chrome.runtime.lastError; });
            }, waitMs);
          } else {
            result.next_refresh_at = await scheduleTab(tabId, Math.ceil(waitMs / 1000), true);
          }
        }
      })
      .catch(error => sendResponse({ok: false, error: String(error && error.message || error)}));
    return true;
  }

  sendResponse({ok: false, error: 'Unknown browser message'});
  return false;
});
