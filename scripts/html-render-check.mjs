#!/usr/bin/env node
// Real-JS execution gate for generated sizing HTML proposals.
//
// Extracts the inline <script> block from a generated proposal HTML, runs it
// inside a Node `vm` context with stub DOM / Chart globals, fires the
// DOMContentLoaded handler, and reports whether boot succeeded and what the
// final `kpi-tcv` textContent is.
//
// This catches the class of bug where a missing-but-template-required key
// (e.g. ai_cortex.document_ai) makes populateAIPanel() throw a TypeError, the
// DOMContentLoaded handler aborts, and the page silently renders every dollar
// value as `$0`. The python `html-render-check.py` re-implements the
// recalculate() math but never runs the real DOM-rendering code path; this
// script does.
//
// Usage:
//   node html-render-check.mjs path-to-proposal.html
//
// Output: a single JSON object on stdout, e.g.
//   {"ok": true, "kpi_tcv": "$1,234,567", "error": null}
//   {"ok": false, "kpi_tcv": "$0", "error": "TypeError: ...", "stack": "..."}
//
// Exit 0 always (errors are encoded in the JSON `ok` field).

import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const argv = process.argv.slice(2);
if (argv.length !== 1) {
  console.error('usage: node html-render-check.mjs <proposal.html>');
  process.exit(2);
}

const htmlPath = argv[0];
const html = readFileSync(htmlPath, 'utf8');

// Extract the inline <script> block. The template wraps the runtime in exactly
// one inline `<script>...</script>` (the other two `<script src=...>` tags load
// chart.js from a CDN and are skipped because they have no body).
const inlineRe = /<script>([\s\S]*?)<\/script>/g;
let scriptBody = null;
let largest = 0;
for (const m of html.matchAll(inlineRe)) {
  if (m[1].length > largest) {
    largest = m[1].length;
    scriptBody = m[1];
  }
}

if (!scriptBody) {
  console.log(JSON.stringify({
    ok: false,
    kpi_tcv: '$0',
    kpi_year1: '$0',
    error: 'No inline <script> block found in HTML',
    stack: null,
  }));
  process.exit(0);
}

// ────────────────────────────────────────────────────────────────────────────
// Stub DOM / browser globals
// ────────────────────────────────────────────────────────────────────────────

function makeElement(id) {
  // Persistent backing store for textContent / value / etc. The renderer
  // writes to `kpi-tcv` and friends; we read those back at the end.
  const el = {
    id: id || '',
    _textContent: '',
    _innerHTML: '',
    _value: '',
    children: [],
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    dataset: {},
    attributes: {},
    addEventListener() {},
    removeEventListener() {},
    appendChild(child) { this.children.push(child); return child; },
    removeChild(child) {
      const i = this.children.indexOf(child);
      if (i >= 0) this.children.splice(i, 1);
      return child;
    },
    insertBefore(child) { this.children.push(child); return child; },
    querySelector() { return makeElement(''); },
    querySelectorAll() { return []; },
    getElementsByClassName() { return []; },
    getElementsByTagName() { return []; },
    getContext() {
      return {
        clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {},
        stroke() {}, fill() {}, arc() {}, save() {}, restore() {}, translate() {},
        rotate() {}, scale() {}, setTransform() {}, fillText() {}, measureText() {
          return { width: 0 };
        },
      };
    },
    getBoundingClientRect() { return { width: 0, height: 0, top: 0, left: 0 }; },
    cloneNode() { return makeElement(this.id); },
    setAttribute(k, v) { this.attributes[k] = v; },
    getAttribute(k) { return this.attributes[k]; },
    removeAttribute(k) { delete this.attributes[k]; },
    hasAttribute(k) { return k in this.attributes; },
    focus() {}, blur() {}, click() {},
    select() {}, scrollIntoView() {},
  };

  Object.defineProperty(el, 'textContent', {
    get() { return el._textContent; },
    set(v) { el._textContent = String(v); },
  });
  Object.defineProperty(el, 'innerHTML', {
    get() { return el._innerHTML; },
    set(v) { el._innerHTML = String(v); },
  });
  Object.defineProperty(el, 'value', {
    get() { return el._value; },
    set(v) { el._value = String(v); },
  });

  return el;
}

const elementsById = new Map();
const documentListeners = {};

const stubDocument = {
  getElementById(id) {
    if (!elementsById.has(id)) {
      elementsById.set(id, makeElement(id));
    }
    return elementsById.get(id);
  },
  createElement(_tag) { return makeElement(''); },
  createTextNode(_text) { return makeElement(''); },
  querySelector() { return makeElement(''); },
  querySelectorAll() { return []; },
  getElementsByClassName() { return []; },
  getElementsByTagName(tag) {
    if (tag === 'html') return [makeElement('html')];
    if (tag === 'body') return [makeElement('body')];
    return [];
  },
  addEventListener(event, cb) {
    if (!documentListeners[event]) documentListeners[event] = [];
    documentListeners[event].push(cb);
  },
  removeEventListener() {},
  body: makeElement('body'),
  documentElement: makeElement('html'),
  head: makeElement('head'),
  readyState: 'loading',
};

