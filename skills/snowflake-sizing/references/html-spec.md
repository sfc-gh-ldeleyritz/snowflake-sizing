# Snowflake Sizing HTML Specification

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

Do **not** add a Google Fonts link. Brand fonts are inlined via base64 (see Brand Assets below).

---

## Brand Assets

When generating the HTML, read two pre-built files from the plugin's `assets/branding/` directory and inline them:

### Fonts (inside `<style>`)

Use the `Read` tool to read `assets/branding/_brand_fonts.css`. Paste its **entire contents** verbatim as the first block inside `<style>` in `<head>`, before the `:root` block. This inlines Texta, Lato, and Source Code Pro as base64 data URIs — no font CDN required.

### Logo (inside the header div)

Use the `Read` tool to read `assets/branding/_brand_logo.svg`. Paste its contents verbatim where the logo SVG placeholder is. In the header, wrap it as:

```html
<div style="height:36px; display:flex; align-items:center;">
  <!-- paste full contents of _brand_logo.svg here, with height="36" added to the root <svg> element -->
</div>
```

### Favicon (in `<head>`, before `</head>`)

Add this favicon using the Snowflake mark (a small blue snowflake):

```html
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='16' fill='%2329B5E8'/%3E%3Cpath d='M16 4v24M8 8l16 16M24 8L8 24M4 16h24' stroke='white' stroke-width='2.5' stroke-linecap='round'/%3E%3C/svg%3E">
```

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

Table of SPCS instances from `SIZING_SPEC.spcs.instances`. Each row: label, generation (gen1/gen2), instance type selector, count, hours/month, live credit cost. "+ Add instance" button clones the last row.

#### Openflow Tab

Deployment selector (BYOC / SPCS), source connections, vCPU/connection, hours/month, live cost. Plus Oracle Connector toggle with licensed cores.

#### Storage Tab

- Raw TB (year 1): range slider 0–1000
- Compression ratio: select (1x / 2x / 3x / 5x / 7x / 10x)
- Annual growth %: range slider 0–100
- Time-travel days: select (0 / 1 / 7 / 14 / 30 / 90)
- Churn rate %: range slider 0–100
- Live storage breakdown table: compressed TB | time-travel TB | failsafe TB | total TB | monthly $ | annual $

#### Collaboration Tab

Reader accounts toggle + warehouse size + hours/day + days/month.
Native Apps toggle + monthly subscription fee.
Marketplace toggle + monthly subscription fee.

#### Global Settings Tab

- Edition: select (Standard / Enterprise / Business Critical / VPS) — updates credit_rate live
- Cloud: select (AWS / Azure / GCP)
- Region: grouped select populated from PRICING_DATA — updates credit_rate live
- Contract years: select (1 / 2 / 3 / 4 / 5) — adds/removes year bars from chart
- Ramp curve: select (Slowest 55% / Slow 65% / Linear 70% / Fast 80% / Fastest 90%)
- Annual growth %: number input (overrides computed growth_rates)

### 6. Scenario Comparison

Three side-by-side columns rendered as cards:

| | Conservative | Expected | Aggressive |
|---|---|---|---|
| Growth | 10%/yr | 20%/yr | 35%/yr |
| Ramp | Slowest (55%) | Linear (70%) | Fast (80%) |

Each column shows: Year 1 / Year 2 / Year 3 / TCV. The "Expected" column is highlighted with `border: 2px solid var(--sf-blue)`.

Each column has editable growth % and ramp selector so the SE can customise.

#### Scenario Calculation

Each scenario computes its own year-by-year totals using `recalculate()` logic with overridden growth and ramp:

