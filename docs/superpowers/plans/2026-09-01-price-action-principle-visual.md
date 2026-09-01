# Price Action Principle Visual Explainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive interactive HTML explainer that makes PA Agent's price-action reasoning chain easy to study.

**Architecture:** A single self-contained HTML file in the thread-scoped visualization directory. CSS defines the dark analysis surface and responsive layout; JavaScript owns one selected pipeline node, updates the detail panel, and toggles Stage 1/Stage 2 emphasis. No network requests or external assets.

**Tech Stack:** HTML, CSS, vanilla JavaScript, inline SVG for the pipeline diagram.

---

### Task 1: Create the interactive explainer

**Files:**
- Create: `/Users/orange/.codex/visualizations/2026/09/01/01a05d94-1126-7590-8140-83d9018ed085/price-action-principle.html`

- [ ] **Step 1: Write the page shell and semantic sections**
  Add a root container, hero summary, pipeline section, detail panel, three-window section, program-vs-AI section, vote/risk sections, and code index.

- [ ] **Step 2: Add the pipeline SVG and local interaction data**
  Define eight clickable nodes with `data-node` and a JavaScript object containing title, meaning, inputs, outputs, and code references. Clicking a node updates the detail panel and selected state.

- [ ] **Step 3: Add responsive styling and accessibility**
  Use CSS grid/flex with a mobile breakpoint at 760px, visible focus states, native buttons, `aria-live` detail updates, and no horizontal overflow.

- [ ] **Step 4: Verify the primary interaction**
  Open the file in a browser, click at least three pipeline nodes and both stage toggles, and confirm the detail panel and visual emphasis update without console errors.

### Task 2: Browser layout verification

**Files:**
- Verify: `/Users/orange/.codex/visualizations/2026/09/01/01a05d94-1126-7590-8140-83d9018ed085/price-action-principle.html`

- [ ] **Step 1: Check desktop width**
  Inspect at approximately 1024px and confirm the pipeline, detail panel, and lower sections fit without clipping or overlap.

- [ ] **Step 2: Check mobile width**
  Inspect at approximately 360px and confirm the pipeline stacks, labels wrap, controls remain usable, and detail text stays inside its container.

- [ ] **Step 3: Finalize the content reference**
  Return the absolute visualization path using the required `visualize` content reference.