const stubWindow = {
  addEventListener() {},
  removeEventListener() {},
  matchMedia(_query) {
    return {
      matches: false,
      addEventListener() {}, removeEventListener() {},
      addListener() {}, removeListener() {},
    };
  },
  getComputedStyle() { return { getPropertyValue() { return ''; } }; },
  requestAnimationFrame(cb) { return setTimeout(cb, 0); },
  cancelAnimationFrame(id) { clearTimeout(id); },
  setTimeout, clearTimeout, setInterval, clearInterval,
  scrollTo() {}, scroll() {}, alert() {}, confirm() { return true; },
  print() {},
  navigator: { userAgent: 'node-render-check' },
  location: { href: 'about:blank', pathname: '/', search: '', hash: '' },
};

// Chart.js stub. The template instantiates `new Chart(...)` for stacked-bar
// and donut charts, and calls `Chart.register(...)` for the datalabels plugin.
function ChartStub(_canvas, _config) {
  return {
    update() {}, destroy() {}, resize() {}, render() {},
    data: { datasets: [], labels: [] },
    options: {},
  };
}
ChartStub.register = function () {};
ChartStub.defaults = { font: {}, plugins: {} };

const ChartDataLabelsStub = { id: 'datalabels' };

// DOM serialization stubs. The PPTX-export module instantiates
// `new DOMParser()` / `new XMLSerializer()` at the top level of its script
// block (these are valid browser globals and do NOT cause a $0 render in a
// real browser). The export DOM machinery itself only runs on a button
// click, so minimal stubs are enough to let the page boot cleanly here.
class DOMParserStub {
  parseFromString() { return stubDocument; }
}
class XMLSerializerStub {
  serializeToString() { return ''; }
}

// ────────────────────────────────────────────────────────────────────────────
// Build the sandbox and run
// ────────────────────────────────────────────────────────────────────────────

// Console stub: mute the embedded script's diagnostic output so it doesn't
// pollute the sidecar's stdout (which carries the JSON result line). The
// embedded HTML may call console.info/log for build-time TCV diagnostics;
// route everything to stderr instead so a developer can still see it via
// the sidecar's stderr but the JSON parser on stdout stays clean.
const sandboxConsole = {
  log:   (...a) => process.stderr.write('[sandbox.log] '   + a.join(' ') + '\n'),
  info:  (...a) => process.stderr.write('[sandbox.info] '  + a.join(' ') + '\n'),
  warn:  (...a) => process.stderr.write('[sandbox.warn] '  + a.join(' ') + '\n'),
  error: (...a) => process.stderr.write('[sandbox.error] ' + a.join(' ') + '\n'),
  debug: () => {},
};

const sandbox = {
  document: stubDocument,
  window: stubWindow,
  Chart: ChartStub,
  ChartDataLabels: ChartDataLabelsStub,
  DOMParser: DOMParserStub,
  XMLSerializer: XMLSerializerStub,
  console: sandboxConsole,
  setTimeout, clearTimeout, setInterval, clearInterval,
  Math, Date, JSON, Object, Array, String, Number, Boolean, RegExp,
  Map, Set, WeakMap, WeakSet, Symbol, Promise, Error, TypeError, RangeError,
  parseInt, parseFloat, isNaN, isFinite,
  encodeURIComponent, decodeURIComponent, encodeURI, decodeURI,
};
sandbox.globalThis = sandbox;
sandbox.self = sandbox;

vm.createContext(sandbox);

let bootError = null;
let bootStack = null;

try {
  // Run top-level script body. This defines functions, registers the
  // DOMContentLoaded handler, and evaluates the embedded SIZING_SPEC and
  // PRICING_DATA constants.
  vm.runInContext(scriptBody, sandbox, {
    filename: htmlPath + ':inline-script',
    timeout: 10_000,
  });
} catch (e) {
  bootError = `${e.name}: ${e.message}`;
  bootStack = e.stack || null;
}

// Fire the captured DOMContentLoaded callbacks (this is what actually triggers
// populate*Panel + recalculate + chart rendering).
let handlerError = null;
let handlerStack = null;

if (!bootError) {
  const handlers = documentListeners['DOMContentLoaded'] || [];
  if (handlers.length === 0) {
    handlerError = 'No DOMContentLoaded handler was registered — the script ' +
                   'body executed but never wired up the boot callback.';
  } else {
    for (const cb of handlers) {
      try {
        cb({ type: 'DOMContentLoaded' });
      } catch (e) {
        handlerError = `${e.name}: ${e.message}`;
        handlerStack = e.stack || null;
        break;
      }
    }
  }
}

const tcvEl = elementsById.get('kpi-tcv');
const tcv = tcvEl ? tcvEl._textContent || '$0' : '$0';

// Extract the Expected scenario card's TCV from the rendered #scenarios innerHTML.
// Used by the scenario-consistency regression test to assert it equals kpi_tcv.
let expectedScenarioTcv = null;
const scenariosEl = elementsById.get('scenarios');
if (scenariosEl && scenariosEl._innerHTML) {
  const cardRe = /scenario-card\s+expected[\s\S]*?scenario-tcv">([^<]*)<\/div>/;
  const cm = scenariosEl._innerHTML.match(cardRe);
  if (cm) expectedScenarioTcv = cm[1].trim();
}

const error = bootError || handlerError;
const stack = bootStack || handlerStack;

// `ok` requires both: (1) no exception thrown, (2) tcv resolved to a non-zero
// dollar string. The textContent format is "$<digits>" or "$<digits>,<digits>"
// — anything other than literal "$0" counts as success.
const tcvIsZero = tcv === '$0' || tcv === '' || tcv == null;
const ok = !error && !tcvIsZero;

console.log(JSON.stringify({
  ok,
  kpi_tcv: tcv,
  expected_scenario_tcv: expectedScenarioTcv,
  error,
  stack,
}));