```javascript
function calcScenarioTCV(growthRate, rampYear1) {
  const years = SIZING_SPEC.meta.contract_years;
  const cr    = SIZING_SPEC.meta.credit_rate;
  const aiCr  = SIZING_SPEC.meta.ai_credit_rate;
  const sr    = SIZING_SPEC.meta.storage_rate_per_tb;

  // Build growth_rates: [rampYear1, 1.0, (1+g)^1, (1+g)^2, ...]
  const ramps = [rampYear1];
  for (let y = 1; y < years; y++) {
    ramps.push(Math.pow(1 + growthRate, y)); // y=1 → (1+g)^1, y=2 → (1+g)^2
  }

  let tcv = 0;
  const yearCosts = [];
  for (let y = 1; y <= years; y++) {
    const ramp = ramps[y - 1];
    const whCredits  = SIZING_SPEC.workloads.reduce((s, w) => s + whMonthlyCredits(w) * 12, 0) * ramp;
    const slCredits  = calcServerlessCredits() * 12 * ramp;
    const aiCredits  = calcAICredits() * 12 * ramp;
    const storageCost = storageForYear(y) * sr * 12;
    const spcsCost   = calcSPCSCost() * 12 * ramp;
    const of = SIZING_SPEC.openflow;
    const ofCost = of.enabled ? of.source_connections * of.vcpu_per_connection * of.hours_monthly * 0.0225 * cr * 12 * ramp : 0;
    const oracleCost = SIZING_SPEC.openflow_oracle.enabled ? SIZING_SPEC.openflow_oracle.licensed_cores * 110 * 12 : 0;
    const yearTotal = (whCredits + slCredits) * cr + aiCredits * aiCr + storageCost + spcsCost + ofCost + oracleCost;
    yearCosts.push(yearTotal);
    tcv += yearTotal;
  }
  return { tcv, yearCosts };
}

function updateScenarios() {
  const scenarios = [
    { id: 'conservative', growth: 0.10, ramp: 0.55 },
    { id: 'expected',     growth: 0.20, ramp: 0.70 },
    { id: 'aggressive',   growth: 0.35, ramp: 0.80 },
  ];
  for (const sc of scenarios) {
    const g = parseFloat(document.getElementById(`sc-growth-${sc.id}`)?.value ?? sc.growth);
    const r = parseFloat(document.getElementById(`sc-ramp-${sc.id}`)?.value  ?? sc.ramp);
    const { tcv, yearCosts } = calcScenarioTCV(g, r);
    document.getElementById(`sc-tcv-${sc.id}`).textContent = '$' + fmt(tcv);
    yearCosts.forEach((cost, i) => {
      const el = document.getElementById(`sc-yr${i+1}-${sc.id}`);
      if (el) el.textContent = '$' + fmt(cost);
    });
  }
}
```

Each scenario card must have:
- Editable growth % input: `<input type="number" id="sc-growth-[id]" value="[default]" min="0" max="200" step="5" oninput="updateScenarios()">`
- Editable ramp select: `<select id="sc-ramp-[id]" onchange="updateScenarios()"><option value="0.55">Slowest 55%</option><option value="0.65">Slow 65%</option><option value="0.70" selected>Linear 70%</option><option value="0.80">Fast 80%</option><option value="0.90">Fastest 90%</option></select>`
- Year cost spans: `<span id="sc-yr1-[id]">`, `<span id="sc-yr2-[id]">`, `<span id="sc-yr3-[id]">`
- TCV span: `<span id="sc-tcv-[id]">`

### 7. Assumptions & Open Questions

Two sections rendered from `SIZING_SPEC.assumptions` and `SIZING_SPEC.confirm_required`:

```html
<div class="assumptions-section">
  <h3>Stated Assumptions</h3>
  <ul id="assumptions-list"><!-- rendered from SIZING_SPEC.assumptions --></ul>
</div>
<div class="confirm-section">
  <h3>⚠️ Requires Customer Confirmation</h3>
  <ul id="confirm-list"><!-- rendered from SIZING_SPEC.confirm_required --></ul>
</div>
```

Each `confirm_required` item renders with an orange warning badge and the quantified impact.

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

## JS Calculation Engine

### Constants (at top of `<script>`)

