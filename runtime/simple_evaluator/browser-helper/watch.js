(() => {
  'use strict';

  const MIN_INTERVAL_SECONDS = 120;
  const WATCH_RECHECK_MS = 5000;
  const MIN_PAGE_DWELL_MS = 5000;
  const MARKET_WAIT_MS = 45000;
  const MARKET_SCAN_MS = 500;
  const MARKET_RETRY_MS = 5000;
  const MARKET_SCROLL_INTERVAL_MS = 2500;

  function normalizedText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function textOf(el) {
    return normalizedText(el && (el.innerText || el.textContent));
  }

  function numberFromMoneyText(value) {
    const raw = normalizedText(value).replace(/\$/g, '');
    const matches = raw.match(/\b\d[\d,]*\b/g) || [];
    for (const match of matches) {
      const n = Number(match.replace(/,/g, ''));
      if (Number.isFinite(n) && n > 0) return n;
    }
    return null;
  }

  function apiFailureStatusFromText(value) {
    const match = normalizedText(value).match(/\bAPI\s+failed\s+with\s+status\s+(\d{3})\b/i);
    return match ? Number(match[1]) : null;
  }


  function headingsInOrder() {
    return [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')].filter(visibleElement);
  }

  function deepestExactTextElements(pattern) {
    const nodes = [...document.querySelectorAll('body *')].filter(el => visibleElement(el) && pattern.test(textOf(el)));
    return nodes.filter(el => ![...el.children].some(child => visibleElement(child) && pattern.test(textOf(child))));
  }

  function playStationHeading() {
    return headingsInOrder().find(h => /playstation\s+live\s+auctions/i.test(textOf(h)))
      || deepestExactTextElements(/^playstation\s+live\s+auctions$/i)[0]
      || null;
  }

  function nextHeadingAfter(target) {
    const headings = headingsInOrder();
    const index = headings.indexOf(target);
    return index >= 0 ? (headings[index + 1] || null) : null;
  }

  function isAfter(a, b) {
    return Boolean(a && b && (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));
  }

  function beforeBoundary(node, boundary) {
    return !boundary || Boolean(node.compareDocumentPosition(boundary) & Node.DOCUMENT_POSITION_FOLLOWING);
  }

  function firstSectionElementAfter(heading, selector) {
    const boundary = nextHeadingAfter(heading);
    return [...document.querySelectorAll(selector)].find(el => visibleElement(el) && isAfter(heading, el) && beforeBoundary(el, boundary)) || null;
  }

  function tableBuyNowColumn(table) {
    const headers = [...table.querySelectorAll('thead th')];
    if (!headers.length) return -1;
    let index = headers.findIndex(h => /buy\s*now/i.test(textOf(h)));
    if (index < 0) index = headers.findIndex(h => /^price$/i.test(textOf(h)));
    return index;
  }

  function buyNowFromRow(row, columnIndex) {
    const cells = [...row.querySelectorAll('td')];
    if (!cells.length) return null;
    if (columnIndex >= 0 && columnIndex < cells.length) {
      return numberFromMoneyText(textOf(cells[columnIndex]));
    }
    for (const cell of cells) {
      const label = `${cell.getAttribute('data-label') || ''} ${cell.getAttribute('aria-label') || ''}`;
      if (/buy\s*now/i.test(label)) {
        const value = numberFromMoneyText(textOf(cell));
        if (value) return value;
      }
    }
    const rowText = textOf(row);
    const labelled = rowText.match(/buy\s*now(?:\s*price)?\s*[:$]?\s*([\d,]+)/i);
    return labelled ? Number(labelled[1].replace(/,/g, '')) : null;
  }

  function parsePlayStationMarket() {
    const pageText = document.body ? (document.body.innerText || document.body.textContent || '') : '';
    const apiStatus = apiFailureStatusFromText(pageText);
    if (apiStatus === 429) return {state: 'RATE_LIMITED', reason: 'CFB.FAN price API returned HTTP 429'};
    if (apiStatus) return {state: 'SOURCE_ERROR', reason: `CFB.FAN price API returned HTTP ${apiStatus}`};
    const heading = playStationHeading();
    if (!heading) return {state: 'WAITING', reason: 'PlayStation Live Auctions heading not present yet'};
    const boundary = nextHeadingAfter(heading);
    const loading = [...document.querySelectorAll('*')].find(el => {
      const t = textOf(el);
      return visibleElement(el) && /^loading(?:\.\.\.)?$/i.test(t) && isAfter(heading, el) && beforeBoundary(el, boundary);
    });
    if (loading) return {state: 'WAITING', reason: 'PlayStation Live Auctions still loading'};

    const table = firstSectionElementAfter(heading, 'table');
    if (table) {
      const rows = [...table.querySelectorAll('tbody tr')].filter(row => visibleElement(row) && row.querySelectorAll('td').length > 0);
      const columnIndex = tableBuyNowColumn(table);
      const prices = rows.map(row => buyNowFromRow(row, columnIndex)).filter(n => Number.isFinite(n) && n > 0);
      if (prices.length) {
        prices.sort((a, b) => a - b);
        return {
          state: 'FOUND',
          price: prices[0],
          listing_count: prices.length,
          other_buy_now_prices: prices.slice(1),
        };
      }
      const emptyCells = [...table.querySelectorAll('td')].filter(visibleElement);
      if (emptyCells.some(cell => /^no\s+data\s+available\.?$/i.test(textOf(cell)))) return {state: 'NO_LISTING', listing_count: 0};
      if (rows.length) return {state: 'PARSE_ERROR', reason: 'Auction rows found but Buy Now prices could not be read safely'};
    }

    const noData = [...document.querySelectorAll('body *')].find(el => {
      const t = textOf(el);
      return visibleElement(el) && /^no\s+data\s+available\.?$/i.test(t) && isAfter(heading, el) && beforeBoundary(el, boundary);
    });
    if (noData) return {state: 'NO_LISTING', listing_count: 0};
    return {state: 'WAITING', reason: 'PlayStation auction result not present yet'};
  }

  function runtimeMessage(message) {
    return new Promise(resolve => {
      try {
        chrome.runtime.sendMessage(message, response => {
          const err = chrome.runtime.lastError;
          if (err) resolve({ok: false, error: err.message});
          else resolve(response || {ok: false, error: 'No extension response'});
        });
      } catch (error) {
        resolve({ok: false, error: String(error && error.message || error)});
      }
    });
  }

  async function getWatchConfig() {
    const response = await runtimeMessage({
      type: 'simple-evaluator:get-watch-config',
      url: location.href,
    });
    if (!response.ok) return {active: false, error: response.error || 'Local app unavailable'};
    return response.result || {active: false};
  }


  async function getBrowserWork() {
    const response = await runtimeMessage({type: 'simple-evaluator:get-browser-work'});
    if (!response.ok) return {active: false, error: response.error || 'Local app unavailable'};
    return response.result || {active: false};
  }

  function normalizedCardUrl(value) {
    try {
      const url = new URL(String(value || ''), location.origin);
      if (url.origin !== 'https://cfb.fan') return '';
      let path = url.pathname || '/';
      if (!path.endsWith('/')) path += '/';
      return url.origin + path;
    } catch (_) {
      return '';
    }
  }

  function isNormalSearchPage() {
    let path = location.pathname || '/';
    if (!path.endsWith('/')) path += '/';
    return path === '/27/players/';
  }

  function setFormValue(el, value) {
    if (!el) return;
    const raw = String(value == null ? '' : value);
    const proto = el instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
    if (descriptor && typeof descriptor.set === 'function') descriptor.set.call(el, raw);
    else el.value = raw;
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }

  function exactRenderedResult(work) {
    const expected = normalizedCardUrl(work && work.source_url);
    if (!expected) return {link: null, matches: [], reason: 'work item has no valid exact source identity'};
    const matches = [...document.querySelectorAll('a[href]')].filter(link => {
      return normalizedCardUrl(link.href) === expected;
    });
    const visible = matches.filter(visibleElement);
    if (visible.length === 1) return {link: visible[0], matches, reason: ''};
    if (visible.length > 1) return {link: null, matches, reason: 'multiple visible exact-card result links'};
    if (matches.length === 1) return {link: matches[0], matches, reason: ''};
    return {link: null, matches, reason: matches.length ? 'exact-card result is duplicated but not uniquely visible' : 'exact-card result not present'};
  }

  function exactApplyFiltersButton() {
    const matches = [...document.querySelectorAll('button,input[type="submit"],input[type="button"]')].filter(el => {
      const label = el.tagName === 'INPUT' ? String(el.value || '') : textOf(el);
      return visibleElement(el) && /^apply\s+filters$/i.test(label.trim());
    });
    return matches.length === 1 ? matches[0] : null;
  }

  async function driveNormalSearch(work) {
    if (!isNormalSearchPage()) return false;
    if (!work || !work.active || !work.source_url || !work.card_id || !work.name) {
      mark('normal-search-inactive', 'No active exact-card work item is available');
      return true;
    }

    const exact = exactRenderedResult(work);
    if (exact.link) {
      sessionStorage.removeItem('simpleEvaluatorNormalSearchWork');
      mark('normal-search-result-selected', String(work.card_id || ''));
      publishPageDiagnostic('normal-search-result-selected', {
        detail: String(work.card_id || ''),
        selected: describeElement(exact.link),
      });
      exact.link.click();
      return true;
    }

    const nameInput = document.querySelector('#f_name');
    const minOvr = document.querySelector('#f_overall__gte');
    const maxOvr = document.querySelector('#f_overall__lte');
    const apply = exactApplyFiltersButton();
    if (!nameInput || !apply) {
      const detail = 'Normal CFB.FAN player search controls are not uniquely available';
      mark('normal-search-controls-missing', detail);
      publishPageDiagnostic('normal-search-controls-missing', {detail});
      await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: 'normal-search-controls-missing'});
      return true;
    }

    const markerKey = 'simpleEvaluatorNormalSearchWork';
    let prior = null;
    try { prior = JSON.parse(sessionStorage.getItem(markerKey) || 'null'); } catch (_) {}
    const sameRecent = prior && prior.card_id === String(work.card_id) && (Date.now() - Number(prior.submitted_at || 0)) < 20000;
    if (sameRecent) {
      const detail = `Normal search completed but exact rendered card ${String(work.card_id)} was not found uniquely`;
      mark('normal-search-exact-result-missing', detail);
      publishPageDiagnostic('normal-search-exact-result-missing', {
        detail,
        expected_source_url: normalizedCardUrl(work.source_url),
        exact_match_count: exact.matches.length,
      });
      await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: 'normal-search-exact-result-missing'});
      return true;
    }

    setFormValue(nameInput, work.name);
    if (minOvr && work.ovr != null) setFormValue(minOvr, work.ovr);
    if (maxOvr && work.ovr != null) setFormValue(maxOvr, work.ovr);
    sessionStorage.setItem(markerKey, JSON.stringify({card_id: String(work.card_id), submitted_at: Date.now()}));
    mark('normal-search-submitted', `${work.name} ${work.ovr || ''}`.trim());
    publishPageDiagnostic('normal-search-submitted', {
      detail: String(work.card_id || ''),
      expected_source_url: normalizedCardUrl(work.source_url),
    });
    apply.click();
    return true;
  }

  function prepareExactWorkPage(work) {
    if (!work || !work.active || !work.source_url) return false;
    const expected = normalizedCardUrl(work.source_url);
    const current = normalizedCardUrl(location.href);
    if (!expected || current !== expected) return false;
    sessionStorage.removeItem('simpleEvaluatorNormalSearchWork');
    if (!/^#prices$/i.test(location.hash || '') && location.hash !== '#simple-evaluator-worktab') {
      history.replaceState(history.state, '', location.pathname + location.search + '#simple-evaluator-worktab');
    }
    publishPageDiagnostic('normal-search-exact-card-opened', {
      detail: String(work.card_id || ''),
      expected_source_url: expected,
    });
    return true;
  }

  async function sendObservation(config, parsed) {
    const observation = {
      source_url: location.href,
      observed_at: new Date().toISOString(),
      status: parsed.state === 'FOUND' ? 'FOUND' : 'NO_LISTING',
      listing_count: parsed.state === 'FOUND' ? parsed.listing_count : 0,
      price: parsed.state === 'FOUND' ? parsed.price : null,
      other_buy_now_prices: parsed.state === 'FOUND' ? parsed.other_buy_now_prices : [],
    };
    const response = await runtimeMessage({
      type: 'simple-evaluator:browser-observation',
      observation,
    });
    if (!response.ok) throw new Error(response.error || 'Local app rejected browser observation');
    return response.result;
  }

  function mark(status, detail = '') {
    document.documentElement.dataset.simpleEvaluatorBrowserWatch = status;
    if (detail) document.documentElement.dataset.simpleEvaluatorBrowserWatchDetail = String(detail).slice(0, 240);
    else delete document.documentElement.dataset.simpleEvaluatorBrowserWatchDetail;
  }

  function pageExtent() {
    const body = document.body;
    const root = document.documentElement;
    return Math.max(
      root ? root.scrollHeight : 0, root ? root.offsetHeight : 0,
      body ? body.scrollHeight : 0, body ? body.offsetHeight : 0
    );
  }

  function nudgeMarketSection() {
    if (playStationHeading()) return false;
    const extent = pageExtent();
    const viewport = Math.max(window.innerHeight || 0, 600);
    const current = Math.max(window.scrollY || window.pageYOffset || 0, 0);
    const target = Math.min(Math.max(extent - viewport, 0), current + Math.max(Math.floor(viewport * 0.85), 500));
    if (target <= current + 20) return false;
    try { window.scrollTo({top: target, left: 0, behavior: 'auto'}); }
    catch (_) { try { window.scrollTo(0, target); } catch (_) { return false; } }
    return true;
  }

  function visibleElement(el) {
    if (!el || !(el instanceof Element)) return false;
    try {
      const style = getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    } catch (_) {
      return false;
    }
  }

  function isGlobalPricesNavigation(el) {
    if (!el || typeof el.getAttribute !== 'function') return false;
    const raw = String(el.getAttribute('href') || '').trim();
    if (!raw) return false;
    try {
      const target = new URL(raw, location.href);
      return target.origin === location.origin && /^\/prices\/?$/i.test(target.pathname);
    } catch (_) {
      return /^\/prices\/?$/i.test(raw);
    }
  }

  function globalPricesAncestor(el) {
    let current = el;
    for (let depth = 0; current && depth < 7; depth += 1, current = current.parentElement) {
      if (isGlobalPricesNavigation(current)) return current;
      if (current === document.body || current === document.documentElement) break;
    }
    return null;
  }

  function sameVisualRow(a, b) {
    if (!a || !b || typeof a.getBoundingClientRect !== 'function' || typeof b.getBoundingClientRect !== 'function') return false;
    try {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      if (!ar || !br || ar.width <= 0 || br.width <= 0 || ar.height <= 0 || br.height <= 0) return false;
      const ac = (ar.top + ar.bottom) / 2;
      const bc = (br.top + br.bottom) / 2;
      return Math.abs(ac - bc) <= Math.max(72, Math.max(ar.height, br.height) * 2.5);
    } catch (_) {
      return false;
    }
  }

  function exactVisibleLabelElements(label) {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const rx = new RegExp(`^${escaped}$`, 'i');
    const nodes = [...document.querySelectorAll('body *')].filter(el => visibleElement(el) && rx.test(textOf(el)));
    return nodes.filter(el => ![...el.children].some(child => visibleElement(child) && rx.test(textOf(child))));
  }

  function clickableAncestor(el) {
    let current = el;
    for (let depth = 0; current && depth < 7; depth += 1, current = current.parentElement) {
      if (current.matches && current.matches('a,button,[role="tab"],[role="button"]')) return current;
      if (typeof current.onclick === 'function') return current;
      const tabindex = current.getAttribute && current.getAttribute('tabindex');
      if (tabindex !== null && tabindex !== undefined && String(tabindex) !== '-1') return current;
      if (current === document.body || current === document.documentElement) break;
    }
    return el;
  }

  function describeElement(el) {
    if (!el) return null;
    let rect = null;
    try {
      const r = el.getBoundingClientRect();
      rect = {top: Math.round(r.top), left: Math.round(r.left), width: Math.round(r.width), height: Math.round(r.height)};
    } catch (_) {}
    return {
      tag: String(el.tagName || '').toLowerCase() || null,
      role: el.getAttribute ? (el.getAttribute('role') || null) : null,
      href: el.getAttribute ? (el.getAttribute('href') || null) : null,
      text: textOf(el).slice(0, 80),
      rect,
    };
  }

  function playerPricesTabInfo() {
    const priceLabels = exactVisibleLabelElements('Prices').filter(el => !globalPricesAncestor(el));
    const overviewLabels = exactVisibleLabelElements('Overview');
    const peerLabels = [
      ...exactVisibleLabelElements('Abilities'),
      ...exactVisibleLabelElements('Comments'),
      ...exactVisibleLabelElements('Compare'),
    ];
    let best = null;
    for (const label of priceLabels) {
      const overview = overviewLabels.find(el => sameVisualRow(label, el));
      if (!overview) continue;
      const peers = peerLabels.filter(el => sameVisualRow(label, el));
      if (peers.length < 2) continue;
      const target = clickableAncestor(label);
      if (!target || globalPricesAncestor(target)) continue;
      const rect = label.getBoundingClientRect();
      const score = peers.length * 100 + Math.max(0, 1000 - Math.abs(rect.top));
      if (!best || score > best.score) best = {tab: target, label, overview, peers, score};
    }
    return {
      tab: best ? best.tab : null,
      diagnostics: {
        price_label_count: priceLabels.length,
        overview_label_count: overviewLabels.length,
        peer_label_count: peerLabels.length,
        selected: best ? describeElement(best.tab) : null,
        price_labels: priceLabels.slice(0, 4).map(describeElement),
      },
    };
  }

  function playerPricesTab() {
    return playerPricesTabInfo().tab;
  }

  function isSelectedTab(el) {
    if (!el) return false;
    if (String(el.getAttribute('aria-selected') || '').toLowerCase() === 'true') return true;
    if (/^(page|true)$/i.test(String(el.getAttribute('aria-current') || ''))) return true;
    if (/^(active|selected)$/i.test(String(el.getAttribute('data-state') || ''))) return true;
    // Only trust the candidate control itself. A shared tab-row parent can carry
    // generic active/selected classes even while a different child tab is active.
    const ownClassText = String(el.className || '');
    return /(^|\s)(active|selected)(\s|$)/i.test(ownClassText);
  }

  let lastDiagnosticKey = '';
  function publishPageDiagnostic(stage, details = {}) {
    const diagnostic = {
      stage: String(stage || '').slice(0, 80),
      url: String(location.href || '').slice(0, 500),
      observed_at: new Date().toISOString(),
      ...details,
    };
    let key = '';
    try { key = JSON.stringify({stage: diagnostic.stage, url: diagnostic.url, detail: diagnostic.detail || '', selected: diagnostic.selected || null, price_label_count: diagnostic.price_label_count}); } catch (_) {}
    if (key && key === lastDiagnosticKey) return;
    lastDiagnosticKey = key;
    void runtimeMessage({type: 'simple-evaluator:page-diagnostic', diagnostic});
  }

  function activatePlayerPricesTab() {
    const info = playerPricesTabInfo();
    const tab = info.tab;
    if (!tab) {
      publishPageDiagnostic('prices-tab-not-found', {...info.diagnostics, detail: 'No visible player-local Prices control matched the Overview/Abilities/Comments/Compare row'});
      return false;
    }
    if (isSelectedTab(tab)) {
      publishPageDiagnostic('prices-tab-already-selected', {...info.diagnostics, detail: 'Player-local Prices control is already selected'});
      return false;
    }
    try {
      publishPageDiagnostic('prices-tab-clicking', {...info.diagnostics, selected: describeElement(tab)});
      tab.click();
      mark('opening-prices', 'Activated player Prices tab for live-auction watch');
      publishPageDiagnostic('prices-tab-clicked', {...info.diagnostics, selected: describeElement(tab)});
      return true;
    } catch (error) {
      publishPageDiagnostic('prices-tab-click-error', {...info.diagnostics, detail: String(error && error.message || error)});
      return false;
    }
  }

  async function observeWhenReady(config) {
    try {
      const deadline = Date.now() + MARKET_WAIT_MS;
      let nextTabAttemptAt = Date.now();
      let nextScrollAt = Date.now() + 1500;
      while (Date.now() < deadline) {
        const preflight = document.documentElement.dataset.simpleEvaluatorPreflight;
        if (['user-action-required', 'access-denied', 'rate-limited'].includes(preflight)) {
          const detail = preflight === 'user-action-required'
            ? 'Page preflight requires user action and the shared work queue will not bypass it'
            : preflight === 'access-denied'
              ? 'Page preflight reports access denied; the shared work queue stopped'
              : 'Page preflight reports rate limiting; the shared work queue stopped';
          mark(preflight, detail);
          publishPageDiagnostic(preflight, {detail});
          const isValueProbe = String(config.watch_id || '').startsWith('value-probe-');
          if (preflight === 'rate-limited' && isValueProbe) {
            await runtimeMessage({type: 'simple-evaluator:value-probe-rate-limited', url: location.href});
          } else {
            await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: preflight});
          }
          return;
        }
        const parsed = parsePlayStationMarket();
        if (parsed.state === 'RATE_LIMITED') {
          mark('rate-limited', 'CFB.FAN returned HTTP 429; automatic probing stopped for this batch');
          publishPageDiagnostic('market-rate-limited', {market_state: parsed.state, detail: `${parsed.reason}; automatic probing stopped`});
          const isValueProbe = String(config.watch_id || '').startsWith('value-probe-');
          if (isValueProbe) {
            await runtimeMessage({type: 'simple-evaluator:value-probe-rate-limited', url: location.href});
          } else {
            await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: 'market-rate-limited'});
          }
          return;
        }
        if (parsed.state === 'SOURCE_ERROR') {
          mark('market-source-error', parsed.reason);
          publishPageDiagnostic('market-source-error', {market_state: parsed.state, detail: parsed.reason});
          await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: 'market-source-error'});
          return;
        }
        if (parsed.state === 'FOUND' || parsed.state === 'NO_LISTING') {
          publishPageDiagnostic('market-parsed', {market_state: parsed.state, detail: parsed.reason || '', price: parsed.price || null, listing_count: parsed.listing_count || 0});
          try {
            const result = await sendObservation(config, parsed);
            const next = result && result.next_refresh_at ? new Date(result.next_refresh_at).toISOString() : '';
            mark('recorded', `${parsed.state} · ${result && result.card_id || config.card_id || ''}${next ? ` · next ${next}` : ''}`);
            publishPageDiagnostic('observation-recorded', {market_state: parsed.state, detail: result && result.card_id || config.card_id || '', next_refresh_at: next || null});
          } catch (error) {
            mark('local-app-unavailable', error.message || String(error));
            setTimeout(start, WATCH_RECHECK_MS);
          }
          return;
        }
        if (parsed.state === 'PARSE_ERROR') {
          mark('parse-error', parsed.reason);
          publishPageDiagnostic('parse-error', {market_state: parsed.state, detail: parsed.reason});
          await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: 'parse-error'});
          return;
        }
        publishPageDiagnostic('market-waiting', {market_state: parsed.state, detail: parsed.reason || 'Waiting for visible PlayStation market'});
        // CFB.FAN may keep inactive tab markup mounted in the DOM. A hidden/off-canvas
        // PlayStation heading must never suppress activation of the visible player Prices
        // control. Attempt the player-local Prices tab whenever the market is still waiting;
        // activatePlayerPricesTab() itself refuses a genuinely selected Prices control.
        if (Date.now() >= nextTabAttemptAt) {
          if (activatePlayerPricesTab()) {
            nextTabAttemptAt = Date.now() + 8000;
            await new Promise(resolve => setTimeout(resolve, 1200));
            continue;
          }
          nextTabAttemptAt = Date.now() + 5000;
        }
        if (Date.now() >= nextScrollAt && /heading not present|result not present/i.test(parsed.reason || '')) {
          nudgeMarketSection();
          nextScrollAt = Date.now() + MARKET_SCROLL_INTERVAL_MS;
        }
        mark('waiting', parsed.reason || 'Waiting for PlayStation market');
        await new Promise(resolve => setTimeout(resolve, MARKET_SCAN_MS));
      }
      mark('market-timeout', 'PlayStation market was not ready within this bounded scan window; shared work queue stopped');
      publishPageDiagnostic('market-timeout', {detail: 'PlayStation market was not ready within this bounded scan window; shared work queue stopped'});
      await runtimeMessage({type: 'simple-evaluator:browser-work-stop', url: location.href, reason: 'market-timeout'});
    } catch (error) {
      mark('watch-error', error && error.message || String(error));
      setTimeout(start, WATCH_RECHECK_MS);
    }
  }

  let starting = false;
  async function start() {
    if (starting) return;
    starting = true;
    try {
      const work = await getBrowserWork();
      if (work && work.active && work.source_url) {
        if (isNormalSearchPage()) {
          await driveNormalSearch(work);
          return;
        }
        prepareExactWorkPage(work);
      }
      const config = await getWatchConfig();
      if (!config.active) {
        mark(config.error ? 'local-app-unavailable' : 'inactive', config.error || '');
        setTimeout(start, WATCH_RECHECK_MS);
        return;
      }
      const elapsedSinceNavigation = (typeof performance !== 'undefined' && Number.isFinite(performance.now())) ? performance.now() : 0;
      const remainingDwell = Math.max(0, MIN_PAGE_DWELL_MS - elapsedSinceNavigation);
      if (remainingDwell > 0) {
        mark('dwell', `Waiting ${Math.ceil(remainingDwell)}ms before rendered-page inspection`);
        publishPageDiagnostic('page-dwell', {detail: `minimum ${MIN_PAGE_DWELL_MS}ms rendered-page dwell before inspection`});
        await new Promise(resolve => setTimeout(resolve, remainingDwell));
      }
      mark('active', config.card_id || '');
      publishPageDiagnostic('active-config', {detail: config.card_id || '', interval_seconds: config.interval_seconds || null});
      await observeWhenReady(config);
    } finally {
      starting = false;
    }
  }

  if (typeof window !== 'undefined') {
    window.__simpleEvaluatorBrowserWatch = {parsePlayStationMarket, numberFromMoneyText, playerPricesTab, playerPricesTabInfo, isGlobalPricesNavigation, normalizedCardUrl, isNormalSearchPage, exactRenderedResult, exactApplyFiltersButton};
  }

  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage && location.hostname === 'cfb.fan') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => { void start(); }, {once: true});
    else void start();
  }
})();
