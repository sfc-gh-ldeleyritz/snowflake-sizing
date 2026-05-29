# Snowflake Sizing HTML Specification

> **Note:** The canonical HTML output is `assets/templates/proposal-template.html`. This document describes its structure, data contracts (SIZING_SPEC schema, PRICING_DATA schema), and token substitution table. When modifying the template, keep this spec in sync.

## Token Substitution Table

The template contains 11 placeholder tokens. All must be substituted before writing the output file:

| Token | Value |
|---|---|
| `__BRAND_FONTS_CSS__` | full contents of `assets/branding/_brand_fonts.css` |
| `__PRICING_DATA__` | JSON object of credit/storage rates |
| `__SIZING_SPEC__` | complete SIZING_SPEC JSON object |
| `__CUSTOMER__` | customer display name |
| `__EDITION__` | Snowflake edition (`Enterprise` / `Business Critical`) |
| `__CLOUD__` | cloud provider (`AWS` / `Azure` / `GCP`) |
| `__REGION__` | deployment region (e.g. `us-east-1`) |
| `__YEARS__` | contract length as integer |
| `__CREDIT_RATE__` | per-credit dollar rate |
| `__DATE__` | generation date (YYYY-MM-DD) |
| `__PDF_VERSION__` | version string from SIZING_SPEC metadata |

---

## Output File

`temp/<customer-slug>-<N>year-sizing.html`

Customer slug: lowercase, hyphens only. E.g. `acme-corp-3year-sizing.html`.

The file MUST be completely self-contained. No external files. No server required. Send directly to customer.

**Self-contained constraint**: The HTML must render correctly with no network access except `cdn.jsdelivr.net` for Chart.js. No font CDN, no remote images — all fonts and logos are inlined as base64 data URIs / inline SVG.

---

## Required CDN Scripts (in `<head>`)

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
```

Do **not** add a Google Fonts link. Brand fonts are inlined via the `__BRAND_FONTS_CSS__` token (see Token Substitution Table above).

---

## Brand Assets

The template already contains official Snowflake branding — wordmark, favicon, crystal mark footer — baked in. Do not regenerate or alter those sections when performing token substitution.

Reference: `assets/branding/` contains `_brand_fonts.css`, `_brand_logo.svg`, `_brand_favicon.b64`, `snowflake-mark.svg`, and `apply_brand.py` (idempotent post-processor for upgrading older files).

---

## CSS Variables (`:root`) and Font Stack

```css
:root {
  /* Primary brand — sourced from snowflake.com canonical tokens */
  --sf-blue:      #29B5E8;  /* --ui-04 brand cyan */
  --sf-blue-dark: #249EDC;  /* --ui-01 deeper primary */
  --sf-navy:      #11567F;  /* --ui-02 navy */
  --sf-navy-deep: #003545;  /* legacy hero deep navy */
  --sf-sky:       #76D0F1;  /* --ui-11 sky accent */
  --sf-teal:      #76D0F1;  /* alias: same as --sf-sky */
  --sf-orange:    #FF9F36;  /* warning badges only */
  /* Surfaces */
  --sf-surface:   #ECF1F5;  /* --ui-08 */
  --sf-divider:   #A0BBCC;  /* --divider-01 */
  --gray-800: #2d3748;
  --gray-700: #4a5568;
  --gray-600: #718096;
  --gray-200: #e2e8f0;
  --gray-100: #f7fafc;
  --white: #ffffff;
  --success: #38a169;
  --warning: #ED7D31;
}

/* Font stack — brand fonts are inlined via _brand_fonts.css */
body {
  font-family: 'Lato', -apple-system, BlinkMacSystemFont, sans-serif;
}
h1, h2, h3, .kpi-value, .scenario-tcv {
  font-family: 'Texta', 'Lato', sans-serif;
  font-weight: 800;
}
.workload-calc, code, pre {
  font-family: 'Source Code Pro', monospace;
}
```

---

## Snowflake Logo (inline SVG — use in header)

Read `assets/branding/_brand_logo.svg` and inline it verbatim in the header. Set `height="36"` on the root `<svg>` element and remove any fixed `width` attribute (let it scale proportionally). The logo is white-on-transparent, designed for the dark navy header.

Example wrapper:

```html
<div style="height:36px; display:flex; align-items:center;">
  <!-- _brand_logo.svg contents here, with height="36" on root svg -->
</div>
```

Note: Do **not** use the old hand-drawn placeholder circle SVG. Always inline `_brand_logo.svg`.

---

## Page Structure (top to bottom)

### 1. Header

```html
<div class="header">
  <div class="header-top">
    <div><!-- Snowflake logo SVG --></div>
    <div class="doc-meta">
      <div>CONSUMPTION ESTIMATE</div>
      <div>Prepared: [DATE]</div>
      <div>[EDITION] · [CLOUD] [REGION]</div>
    </div>
  </div>
  <h1>[CUSTOMER NAME]</h1>
  <div class="header-subtitle">[N]-Year Snowflake Consumption Estimate</div>