```javascript
const PRICING_DATA = /* paste full snowflake_pricing_master.json here */;
const SIZING_SPEC  = /* paste generated spec JSON here */;
```

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
  const ramps = SIZING_SPEC.growth_rates;

  const yearData = [];

  for (let y = 1; y <= years; y++) {
    const ramp = ramps[y - 1] || ramps[ramps.length - 1];

    // Warehouse credits (annual)
    const whCredits = SIZING_SPEC.workloads
      .reduce((sum, w) => sum + whMonthlyCredits(w) * 12, 0) * ramp;

    // Serverless credits (annual) — each feature uses its own formula
    const slCredits = calcServerlessCredits() * 12 * ramp;

    // AI credits (annual)
    const aiCredits = calcAICredits() * 12 * ramp;

    // Storage cost (annual)
    const storageCost = storageForYear(y) * sr * 12;

    // SPCS cost (annual)
    const spcsCost = calcSPCSCost() * 12 * ramp;

    // Openflow cost (annual)
    const of = SIZING_SPEC.openflow;
    const ofCost = of.enabled
      ? of.source_connections * of.vcpu_per_connection * of.hours_monthly * 0.0225 * cr * 12 * ramp
      : 0;

    // Oracle Openflow (annual, not credit-based)
    const oracleCost = SIZING_SPEC.openflow_oracle.enabled
      ? SIZING_SPEC.openflow_oracle.licensed_cores * (70 + 40) * 12
      : 0;

    // Data transfer & Privatelink (annual)
    const transferCost = calcTransferCost() * 12;

    // Collaboration costs (annual)
    const collabCost = calcCollabCost() * 12 * ramp;

    const computeCost  = whCredits  * cr;
    const serverlessCost = slCredits * cr;
    const aiCost       = aiCredits  * aiCr;
    const otherCost    = spcsCost + ofCost + oracleCost + transferCost + collabCost;
    const yearTotal    = computeCost + serverlessCost + aiCost + storageCost + otherCost;

    yearData.push({ y, whCredits, slCredits, aiCredits, computeCost, serverlessCost, aiCost, storageCost, otherCost, yearTotal });
  }

  updateKPIs(yearData);
  updateCharts(yearData);
  updateWorkloadCalcs();
  updateScenarios();
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

```javascript
function calcAICredits() {
  const ai = SIZING_SPEC.ai_cortex;
  let total = 0;
  const aiModels = PRICING_DATA.ai_features.cortex_complete.data;
  const getRate = (model, type) => {
    const m = aiModels.find(x => x.model === model);
    return m ? (m[type] || 0) : 0;
  };
  if (ai.cortex_complete.enabled)
    total += ai.cortex_complete.monthly_input_tokens_M  * getRate(ai.cortex_complete.model, 'input') +
             ai.cortex_complete.monthly_output_tokens_M * getRate(ai.cortex_complete.model, 'output');
  if (ai.cortex_agents.enabled)
    total += (ai.cortex_agents.monthly_input_tokens_M  * 1.88 +
              ai.cortex_agents.monthly_output_tokens_M * 9.41);
  if (ai.snowflake_intelligence.enabled)
    total += (ai.snowflake_intelligence.monthly_input_tokens_M  * 2.51 +
              ai.snowflake_intelligence.monthly_output_tokens_M * 12.55);
  if (ai.cortex_code.enabled) {
    const tokensM = ai.cortex_code.developers * ai.cortex_code.queries_per_dev_per_day *
                    ai.cortex_code.avg_tokens_per_query / 1_000_000 * 22;
    total += tokensM * 2.51; // via Snowflake Intelligence
  }
  if (ai.cortex_analyst.enabled)
    total += ai.cortex_analyst.monthly_messages / 1000 * 67;
  if (ai.cortex_search.enabled)
    total += ai.cortex_search.indexed_data_gb * 6.3;
  if (ai.document_ai.enabled)
    total += ai.document_ai.compute_hours_monthly * 8;
  if (ai.ai_parse_document_layout.enabled)
    total += ai.ai_parse_document_layout.pages_per_month / 1000 * 3.33;
  if (ai.ai_parse_document_ocr.enabled)
    total += ai.ai_parse_document_ocr.pages_per_month / 1000 * 0.5;
  if (ai.cortex_fine_tuning.enabled)
    total += ai.cortex_fine_tuning.training_tokens_M * 3.40;
  const funcRates = { ai_classify: 1.39, ai_sentiment: 1.60, ai_summarize: 0.10, ai_translate: 1.50, ai_extract: 5.00, ai_transcribe: 1.30 };
  for (const [key, rate] of Object.entries(funcRates)) {
    const f = ai.cortex_functions[key];
    if (f && f.enabled) total += f.tokens_M_monthly * rate;
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

```javascript
function calcCollabCost() {
  const c = SIZING_SPEC.collaboration;
  let total = 0;
  if (c.reader_accounts.enabled) {
    const rate = WH_CREDITS[c.reader_accounts.warehouse_size] || 1;
    total += rate * c.reader_accounts.hours_per_day * c.reader_accounts.days_per_month;
  }
  // Native apps and marketplace are subscription fees, not credits — added to otherCost directly
  return total;
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