</div>
```

CSS: `background: linear-gradient(140.86deg, var(--sf-navy-deep) 0%, var(--sf-navy) 100%); border-radius: 8px; padding: 32px; color: white;`

### 2. Executive Summary KPI Tiles

Four tiles in a `grid-template-columns: repeat(4, 1fr)` grid. Each tile:
- Label (small, muted)
- Large value (bold, white)
- Left border `3px solid var(--sf-blue)`

Tiles:
1. **Total TCV** — sum of all years, formatted `$X,XXX,XXX`
2. **Year 1 Cost** — year 1 total
3. **Total Credits** — sum of all years' compute+serverless+AI credits (not dollar)
4. **Recommended Commitment** — same as TCV (SE adjusts manually)

All tiles update live via `id="kpi-tcv"` etc.

### 3. Year-by-Year Chart + Table

**Chart**: Stacked bar chart (Chart.js). One bar per year. Monochromatic Snowflake-blue palette — define once at the top of `<script>`:

```javascript
const SF_CHART_PALETTE = ['#11567F', '#1B7BAE', '#29B5E8', '#76D0F1', '#A0BBCC'];
```

Segments (bottom to top), using `SF_CHART_PALETTE[0..4]`:
- Compute Warehouses (`SF_CHART_PALETTE[0]` — deep navy)
- Serverless (`SF_CHART_PALETTE[1]` — mid blue)
- AI/Cortex (`SF_CHART_PALETTE[2]` — brand cyan)
- Storage (`SF_CHART_PALETTE[3]` — sky)
- Other (`SF_CHART_PALETTE[4]` — muted blue-grey)

Chart dataset IDs: `chartCompute`, `chartServerless`, `chartAI`, `chartStorage`, `chartOther`

**Table below chart** — columns: Year | Credits | Compute $ | Serverless $ | AI $ | Storage $ | Other $ | **Total $**

### 4. Workload Breakdown Donut

Chart.js doughnut showing credit % by workload. Labels show workload name + percentage. Colours cycle through `SF_CHART_PALETTE` (starting from index 0, wrapping).

### 5. Configuration Panel (Accordion Tabs)

Tabs rendered as pill buttons. Active tab shows its section. Default active: **Warehouses**.

Tabs (in order): Warehouses | Serverless | AI / Cortex | SPCS | Openflow | Storage | Collaboration | Global Settings

#### Warehouses Tab

For each workload in `SIZING_SPEC.workloads`, render a card:

```html
<div class="workload-card" data-id="[workload.id]">
  <div class="workload-header">
    <span class="workload-label">[workload.label]</span>
    <span class="workload-calc" id="calc-[id]"><!-- live calculation --></span>
  </div>
  <div class="controls-grid">
    <label>Warehouse Size
      <select id="size-[id]" onchange="updateWorkload('[id]', 'size', this.value)">
        <option value="XS">XS — 1 cr/hr</option>
        <option value="S">S — 2 cr/hr</option>
        <option value="M" selected>M — 4 cr/hr</option>
        <option value="L">L — 8 cr/hr</option>
        <option value="XL">XL — 16 cr/hr</option>
        <option value="2XL">2XL — 32 cr/hr</option>
        <option value="3XL">3XL — 64 cr/hr</option>
        <option value="4XL">4XL — 128 cr/hr</option>
      </select>
    </label>
    <label>Hours/Day
      <input type="range" id="hrs-[id]" min="0" max="24" step="0.5" value="[hours_per_day]"
             oninput="updateWorkload('[id]', 'hours_per_day', +this.value)">
      <span id="hrs-val-[id]">[hours_per_day]</span>
    </label>
    <label>Days/Month
      <input type="range" id="days-[id]" min="1" max="31" step="1" value="[days_per_month]"
             oninput="updateWorkload('[id]', 'days_per_month', +this.value)">
      <span id="days-val-[id]">[days_per_month]</span>
    </label>
    <label>Clusters (min / max)
      <input type="number" id="cmin-[id]" min="1" max="10" value="[clusters_min]"
             onchange="updateWorkload('[id]', 'clusters_min', +this.value)"> /
      <input type="number" id="cmax-[id]" min="1" max="10" value="[clusters_max]"
             onchange="updateWorkload('[id]', 'clusters_max', +this.value)">
    </label>
  </div>
  <div class="justification">[workload.source]: [workload.justification]</div>
</div>
```

Live calculation shown in `.workload-calc`:
`4 cr/hr × 2.0 hrs × 22 days × 1.0 avg clusters = 176 cr/mo → 2,112 cr/yr`

The card label is rendered as an editable `<input>` so the SE can rename a workload during a live session. Each card also has a `Delete` button, and the tab footer has a `+ Add Workload` button which appends a card with default values (M / 4 hrs / 22 days / 1 cluster) and triggers `recalculate()`. Every workload entry MUST have a stable `id` field; new workloads are issued ids by `nextId('wl')`.

Card mutation handlers: `addWorkload()`, `removeWorkload(id)`, `updateWorkload(id, field, value)`.

#### Serverless Tab

For each feature in `SIZING_SPEC.serverless`, render a row:
```html
<div class="serverless-row">
  <label class="toggle">
    <input type="checkbox" id="sl-[key]" [checked if enabled]
           onchange="updateServerless('[key]', 'enabled', this.checked)">
    <span class="feature-name">[label]</span>
    <span class="unit-hint">[unit, e.g. "GB/month"]</span>
  </label>
  <input type="number" id="sl-vol-[key]" value="[volume]" min="0"
         oninput="updateServerless('[key]', '[volume_field]', +this.value)"
         [disabled if not enabled]>
  <span class="serverless-cost" id="sl-cost-[key]">$0</span>
</div>
```

#### AI / Cortex Tab

Group by sub-category: Cortex Complete | Cortex Agents | Snowflake Intelligence | Cortex Code | Analyst & Search | Functions | Fine-tuning | Other

Each feature: toggle + model selector (where applicable) + token/message/GB input + live cost.

#### SPCS Tab

`SIZING_SPEC.spcs.instances[]` rendered as one card per instance. Each card has an editable label, generation (gen1/gen2), instance type selector, count, hours/month, and a `Delete` button. A `+ Add SPCS Instance` button at the bottom of the tab appends a new instance with sensible defaults (gen2 / `GEN_X64_G2_4` / 1 / 730 hrs) and triggers `recalculate()`. When the last instance is deleted, `spcs.enabled` is set to false automatically.

Card mutation handlers: `addSPCSInstance()`, `removeSPCSInstance(id)`, `updateSPCSInstance(id, field, value)`.

#### OpenFlow Tab

`SIZING_SPEC.openflow.instances[]` rendered as one card per connector. Each card has an editable label, deployment (BYOC / SPCS), source connections, vCPU per connection, hours/month, and a `Delete` button. A `+ Add OpenFlow Instance` button at the bottom appends a new connector. The tab also exposes a master `Enable OpenFlow billing` checkbox bound to `openflow.enabled`. The Oracle Connector remains a separate `openflow_oracle` object with licensed cores.

Legacy single-object specs (`openflow.source_connections` / `vcpu_per_connection` / `hours_monthly` directly on `openflow`) are auto-migrated by the template's `normalizeSpec()` IIFE on load — but freshly generated specs MUST emit the array form.

Card mutation handlers: `addOpenflowInstance()`, `removeOpenflowInstance(id)`, `updateOpenflowInstance(id, field, value)`.

#### Storage Tab

- Raw TB (year 1): range slider 0–1000
- Compression ratio: select (1x / 2x / 3x / 5x / 7x / 10x)
- Annual growth %: range slider 0–100
- Time-travel days: select (0 / 1 / 7 / 14 / 30 / 90)
- Churn rate %: range slider 0–100
- Live storage breakdown table: compressed TB | time-travel TB | failsafe TB | total TB | monthly $ | annual $

#### Collaboration Tab

`SIZING_SPEC.collaboration.accounts[]` rendered as one card per account, with a coloured badge indicating type (`Reader` or `Managed`). Each card has an editable label, type selector (`reader` / `managed`), warehouse size, hours/day, days/month, and a `Delete` button. Two add buttons at the bottom: `+ Add Reader Account` and `+ Add Managed Account`. The `type` field is display-only — both reader and managed accounts use the same compute cost model (warehouse size × hours × days × credit rate).

Native Apps and Marketplace remain separate subscription objects on `collaboration.native_apps` / `collaboration.marketplace`.

Legacy `collaboration.reader_accounts` (single object) is auto-migrated by the template's `normalizeSpec()` IIFE on load.

Card mutation handlers: `addAccount(type)`, `removeAccount(id)`, `updateAccount(id, field, value)`.

#### Global Settings Tab

- Edition: select (Standard / Enterprise / Business Critical / VPS) — updates credit_rate live
- Cloud: select (AWS / Azure / GCP)
- Region: grouped select populated from PRICING_DATA — updates credit_rate live
- Contract years: select (1 / 2 / 3 / 4 / 5) — adds/removes year bars from chart
- Default Ramp curve: select (Slowest x^4 / Slow x^2 / Linear x / Fast x^0.5 / Fastest x^0.25 / Manual). Sets `meta.default_ramp_curve` AND propagates to every workload row's `ramp_curve` field for one-click rebaseline.
- Dev start month: number input (1-36). Sets `meta.default_dev_start_month` AND propagates to every workload row.
- Go-live month: number input (1-36). Sets `meta.default_go_live_month` AND propagates to every workload row.
- Annual growth %: number input. Sets `meta.annual_growth_rate` (used by year 2+ scaling).
- List rate ($/credit): read-only display of the rate from `PRICING_DATA.credit_pricing` for the current Edition × Cloud × Region selection.

##### Discount override

A separate card below the main grid lets the SE apply a negotiated discount.

```js
SIZING_SPEC.meta.list_credit_rate    // pricing-JSON rate (always preserved)
SIZING_SPEC.meta.credit_rate         // EFFECTIVE rate every calculation reads
SIZING_SPEC.meta.discount = {
  enabled: false,                    // toggle state
  mode: "percent",                   // "percent" or "rate" — last edited field
  percent: 0,                        // 0..100 (clamped)
  rate: null                         // $/credit override; null means derive from percent
}
```

Behaviour:
- **Toggle off** (default): fields hidden, `meta.credit_rate = meta.list_credit_rate`, header shows the list rate with no badge.
- **Toggle on**: two mutually-linked inputs appear — `Net rate ($/credit)` and `Discount %`. Editing one updates the other against the list rate via `applyDiscount()`. A read-only `Effective rate` field mirrors `meta.credit_rate` for confirmation.
- Edition / Cloud / Region change recomputes `meta.list_credit_rate` from the pricing JSON, then `applyDiscount()` re-derives the effective rate (percent stays sticky if `mode === "percent"`; net rate stays sticky if `mode === "rate"`).
- Header shows the effective rate followed by a subtle `(N% off list)` badge (rendered by `updateHeaderInfo()` into `#hdr-discount-badge`).

**Scope** — applies to Platform Credits only (warehouses, serverless, replication compute). AI Credit rate (`PRICING_DATA.ai_credit_rate.global_on_demand` = $2.00, regional = $2.20) is intentionally untouched per Snowflake's [AI Pricing Sales GTM FAQ](https://docs.google.com/document/d/10k7wZLUN3tybElajcKuSccplCaYx4xEmx70HovXbVrw): *"Negotiated capacity discounts do not apply to AI Credits."* AI Credits use a separate automatic ACV-tiered discount (Table 2(b) of the Consumption Table) that the plugin does not surface as an editable input.

Persistence: `meta.discount` and `meta.list_credit_rate` round-trip through `saveSnapshot()`. Legacy snapshots without these fields are seeded by the `normalizeSpec()` IIFE on load (`enabled: false`, `list_credit_rate = credit_rate`), so existing examples continue to load and render unchanged.

### 6. Scenario Comparison

Three side-by-side columns rendered as cards:

| | Conservative | Expected | Aggressive |
|---|---|---|---|
| Growth | 10%/yr | 20%/yr | 35%/yr |
| Curve | slow (x^2) | linear (x) | fast (x^0.5) |
| Go-live shift | +1 month later | unchanged | -1 month earlier |

Each column shows: Year 1 / Year 2 / Year 3 / TCV. The "Expected" column is highlighted with `border: 2px solid var(--sf-blue)`.

Each column has read-only growth and curve indicators (the canonical edit paths are the per-workload ramp fields and the global defaults in the Global Settings tab).

**Scenario toggle.** Above the grid: `<input type="checkbox" id="show-low-high" checked>` labeled *Show Conservative & Aggressive scenarios*. When unchecked, `updateScenarios()` filters the array to the Expected card only and adds the `only-expected` class to `.scenario-grid` (`grid-template-columns: minmax(0, 480px); justify-content: center;`) so the lone card doesn't stretch full-width. Hidden in print (`@media print` rule on `.scenario-toggle`).

#### Scenario Calculation

Each scenario computes its own year-by-year totals using the per-month ramp helper:

```javascript
function scenarioRampForYear(sc, year) {
  // sc = { growth, curve, shift }
  const m = SIZING_SPEC.meta;
  const synthRow = {
    ramp_curve: sc.curve,
    dev_start_month: m.default_dev_start_month,
    go_live_month: Math.max(2, (m.default_go_live_month || 11) + sc.shift),
  };
  const saved = m.annual_growth_rate;
  m.annual_growth_rate = sc.growth;
  const r = rampMultiplierForYear(synthRow, year);
  m.annual_growth_rate = saved;
  return r;
}

function calcScenarioTCV(sc) {
  const years = SIZING_SPEC.meta.contract_years;
  const cr    = SIZING_SPEC.meta.credit_rate;
  const aiCr  = SIZING_SPEC.meta.ai_credit_rate;
  const sr    = SIZING_SPEC.meta.storage_rate_per_tb;
  let tcv = 0;
  const yearCosts = [];
  for (let y = 1; y <= years; y++) {
    const r = scenarioRampForYear(sc, y);
    const whCredits  = SIZING_SPEC.workloads.reduce((s, w) => s + whMonthlyCredits(w) * 12, 0) * r;
    const slCredits  = calcServerlessCredits() * 12 * r;
    const aiCredits  = calcAICredits() * 12 * r;
    const storageCost = storageForYear(y) * sr * 12;
    const spcsCost   = calcSPCSCost() * 12 * r;
    const ofCost     = calcOpenflowCost(cr, r);
    const oracleCost = SIZING_SPEC.openflow_oracle.enabled ? SIZING_SPEC.openflow_oracle.licensed_cores * 110 * 12 : 0;
    const replication = calcReplicationForYear(y);  // not scaled by scenario ramp; replication has its own growth model
    const yearTotal = (whCredits + slCredits) * cr + aiCredits * aiCr + storageCost + spcsCost + ofCost + oracleCost + replication.total_cost;
    yearCosts.push(yearTotal);
    tcv += yearTotal;
  }
  return { tcv, yearCosts };
}

function updateScenarios() {
  const scenarios = [
    { id: 'conservative', growth: 0.10, curve: 'slow',   shift: +1 },
    { id: 'expected',     growth: 0.20, curve: 'linear', shift:  0 },
    { id: 'aggressive',   growth: 0.35, curve: 'fast',   shift: -1 },
  ];
  for (const sc of scenarios) {
    const { tcv, yearCosts } = calcScenarioTCV(sc);
    document.getElementById(`sc-tcv-${sc.id}`).textContent = '$' + fmt(tcv);
    yearCosts.forEach((cost, i) => {
      const el = document.getElementById(`sc-yr${i+1}-${sc.id}`);
      if (el) el.textContent = '$' + fmt(cost);
    });
  }
}
```

Each scenario card must have:
- Read-only growth indicator: `<input type="text" disabled value="[growth]%/yr">`
- Read-only curve indicator: `<input type="text" disabled value="[curve] · go-live month [shift-applied]">`
- Year cost spans: `<span id="sc-yr1-[id]">`, `<span id="sc-yr2-[id]">`, `<span id="sc-yr3-[id]">`
- TCV span: `<span id="sc-tcv-[id]">`

### 7. Assumptions & Open Questions

Two sections rendered from `SIZING_SPEC.assumptions` and `SIZING_SPEC.confirm_required`:

```html
<div class="section">
  <h3>Stated Assumptions</h3>
  <ul class="assumptions-list" id="assumptions-list"><!-- rendered by renderAssumptions() --></ul>
  <button class="add-item-btn" onclick="addAssumption()">+ Add Assumption</button>
  <h3 style="margin-top: 24px;">⚠️ Requires Confirmation</h3>
  <ul class="confirm-list" id="confirm-list"><!-- rendered by renderAssumptions() --></ul>
  <button class="add-item-btn" onclick="addConfirmItem()">+ Add Item</button>
</div>
```

**Editable items.** Both lists are fully editable in the browser:

- `assumptions` items: each `<li>` carries `contenteditable="true"`. An `oninput` handler writes back to `SIZING_SPEC.assumptions[i]` on every keystroke.
- `confirm_required` items: the item text is a `<span contenteditable="true">` inside the `<li>` (the `<li>` itself also holds the non-editable CONFIRM badge). An `oninput` handler calls `updateConfirmItem(i, text)`.
- A `✕` delete button (`.item-delete-btn`) appears on hover for each item; it calls `removeAssumption(i)` or `removeConfirmItem(i)` which splices the array and re-renders.
- `+ Add Assumption` / `+ Add Item` buttons (`.add-item-btn`) push a placeholder entry, re-render, and focus + select the new item.
- All edit controls (`.item-delete-btn`, `.add-item-btn`) are `display: none !important` in `@media print`.
- `saveSnapshot()` requires no changes — it serialises the full `SIZING_SPEC`, so all edits are preserved automatically on the next save.

JS mutation helpers (defined immediately after `renderAssumptions()`): `removeAssumption(i)`, `addAssumption()`, `updateConfirmItem(i, text)`, `removeConfirmItem(i)`, `addConfirmItem()`, `_selectAll(el)`.

### 8. Footer

```html
<div class="footer">
  <div style="margin-bottom:8px;">
    <svg height="20" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle;margin-right:6px;">
      <circle cx="16" cy="16" r="16" fill="#29B5E8"/>
      <path d="M16 4v24M8 8l16 16M24 8L8 24M4 16h24" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
    </svg>
    <span style="font-weight:700;">Snowflake Confidential</span>
  </div>
  <p>Prepared by Snowflake · This estimate is based on stated requirements and industry benchmarks.
  Actual consumption may vary. All prices are list price on-demand rates.
  Credit rates effective [PDF_VERSION].</p>
  <p>Generated [DATE]</p>
</div>
```

---

## Print / PDF Layout

SEs share the proposal as a PDF. The only path is the browser's native **Print** dialog (with "Save as PDF" as the destination); there is no in-browser rasterizer. A single `@media print` block restyles the live page for paper/PDF output.

### Print / Save as PDF button (primary)

A floating `<button class="print-btn" onclick="window.print()">Print / Save as PDF</button>` is rendered at fixed top-right (navy, primary). It opens the native print dialog; the SE chooses "Save as PDF" as the destination. The button is hidden by `@media print` so it never appears in the output. (The only other floating button is the secondary white **Save HTML** button.)

### `@media print` rules (essentials)

- `@page { size: A4 portrait; margin: 15mm; }` — generous margin so any browser-injected date/title/URL bars land in the unprintable margin instead of overlapping content.
- `body` set to `print-color-adjust: exact` so the navy header background and badge colours render in the PDF.
- `.tab-nav`, `.print-btn`, `.save-btn`, `.add-btn`, `.add-btn-group`, `.delete-btn`, `.scenario-toggle`, `.info-icon`, `#tt-tip`, `.item-delete-btn`, `.add-item-btn` are all `display: none !important` so the interactive chrome never appears in the output.
- `.tab-content { display: block !important; }` — every tab is shown in flow. `.tab-content + .tab-content { page-break-before: always; }` puts each tab on its own page (a per-tab handout).
- Each `.tab-content` carries a `data-print-title` attribute (e.g. `"Warehouses"`, `"Snowpark Container Services (SPCS)"`); a `::before` rule renders that title as a section heading in print mode only, with `page-break-after: avoid` so a section title never orphans at a page bottom.
- `input[type="range"] { display: none; }` — sliders disappear; the inline value `<span>`s next to each slider remain visible.
- `input[type="number"]`, `input[type="text"]`, `select` are stripped of their borders/background and made non-interactive so they read as plain values, not form controls.
- `.scenario-controls` hidden (the scenario toggles are interaction-only); the year/TCV figures stay.
- `.chart-row { grid-template-columns: 1fr; }` and `.chart-container { height: 240px; }` so charts reflow to a single-column layout.

**Protect only the small, indivisible inner units against page splits — never `.section`.** Apply `page-break-inside: avoid` / `break-inside: avoid` to `.kpi-tile`, `.workload-card`, `.scenario-card`, `.chart-row`, `.chart-container`, and `.year-table tr` so a page boundary never cuts a tile, card, chart, or table row in half; `.year-table thead` gets `break-after: avoid` so a header row never strands at the bottom of a page. **Do NOT put `break-inside: avoid` on `.section`.** A `.section` is a top-level content block (e.g. Year-by-Year: an `h2` + two stacked charts + a table) that is frequently *taller than one A4 page*, so the constraint can never be satisfied — it only provokes a large dead gap before the section, then the section splits anyway. Sections must flow freely across pages; protect only the small inner units listed above.

### Browser-injected headers/footers

Chrome and other browsers add their own date+title bar at the top and `file://` URL footer at the bottom of every printed page. **CSS cannot suppress these** — only the user can disable them via *Print dialog → More settings → Headers and footers*. The Print button's `title` tooltip points the SE at this workaround. Don't attempt server-side PDF rendering from this skill.

### Chart canvas reflow

Chart.js canvases keep their on-screen pixel dimensions across the media query change unless explicitly resized. The template wires three handlers — `beforeprint`, `afterprint`, and a `matchMedia('print').change` listener — that all call `chartStacked.resize()` and `chartDonut.resize()` to force a layout pass at the new container width.

### What appears in the PDF

Per project direction, the printed PDF contains the full proposal: header, KPI tiles, year-by-year chart and table, every configuration tab (warehouses / serverless / AI / SPCS / OpenFlow / storage / collaboration / global), scenarios, assumptions, and confirm-required items. Sliders and buttons are hidden; their values stay inline.

---

## Per-feature Tooltips

Every togglable feature label renders with a small info icon `<span class="info-icon" data-tt="<key>" tabindex="0">ⓘ</span>` (Unicode U+24D8). The shared dispatcher attaches `mouseover` / `focusin` listeners on `document` and looks up the body string in a hardcoded `FEATURE_TOOLTIPS` dictionary at the top of `<script>`.

```js
const FEATURE_TOOLTIPS = {
  print_help:  "For a clean PDF: ...",
  snowpipe:    'Continuous file ingestion service. Billed per GB ingested ...',
  cortex_complete: 'LLM completions API. Billed per million input/output tokens by model.',
  cortex_code_cli:       'Cortex Code via Snowflake CLI. ...',
  cortex_code_snowsight: 'Cortex Code surfaced inside Snowsight ...',
  cortex_code_desktop:   'Cortex Code Desktop IDE assistant ...',
  // ~30 more entries covering every togglable feature
};
```

A reusable inline helper `tt(key)` returns the icon HTML. Populators call it next to every feature label, e.g. `<span class="feature-name">Snowpipe</span>${tt('snowpipe')}`.

The tooltip element is a single `<div id="tt-tip">` lazily created on first show. Positioning logic measures the element's `getBoundingClientRect()` and the viewport, places the tooltip above the icon if there's room, or below otherwise; horizontal position is clamped to a minimum 8px viewport gutter. A small triangle is positioned via `[data-pos="above"|"below"]::after`.

The tooltip is hidden by `mouseout`, `focusout`, `Escape`, and is `display: none` in print.

## Group-header rows with units

Every config-tab populator prepends a `.group-header` row above the first card, formatted `[Feature label | Configuration | <unit>]` so SEs can read the live monthly total at a glance:

| Tab | Unit |
|---|---|
| Warehouses | `cr/mo` |
| Serverless | `cr/mo` |
| AI / Cortex | `AI cr/mo` |
| SPCS | `cr/mo` |
| OpenFlow | `cr/mo` |
| Storage | `$/mo` |
| Collaboration | `cr/mo` |

A reusable helper `groupHeaderRow(featureLabel, configLabel, unit, totalElId)` returns the HTML; the right cell is `<span id="<totalElId>">0</span> <unit>`. Each panel uses an id like `gh-total-workloads`, `gh-total-serverless`, etc. `recalculate()` calls `updateGroupHeaderTotals()` which re-computes the per-panel monthly figure (workloads = sum of `whMonthlyCredits`; serverless = `calcServerlessCredits()`; AI = `calcAICredits()`; SPCS = `calcSPCSCost()`; OpenFlow = sum of `connections * vcpu * hours * 0.0225`; storage = `storageForYear(1) * storage_rate`; collaboration = `calcCollabCost()`) and writes to each id.

CSS: `.group-header { display: grid; grid-template-columns: 1.5fr 2fr auto; padding: 6px 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--gray-600); background: var(--gray-100); border-bottom: 1px solid var(--sf-divider); }`. The unit cell uses navy bold for the live number.

## Save Version button

Next to the Print button: `<button class="save-btn" onclick="saveSnapshot()">Save Version</button>`. Hidden in print.

`saveSnapshot()`:

1. Reads `SIZING_SPEC.meta.version_number` (initialised to `1` by SKILL.md Phase 4) and increments by 1.
2. Reads `'<!DOCTYPE html>\n' + document.documentElement.outerHTML`.
3. Replaces the sentinel-wrapped block:

   ```html
   <script>
   const PRICING_DATA = ...;
   /* __SIZING_SPEC_BEGIN__ */
   const SIZING_SPEC = ...;
   /* __SIZING_SPEC_END__ */
   ...
   ```

   with a fresh `JSON.stringify(SIZING_SPEC)` snapshot reflecting all current edits. The sentinel comments are emitted by the template; saved files re-emit them so successive saves work.

4. Builds filename `<slug>-<contract_years>year-sizing-v<version_number>-<YYYY-MM-DD>.html` and triggers a browser download via Blob URL.

The serialisation only replaces `SIZING_SPEC` because all UI state and calculation output is derived from it. PRICING_DATA is unchanged. The brand-fonts CSS, Chart.js script tag, and template scaffold are inherited from the live DOM verbatim.

If the saved file is opened in a browser and the SE saves again, the auto-incrementing version number continues from the embedded value (v3 → v4 → v5).

---

## JS Calculation Engine

### Constants (at top of `<script>`)

```javascript
const PRICING_DATA = /* paste full snowflake_pricing_master.json here */;
const SIZING_SPEC  = /* paste generated spec JSON here */;
```

### Birdbox Ramp Curves (replaces legacy `growth_rates` array)

The legacy `SIZING_SPEC.growth_rates` array is **gone**. Each workload row carries its own `dev_start_month`, `go_live_month`, `ramp_curve` fields. `meta.default_*` fields seed defaults for new rows. `meta.annual_growth_rate` drives year-2+ scaling for all categories.

```javascript
function rampExponentFor(curve) {
  const exp = (PRICING_DATA && PRICING_DATA.ramp_curves && PRICING_DATA.ramp_curves.exponents) || {};
  return (typeof exp[curve] === 'number') ? exp[curve] : 1.0;
}
function rampFactorForMonth(devStart, goLive, curve, m) {
  if (curve === 'manual') return (devStart === 1 && goLive === 1) ? 1.0 : 0.0;
  if (m < devStart) return 0;
  if (m >= goLive)  return 1;
  const denom = (goLive - devStart + 1);
  if (denom <= 0) return 1;
  return Math.pow((m - devStart + 1) / denom, rampExponentFor(curve));
}
function rampMultiplierForYear(row, year) {
  // Returns the AVERAGE per-month factor for the 12 months in `year` (year is 1-indexed),
  // multiplied by the cumulative annual-growth factor for years 2+.
  // Caller multiplies by × 12 to get effective months-equivalent of full capacity.
  const m = SIZING_SPEC.meta;
  const annualGrowth = (m.annual_growth_rate != null) ? m.annual_growth_rate : 0.20;
  const devStart = (row && row.dev_start_month != null) ? row.dev_start_month : (m.default_dev_start_month || 2);
  const goLive  = (row && row.go_live_month   != null) ? row.go_live_month   : (m.default_go_live_month   || 11);
  const curve   = (row && row.ramp_curve)              ? row.ramp_curve      : (m.default_ramp_curve || 'linear');
  let avg;
  if (year === 1) {
    let sum = 0;
    for (let mo = 1; mo <= 12; mo++) sum += rampFactorForMonth(devStart, goLive, curve, mo);
    avg = sum / 12;
  } else {
    avg = 1.0;  // year 2+: full capacity, growth handled below
  }
  return avg * Math.pow(1 + annualGrowth, year - 1);
}
function defaultRampMultiplierForYear(year) { return rampMultiplierForYear(null, year); }
```

### Replication / DR cost engine

```javascript
function calcReplicationForYear(year) {
  const rep = SIZING_SPEC.replication;
  if (!rep || rep.enabled === false) {
    return { compute_credits: 0, compute_cost: 0, egress_cost: 0, storage_cost: 0, total_cost: 0,
             active_TB: 0, change_TB: 0, egress_rate: 0 };
  }
  const cr = SIZING_SPEC.meta.credit_rate;
  const yoy = (rep.yoy_pct != null) ? rep.yoy_pct : 0.10;
  const growth = (rep.storage_growth_pct != null) ? rep.storage_growth_pct : 0.15;
  const credPerTB = (rep.compute_credits_per_TB != null) ? rep.compute_credits_per_TB : 4;
  const storageRate = (rep.replica_storage_per_tb_per_month != null) ? rep.replica_storage_per_tb_per_month : 23;

  let activeTB = rep.initial_TB || 0;
  let growthTB = activeTB * growth;
  let changeTB = (rep.monthly_change_TB || 0) * 12;
  for (let y = 2; y <= year; y++) {
    activeTB = activeTB + growthTB;
    growthTB = growthTB * (1 + yoy);
    changeTB = changeTB * (1 + yoy);
  }
  const avgTB = activeTB + (growthTB / 2);
  const matrix = (PRICING_DATA.replication && PRICING_DATA.replication.egress_matrix) || {};
  let egressRate = 0;
  if (rep.source_region && rep.target_region) {
    const row = matrix[rep.source_region];
    if (row && typeof row[rep.target_region] === 'number') egressRate = row[rep.target_region];
  }
  // Year 1: includes initial seed transfer (matches Apr 2026 calculator math).
  // Year 2+: only growth + change (steady-state delta).
  const computeBasisTB = (year === 1) ? (activeTB + growthTB + changeTB) : (growthTB + changeTB);
  const egressBasisTB  = (year === 1) ? (activeTB + growthTB + changeTB) : (growthTB + changeTB);
  const computeCredits = computeBasisTB * credPerTB;
  const computeCost    = computeCredits * cr;
  const egressCost     = egressBasisTB * egressRate;
  const storageCost    = avgTB * storageRate * 12;
  return { compute_credits: computeCredits, compute_cost: computeCost,
           egress_cost: egressCost, storage_cost: storageCost,
           total_cost: computeCost + egressCost + storageCost,
           active_TB: activeTB, change_TB: changeTB, egress_rate: egressRate, avg_TB: avgTB };
}
```

A `<section id="replication-section">` is only rendered (display:block) when `SIZING_SPEC.replication` is present and `enabled !== false`. The panel exposes `source_region`, `target_region`, `initial_TB`, `monthly_change_TB`, `compute_credits_per_TB`, `replica_storage_per_tb_per_month`, `storage_growth_pct`, `yoy_pct` as editable controls. A summary table below shows year-by-year breakdown of compute/egress/storage/total. Region dropdowns are populated from `PRICING_DATA.replication.egress_matrix` keys.

**Configuration tab placement.** The Replication / DR / Migration panel lives as one of the configuration tabs (`#tab-replication`) alongside Warehouses / Serverless / AI / SPCS / OpenFlow / Storage / Collaboration / Global Settings. The card uses the same `workload-card` + `controls-grid` + `justification` formatting as other tabs; its group-header row (`gh-cr-replication`, `gh-d-replication`) shows live monthly credits and dollars. When `SIZING_SPEC.replication` is absent or `enabled: false`, the tab shows a `+ Enable Replication / DR` add-button; clicking it calls `enableReplication()` to seed default values (N. Virginia → Oregon, 0 TB, 4 cr/TB, $23/TB/mo). The Delete button on the active card calls `disableReplication()` (sets `enabled: false`).

**Live header updates.** The proposal header (Customer name, Edition, Cloud + Region, Credit rate, Years) is wrapped in spans with stable IDs (`hdr-customer`, `hdr-edition`, `hdr-cloud`, `hdr-region`, `hdr-credit-rate`, `hdr-years`, `hdr-discount-badge`). `updateHeaderInfo()` synchronises these spans from `SIZING_SPEC.meta` whenever `updateGlobal()` is called from the Global Settings tab, so any change there reflects immediately in the header without a page reload. When `meta.discount.enabled` is true, `#hdr-discount-badge` renders ` (N% off list)` next to the rate (rounded to 1 decimal); otherwise empty.

### Core Functions

```javascript
const WH_CREDITS = { XS:1, S:2, M:4, L:8, XL:16, '2XL':32, '3XL':64, '4XL':128 };

function whMonthlyCredits(w) {
  const rate = WH_CREDITS[w.size] || 1;
  const avgClusters = (w.clusters_min + w.clusters_max) / 2;
  return rate * w.hours_per_day * w.days_per_month * avgClusters;
}

function storageForYear(year) {
  const s = SIZING_SPEC.storage.standard;
  const base = s.raw_tb_year1 / s.compression_ratio;
  const grown = base * Math.pow(1 + s.annual_growth_pct / 100, year - 1);
  const ttOH  = grown * (s.churn_rate_pct / 100) * (s.time_travel_days / 30);
  const fsOH  = grown * (s.churn_rate_pct / 100) * (7 / 30);
  return grown + ttOH + fsOH;
}

function recalculate() {
  const years = SIZING_SPEC.meta.contract_years;
  const cr    = SIZING_SPEC.meta.credit_rate;
  const aiCr  = SIZING_SPEC.meta.ai_credit_rate;
  const sr    = SIZING_SPEC.meta.storage_rate_per_tb;

  const yearData = [];

  for (let y = 1; y <= years; y++) {
    // Per-workload ramp: each warehouse row has its own dev_start/go_live/curve.
    const whCredits = SIZING_SPEC.workloads
      .reduce((sum, w) => sum + whMonthlyCredits(w) * 12 * rampMultiplierForYear(w, y), 0);

    // Serverless / AI / SPCS / OpenFlow / Collab use the meta-default ramp (no per-row data captured).
    const defRamp = defaultRampMultiplierForYear(y);
    const slCredits = calcServerlessCredits() * 12 * defRamp;
    const aiCredits = calcAICredits() * 12 * defRamp;

    // Storage cost (annual)
    const storageCost = storageForYear(y) * sr * 12;

    // SPCS cost (annual)
    const spcsCost = calcSPCSCost() * 12 * defRamp;

    // OpenFlow cost (annual) - sums across openflow.instances[]
    const ofCost = calcOpenflowCost(cr, defRamp);

    // Oracle Openflow (annual, not credit-based)
    const oracleCost = SIZING_SPEC.openflow_oracle.enabled
      ? SIZING_SPEC.openflow_oracle.licensed_cores * (70 + 40) * 12
      : 0;

    // Data transfer & Privatelink (annual)
    const transferCost = calcTransferCost() * 12;

    // Collaboration costs (annual)
    const collabCost = calcCollabCost() * 12 * defRamp;

    // Replication (annual) - has its own growth model (storage_growth_pct + yoy_pct), no ramp multiplier.
    const replication = calcReplicationForYear(y);

    const computeCost  = whCredits  * cr;
    const serverlessCost = slCredits * cr;
    const aiCost       = aiCredits  * aiCr;
    const otherCost    = spcsCost + ofCost + oracleCost + transferCost + collabCost + replication.total_cost;
    const yearTotal    = computeCost + serverlessCost + aiCost + storageCost + otherCost;

    yearData.push({ y, whCredits, slCredits, aiCredits,
                    computeCost, serverlessCost, aiCost, storageCost, otherCost, yearTotal,
                    replicationCost: replication.total_cost,
                    replicationDetail: replication });
  }

  updateKPIs(yearData);
  updateCharts(yearData);
  updateWorkloadCalcs();
  updateScenarios();
  updateReplicationPanel(yearData);
}
```

### `calcServerlessCredits()` — returns monthly credits

```javascript
function calcServerlessCredits() {
  const sl = SIZING_SPEC.serverless;
  let total = 0;
  // Unit-charge features
  if (sl.snowpipe.enabled)
    total += sl.snowpipe.files_per_month / 1000 * 0.0037 * 1000; // approx via GB
  if (sl.snowpipe_streaming.enabled)
    total += sl.snowpipe_streaming.uncompressed_gb_per_month * 0.0037;
  if (sl.snowpipe_streaming_classic.enabled)
    total += sl.snowpipe_streaming_classic.client_instances * 0.01 * 730;
  if (sl.open_catalog.enabled)
    total += sl.open_catalog.requests_per_month_M * 0.5;
  if (sl.telemetry_data_ingest.enabled)
    total += sl.telemetry_data_ingest.gb_per_month * 0.0212;
  if (sl.archive_storage_retrieval.enabled)
    total += sl.archive_storage_retrieval.files_per_month / 1000 * 0.05;
  if (sl.archive_storage_write.enabled)
    total += sl.archive_storage_write.files_per_month / 1000 * 0.05;
  if (sl.logging.enabled)
    total += sl.logging.file_batches_per_month / 1000 * 0.28;
  if (sl.automated_refresh.enabled)
    total += sl.automated_refresh.files_per_month / 1000 * 0.06;
  if (sl.hybrid_tables_requests.enabled)
    total += (sl.hybrid_tables_requests.reads_gb_monthly / 30) +
             (sl.hybrid_tables_requests.writes_gb_monthly / 7.5);
  // Compute-multiplier features (multiplier × 1 cr/hr)
  const computeMultipliers = {
    serverless_tasks: 0.9, serverless_tasks_flex: 0.5, serverless_alerts: 0.9,
    clustered_tables: 2.0, materialized_views: 2.0, search_optimization: 2.0,
    query_acceleration: 1.0, replication: 2.0, backup: 2.0, failsafe_recovery: 0.9,
    data_quality_monitoring: 2.0, trust_center: 1.0, table_optimization: 0.75,
    storage_lifecycle_policy: 0.5, copy_files: 2.0, organization_usage: 1.0,
    sensitive_data_classification: 0.9
  };
  for (const [key, mult] of Object.entries(computeMultipliers)) {
    const f = sl[key];
    if (f && f.enabled) total += f.compute_hours_monthly * mult;
  }
  return total;
}
```

### `calcAICredits()` — returns monthly AI credits

All rates source from `PRICING_DATA.ai_features.*` — no hardcoded numbers. The function looks up rates by model name (Cortex Complete, SI/Agents, Fine-tuning) or by feature name (Cortex Search, Cortex Analyst API, Document AI, AI Parse Document). When a SIZING_SPEC field references a `model` that isn't in the pricing data, the rate falls through to 0.

```javascript
function calcAICredits() {
  const ai = SIZING_SPEC.ai_cortex;
  let total = 0;
  // Cortex Complete - Table 6(a)
  const aiModels = PRICING_DATA.ai_features.cortex_complete.data;
  const getRate = (model, type) => {
    const m = aiModels.find(x => x.model === model);
    return m ? (m[type] || 0) : 0;
  };
  // Snowflake Intelligence / Cortex Agents / Cortex Analyst (via SI or Agents) - Table 6(d)
  const siAgentsModels = (PRICING_DATA.ai_features.intelligence_agents_analyst || {}).data || [];
  const getSIRate = (model, type) => {
    const m = siAgentsModels.find(x => x.model === model);
    return m ? (m[type] || 0) : 0;
  };
  // Other AI features (Cortex Search, Cortex Analyst API, Document AI, AI Parse Document) - Table 6(h)
  const otherFeats = (PRICING_DATA.ai_features.other_ai_features || {}).data || [];
  const getFeatRate = (featureName) => {
    const f = otherFeats.find(x => x.feature === featureName);
    return f ? (f.rate || 0) : 0;
  };

  if (ai.cortex_complete.enabled)
    total += ai.cortex_complete.monthly_input_tokens_M  * getRate(ai.cortex_complete.model, 'input') +
             ai.cortex_complete.monthly_output_tokens_M * getRate(ai.cortex_complete.model, 'output');

  // SI/Agents/Cortex Analyst-via-SI now use cache_write and cache_read tokens too (Table 6d/6e have these columns).
  // Default model claude-4-sonnet if SIZING_SPEC omits it.
  if (ai.cortex_agents.enabled) {
    const model = ai.cortex_agents.model || 'claude-4-sonnet';
    total += (ai.cortex_agents.monthly_input_tokens_M  || 0) * getSIRate(model, 'input') +
             (ai.cortex_agents.monthly_output_tokens_M || 0) * getSIRate(model, 'output') +
             (ai.cortex_agents.monthly_cache_write_tokens_M || 0) * getSIRate(model, 'cache_write') +
             (ai.cortex_agents.monthly_cache_read_tokens_M  || 0) * getSIRate(model, 'cache_read');
  }
  if (ai.snowflake_intelligence.enabled) {
    const model = ai.snowflake_intelligence.model || 'claude-4-sonnet';
    total += (ai.snowflake_intelligence.monthly_input_tokens_M  || 0) * getSIRate(model, 'input') +
             (ai.snowflake_intelligence.monthly_output_tokens_M || 0) * getSIRate(model, 'output') +
             (ai.snowflake_intelligence.monthly_cache_write_tokens_M || 0) * getSIRate(model, 'cache_write') +
             (ai.snowflake_intelligence.monthly_cache_read_tokens_M  || 0) * getSIRate(model, 'cache_read');
  }
  if (ai.cortex_code) {
    const ccModel = ai.cortex_code.model || 'claude-4-sonnet';
    const ccRate = getSIRate(ccModel, 'input');  // blended approximation
    ['cli', 'snowsight', 'desktop'].forEach(surface => {
      const cc = ai.cortex_code[surface];
      if (cc && cc.enabled) {
        const tokensM = cc.developers * cc.queries_per_dev_per_day *
                        cc.avg_tokens_per_query / 1_000_000 * 22;
        total += tokensM * ccRate;
      }
    });
  }
  if (ai.cortex_analyst.enabled)
    total += ai.cortex_analyst.monthly_messages / 1000 * getFeatRate('Cortex Analyst (API)');
  if (ai.cortex_search.enabled)
    total += ai.cortex_search.indexed_data_gb * getFeatRate('Cortex Search');
  if (ai.document_ai.enabled)
    total += ai.document_ai.compute_hours_monthly * getFeatRate('Document AI');
  if (ai.ai_parse_document_layout.enabled)
    total += ai.ai_parse_document_layout.pages_per_month / 1000 * getFeatRate('AI Parse Document - Layout');
  if (ai.ai_parse_document_ocr.enabled)
    total += ai.ai_parse_document_ocr.pages_per_month / 1000 * getFeatRate('AI Parse Document - OCR');

  // Fine-tuning - Table 6(f)
  if (ai.cortex_fine_tuning.enabled) {
    const model = ai.cortex_fine_tuning.model || 'llama3.1-70b';
    const ftData = (PRICING_DATA.ai_features.fine_tuning || {}).data || [];
    const ft = ftData.find(x => x.model === model);
    total += ai.cortex_fine_tuning.training_tokens_M * (ft ? (ft.training || 0) : 0);
  }

  // Utility functions - Table 6(c)
  const utilFuncs = (PRICING_DATA.ai_features.utility_functions || {}).data || [];
  const getUtilRate = (functionName) => {
    const f = utilFuncs.find(x => x.function === functionName);
    return f ? (f.rate || 0) : 0;
  };
  const funcMap = {
    ai_classify: 'AI_CLASSIFY',
    ai_sentiment: 'AI Sentiment',
    ai_summarize: 'Summarize',
    ai_translate: 'AI_TRANSLATE',
    ai_extract: 'AI_EXTRACT (arctic-extract)',
    ai_transcribe: 'AI_TRANSCRIBE'
  };
  for (const [key, featName] of Object.entries(funcMap)) {
    const f = ai.cortex_functions[key];
    if (f && f.enabled) total += f.tokens_M_monthly * getUtilRate(featName);
  }
  if (ai.embeddings.enabled) total += ai.embeddings.tokens_M_monthly * 0.05;
  return total;
}
```

### `updateKPIs(yearData)`

```javascript
function updateKPIs(yearData) {
  const tcv = yearData.reduce((s, y) => s + y.yearTotal, 0);
  const yr1 = yearData[0].yearTotal;
  const totalCredits = yearData.reduce((s, y) => s + y.whCredits + y.slCredits + y.aiCredits, 0);
  document.getElementById('kpi-tcv').textContent       = '$' + fmt(tcv);
  document.getElementById('kpi-yr1').textContent       = '$' + fmt(yr1);
  document.getElementById('kpi-credits').textContent   = fmt(totalCredits) + ' cr';
  document.getElementById('kpi-commit').textContent    = '$' + fmt(tcv);
}
function fmt(n) { return Math.round(n).toLocaleString('en-US'); }
```

### `updateWorkload(id, field, value)` and `updateServerless(key, field, value)`

```javascript
function updateWorkload(id, field, value) {
  const w = SIZING_SPEC.workloads.find(x => x.id === id);
  if (w) { w[field] = value; recalculate(); }
}
function updateServerless(key, field, value) {
  if (SIZING_SPEC.serverless[key]) {
    SIZING_SPEC.serverless[key][field] = value;
    recalculate();
  }
}
```

### `calcSPCSCost()` — returns monthly SPCS credits

```javascript
function calcSPCSCost() {
  if (!SIZING_SPEC.spcs.enabled) return 0;
  const SPCS_GEN1 = { XS_MEM: 1.5, S_MEM: 3, M_MEM: 6, L_MEM: 12, XS_HIPU: 1.5, S_HIPU: 3, M_HIPU: 6 };
  return SIZING_SPEC.spcs.instances.reduce((sum, inst) => {
    if (inst.generation === 'gen2') {
      const gen2Data = PRICING_DATA.spcs.spcs_gen2.data.find(r => r.family === inst.instance_type);
      const cloud = SIZING_SPEC.meta.cloud.toLowerCase();
      const rate = gen2Data ? (gen2Data[cloud] || 0) : 0;
      return sum + rate * inst.hours_monthly * inst.count;
    } else {
      const rate = SPCS_GEN1[inst.instance_type] || 0;
      return sum + rate * inst.hours_monthly * inst.count;
    }
  }, 0);
}
```

### `calcTransferCost()` — returns monthly transfer cost (dollars, not credits)

```javascript
function calcTransferCost() {
  const dt = SIZING_SPEC.data_transfer;
  const pl = SIZING_SPEC.privatelink;
  let total = 0;
  if (dt.enabled) {
    const rate = dt.pattern === 'same_region' ? 0 : (dt.pattern === 'cross_region' ? 0.08 : 0.154);
    total += dt.tb_per_month * 1024 * rate; // TB → GB
  }
  if (pl.enabled) {
    total += pl.endpoints * 7.30; // $0.01/hr/endpoint ≈ $7.30/mo
    total += pl.tb_processed_monthly * 1024 * 0.01; // $0.01/GB
  }
  return total;
}
```

### `calcCollabCost()` — returns monthly collaboration credits

Iterates `SIZING_SPEC.collaboration.accounts[]` (the new list shape; legacy `reader_accounts` is auto-migrated by the template's `normalizeSpec()` IIFE on load). `type` (`reader` | `managed`) is display-only; both bill identically against the named warehouse.

```javascript
function calcCollabCost() {
  const c = SIZING_SPEC.collaboration;
  if (!c || !Array.isArray(c.accounts)) return 0;
  return c.accounts.reduce((sum, a) => {
    if (a.enabled === false) return sum;
    const rate = WH_CREDITS[a.warehouse_size] || 1;
    return sum + rate * (a.hours_per_day || 0) * (a.days_per_month || 0);
  }, 0);
  // Native apps and marketplace are subscription fees, not credits - added to otherCost directly.
}
```

### `calcOpenflowCost(cr, ramp)` — returns annual OpenFlow cost in dollars

Iterates `SIZING_SPEC.openflow.instances[]`; each connector contributes `connections × vcpu × hours × 0.0225 × credit_rate × 12 × ramp`.

```javascript
function calcOpenflowCost(cr, ramp) {
  const of = SIZING_SPEC.openflow;
  if (!of || !of.enabled || !Array.isArray(of.instances)) return 0;
  return of.instances.reduce((sum, inst) => {
    return sum + (inst.source_connections || 0) * (inst.vcpu_per_connection || 0) *
                 (inst.hours_monthly || 0) * 0.0225 * cr * 12 * ramp;
  }, 0);
}
```

---

## Formatting Rules

- Dollar amounts: `$X,XXX` (no cents unless <$10)
- Credit amounts: `X,XXX cr` (integer)
- Percentages: `XX%`
- Large numbers use `toLocaleString('en-US')`

---

## What-if Slider Behaviour

- All sliders fire `oninput` (not `onchange`) for live updates
- Every slider has a visible value display (a `<span>` next to it updated in `oninput`)
- Disabled inputs (feature not enabled) are `opacity: 0.4; pointer-events: none`
- Enabling a feature via toggle immediately enables its inputs and re-runs `recalculate()`

---

## On Page Load

```javascript
document.addEventListener('DOMContentLoaded', () => {
  populateGlobalSettings();
  populateWorkloadCards();
  populateServerlessPanel();
  populateAIPanel();
  populateSPCSPanel();
  populateOpenflowPanel();
  populateStoragePanel();
  populateCollabPanel();
  renderAssumptions();
  recalculate();
});
```
