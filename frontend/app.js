"use strict";

const state = {
  user: { username: "Guest concept mode" },
  projects: [],
  view: "overview",
  currentProject: null,
};

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function projectIdValue(project) {
  return String(project?.id ?? project?.project_id ?? project?.db_id ?? "");
}

function money(value) {
  const amount = Number(value || 0);
  return `GHS ${Math.round(amount).toLocaleString("en-GH")}`;
}

function conceptFloorCount(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(50, Math.max(1, Math.trunc(parsed))) : 1;
}

function shortDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("en-GH", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function showToast(message, kind = "success") {
  const host = $("#toast-container");
  if (!host) return;
  const toast = document.createElement("div");
  toast.className = `toast${kind === "error" ? " error" : ""}`;
  toast.textContent = message;
  host.appendChild(toast);
  window.setTimeout(() => toast.remove(), 4000);
}

async function api(path, options = {}) {
  const init = { ...options };
  const headers = new Headers(init.headers || {});
  if (init.body && typeof init.body === "object" && !(init.body instanceof FormData) && !(init.body instanceof Blob)) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(init.body);
  }
  init.headers = headers;

  let response;
  try {
    response = await fetch(path, init);
  } catch (error) {
    throw new Error("Could not reach the app. Check your connection and try again.");
  }

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    if (contentType.includes("application/json")) {
      const data = await response.json().catch(() => ({}));
      message = data.detail || data.message || message;
    } else {
      const body = await response.text().catch(() => "");
      if (body && body.length < 180) message = body;
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  if (contentType.includes("application/json")) return response.json();
  return response.blob();
}

function showWorkspace() {
  const username = "Guest concept mode";
  $("#user-label").textContent = username;
  $("#user-avatar").textContent = "G";
  updateNavCount();
  setView("overview");
}

function boot() {
  state.user = { username: "Guest concept mode" };
  state.projects = [];
  showWorkspace();
}

function updateNavCount() {
  $("#nav-project-count").textContent = String(state.projects.length);
}

function setView(view) {
  state.view = view;
  state.currentProject = null;
  $("#sidebar").classList.remove("open");
  const titles = {
    overview: ["YOUR WORKSPACE", "Overview"],
    create: ["PROJECT PLANNING", "New concept"],
    projects: ["TEMPORARY SESSION", "Session concepts"],
    contractors: ["LOCAL DIRECTORY", "Contractor directory"],
  };
  const [eyebrow, title] = titles[view] || titles.overview;
  $("#page-eyebrow").textContent = eyebrow;
  $("#page-title").textContent = title;
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  const content = $("#view-content");
  if (view === "overview") content.innerHTML = overviewMarkup();
  else if (view === "create") content.innerHTML = createMarkup();
  else if (view === "projects") content.innerHTML = projectsMarkup();
  else if (view === "contractors") content.innerHTML = contractorsMarkup();
  if (view === "create") initCreateForm();
  if (view === "contractors") initContractorForm();
}

function projectStatusClass(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("preliminary checks passed") || value.includes("compliant")) return "status-good";
  if (value.includes("review") || value.includes("conditional") || value.includes("non-compliant")) return "";
  return "status-neutral";
}

function projectCard(project) {
  const type = escapeHtml(project.building_type || "residential");
  const description = escapeHtml(project.description || `${project.floors || 1} floor · ${project.area_sqm || 0} m²`);
  return `
    <article class="project-card">
      <button class="card-open" type="button" data-action="project-open" data-project-id="${escapeHtml(projectIdValue(project))}" aria-label="Open ${escapeHtml(project.name)}"></button>
      <div class="project-card-top"><div class="project-card-icon" aria-hidden="true">⌂</div><span class="status-badge ${projectStatusClass(project.compliance_status)}">${escapeHtml(project.compliance_status || "Review required")}</span></div>
      <h3>${escapeHtml(project.name || `${type} concept`)}</h3>
      <p class="project-description">${description}</p>
      <div class="project-meta"><span class="meta-pill">${escapeHtml(project.location || "Ghana")}</span><span class="meta-pill">${Number(project.floors || 1)} floor${Number(project.floors || 1) === 1 ? "" : "s"}</span><span class="meta-pill">${Number(project.area_sqm || 0).toLocaleString("en-GH")} m²</span></div>
      <div class="project-card-bottom"><strong>${money(project.estimated_cost_ghs)}</strong><span>${shortDate(project.created_at)}</span></div>
    </article>`;
}

function overviewMarkup() {
  const projects = state.projects || [];
  const totalEstimate = projects.reduce((sum, project) => sum + Number(project.estimated_cost_ghs || 0), 0);
  const needsReview = projects.filter((project) => !String(project.compliance_status || "").toLowerCase().includes("preliminary checks passed")).length;
  const avgArea = projects.length ? Math.round(projects.reduce((sum, p) => sum + Number(p.area_sqm || 0), 0) / projects.length) : 0;
  const recent = projects.slice(0, 4);
  return `
    <section class="welcome-banner">
      <div class="welcome-copy"><span class="eyebrow">GOOD PLANNING STARTS WITH A CLEAR BRIEF</span><h2>Bring your next building idea into focus.</h2><p>Create a schematic plan, review an indicative GHS estimate and explore a first-pass schedule — all from one short description.</p></div>
      <button class="button" type="button" data-view="create">＋ Start a concept</button>
    </section>
    <section class="stats-grid" aria-label="Project summary">
      <article class="stat-card"><div class="stat-head"><span>Session concepts</span><span class="stat-icon">▤</span></div><div class="stat-value">${projects.length}</div><div class="stat-foot">Temporary in this browser</div></article>
      <article class="stat-card"><div class="stat-head"><span>Indicative portfolio</span><span class="stat-icon">₵</span></div><div class="stat-value">${money(totalEstimate)}</div><div class="stat-foot">Early estimates, not quotes</div></article>
      <article class="stat-card"><div class="stat-head"><span>Need professional review</span><span class="stat-icon">!</span></div><div class="stat-value">${needsReview}</div><div class="stat-foot">Every concept needs local validation</div></article>
      <article class="stat-card"><div class="stat-head"><span>Average floor area</span><span class="stat-icon">⌗</span></div><div class="stat-value">${avgArea.toLocaleString("en-GH")} <small style="font-size:12px;font-weight:650">m²</small></div><div class="stat-foot">Across saved concepts</div></article>
    </section>
    <section class="overview-lower">
      <div class="panel"><div class="panel-heading"><div><h3>Recent concepts</h3><p>Your latest generated project starting points.</p></div><button class="panel-link" type="button" data-view="projects">View all →</button></div>
        ${recent.length ? `<div class="project-list">${recent.map(projectRow).join("")}</div>` : emptyMarkup("No concepts yet", "Create a first project brief to see your plan, schedule and estimate here.", "Start a concept", "create")}
      </div>
      <aside class="quick-card"><div class="quick-card-inner"><span class="quick-icon">✦</span><h3>Start with a good brief</h3><p>Include building type, floors, bedrooms, total floor area, location and any special requirements. The system will make its assumptions visible.</p><button class="button button-secondary" type="button" data-view="create">Write a project brief <span>→</span></button></div></aside>
    </section>`;
}

function projectRow(project) {
  return `<button class="project-row" type="button" data-action="project-open" data-project-id="${escapeHtml(projectIdValue(project))}"><span class="project-thumb" aria-hidden="true">⌂</span><span class="project-row-copy"><strong>${escapeHtml(project.name || "Untitled concept")}</strong><span>${escapeHtml(project.location || "Ghana")} · ${Number(project.floors || 1)} floor${Number(project.floors || 1) === 1 ? "" : "s"} · ${Number(project.area_sqm || 0)} m²</span></span><span class="project-row-cost"><strong>${money(project.estimated_cost_ghs)}</strong><span>${shortDate(project.created_at)}</span></span></button>`;
}

function emptyMarkup(title, description, buttonLabel, view) {
  return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">⌂</div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p>${buttonLabel ? `<button class="button button-primary" type="button" data-view="${escapeHtml(view)}">${escapeHtml(buttonLabel)} <span>→</span></button>` : ""}</div>`;
}

function createMarkup() {
  const locations = ["Auto-detect from brief", "Accra", "Tema", "Kumasi", "Tamale", "Cape Coast", "Takoradi", "Ho", "Koforidua", "Obuasi", "Bolgatanga", "Aflao"];
  return `
    <div class="page-intro"><div><div class="page-kicker">CONCEPT GENERATOR</div><h2>Describe what you want to build.</h2><p>Write naturally. We’ll extract a preliminary brief and produce a schematic layout, rough cost allocation, 3D massing file and a planning timeline.</p></div></div>
    <div class="creation-grid">
      <section class="panel">
        <div class="panel-heading"><div><h3>Project brief</h3><p>More detail helps the concept match your intent.</p></div><span class="meta-pill">Ghana · GHS</span></div>
        <form id="create-form" class="creation-form">
          <label class="form-field"><span>What are you planning?</span><textarea id="project-description" required minlength="10" maxlength="75000" placeholder="Example: A 3-bedroom, 2-bathroom bungalow in Kumasi, about 150 sqm total floor area, cement blocks, metal roof, with a porch and solar power."></textarea><small class="form-hint">Long briefs are supported: up to 75,000 characters, including a detailed 5,000-word brief. State total floor area across all levels if you know it. This tool creates a concept, not permit-ready drawings.</small><small id="project-description-counter" class="form-hint">0 words · 0 / 75,000 characters</small></label>
          <label class="form-field"><span>Project name <small>Optional</small></span><input id="project-name" type="text" maxlength="120" placeholder="e.g. Adum Family Home"></label>
          <div class="input-grid">
            <label class="form-field"><span>Project location</span><select id="project-location">${locations.map((location, index) => `<option value="${index === 0 ? "auto" : escapeHtml(location)}" ${index === 0 ? "selected" : ""}>${escapeHtml(location)}</option>`).join("")}</select><small class="form-hint">Choose a city or use the location mentioned in your brief.</small></label>
            <label class="form-field"><span>Budget ceiling <small>Optional · GHS</small></span><input id="project-budget" type="number" min="1" step="1000" placeholder="e.g. 500000"><small class="form-hint">Used only to compare the estimate with your target.</small></label>
          </div>
          <label class="form-field"><span>Bathroom planning preference</span><select id="bathroom-template-choice"><option value="keep" selected>Keep the bathroom count in my brief</option><option value="apply">Apply the Ghana-focused planning template suggestion</option></select><small class="form-hint">The template is optional. It can suggest additional sanitary spaces for the concept, but it is not a building-code or permit determination.</small></label>
          <label class="form-field"><span>Concept direction</span><select id="market-focus"><option value="balanced" selected>Balanced · Ghana context + contemporary living</option><option value="ghana_context">Ghana-context · site, climate and supply prompts</option><option value="global_modern">Global-modern · flexibility and long-term comfort prompts</option></select><small class="form-hint">Creates transparent briefing prompts, not market scoring, code compliance, investment advice or a different approved design.</small></label>
          <details class="disclaimer-box"><summary><strong>Professional handoff details</strong> <span>Optional · for your appointed architect/engineer</span></summary><p>These details create a printable handoff brief and JSON export. They do not create a permit drawing or approval.</p><div class="input-grid"><label class="form-field"><span>Site width · m</span><input id="handoff-site-width" type="number" min="0.1" max="100000" step="0.1" placeholder="e.g. 30"></label><label class="form-field"><span>Site depth · m</span><input id="handoff-site-depth" type="number" min="0.1" max="100000" step="0.1" placeholder="e.g. 40"></label><label class="form-field"><span>Target footprint · m²</span><input id="handoff-footprint" type="number" min="0.1" max="1000000" step="0.1" placeholder="e.g. 120"></label><label class="form-field"><span>Road orientation</span><select id="handoff-road-orientation"><option value="">Not supplied</option><option>North</option><option>East</option><option>South</option><option>West</option></select></label></div><label class="form-field"><span>Local authority / assembly</span><input id="handoff-authority" type="text" maxlength="160" placeholder="e.g. Kumasi Metropolitan Assembly"></label><label class="form-field"><span>Priorities for your professional team</span><textarea id="handoff-priorities" maxlength="1500" placeholder="Access, daylight, drainage, accessibility, future expansion, materials, etc."></textarea></label></details>
          <div class="form-actions"><span>Rule-based first pass; review every extracted assumption.</span><button id="generate-button" class="button button-primary" type="submit">Generate concept <span>→</span></button></div>
        </form>
      </section>
      <aside class="tip-panel"><div class="page-kicker">GET A BETTER RESULT</div><h3>Brief checklist</h3><p>Use plain English and call out anything that should shape the first concept.</p><div class="example-prompt"><strong>Example brief</strong>“A 2-storey family house in Kumasi, 4 bedrooms, 3 bathrooms, 220 m² total floor area, block walls, metal roof, a balcony and solar power.”</div><div class="safety-list"><span><i>✓</i> Building type and number of floors</span><span><i>✓</i> Bedrooms, bathrooms and total area</span><span><i>✓</i> Location, materials and special features</span><span><i>!</i> Estimates use starter rates; verify current prices</span><span><i>!</i> Plans and code checks need a professional review</span></div></aside>
    </div>
    <div id="generated-output" class="generated-wrap"></div>`;
}

function initCreateForm() {
  const form = $("#create-form");
  if (!form) return;
  const descriptionInput = $("#project-description");
  const descriptionCounter = $("#project-description-counter");
  const updateDescriptionCounter = () => {
    if (!descriptionInput || !descriptionCounter) return;
    const text = descriptionInput.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    descriptionCounter.textContent = `${words.toLocaleString("en-GH")} words · ${descriptionInput.value.length.toLocaleString("en-GH")} / 75,000 characters`;
  };
  descriptionInput?.addEventListener("input", updateDescriptionCounter);
  updateDescriptionCounter();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const description = $("#project-description").value.trim();
    const projectName = $("#project-name").value.trim();
    const location = $("#project-location").value;
    const budgetValue = $("#project-budget").value.trim();
    const output = $("#generated-output");
    const button = $("#generate-button");
    button.disabled = true;
    output.innerHTML = '<div class="loading-block"><span class="spinner"></span><span>Turning your brief into a first-pass project concept…</span></div>';
    try {
      const payload = {
        description,
        location: location === "auto" ? null : location,
        apply_bathroom_template: $("#bathroom-template-choice").value === "apply",
        market_focus: $("#market-focus").value,
      };
      const optionalNumber = (selector) => {
        const value = $(selector).value.trim();
        return value ? Number(value) : null;
      };
      const handoff = {
        site_width_m: optionalNumber("#handoff-site-width"),
        site_depth_m: optionalNumber("#handoff-site-depth"),
        building_footprint_sqm: optionalNumber("#handoff-footprint"),
        road_orientation: $("#handoff-road-orientation").value,
        local_authority: $("#handoff-authority").value.trim(),
        planning_priorities: $("#handoff-priorities").value.trim(),
      };
      if (Object.values(handoff).some((value) => value !== null && value !== "")) payload.handoff = handoff;
      if (projectName) payload.name = projectName;
      if (budgetValue) payload.budget = Number(budgetValue);
      const result = await api("/api/public/project/generate", { method: "POST", body: payload });
      state.projects = [result, ...state.projects.filter((project) => projectIdValue(project) !== projectIdValue(result))];
      updateNavCount();
      output.innerHTML = projectDetailMarkup(result, true);
      await initProjectArtifacts(result);
      showToast("Concept generated. Review its assumptions before using it.");
    } catch (error) {
      output.innerHTML = `<div class="form-error" role="alert">${escapeHtml(error.message)}</div>`;
      showToast(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
}

function projectsMarkup() {
  const projects = state.projects || [];
  const description = "Guest concepts are temporary and their generated links expire after one hour.";
  return `<div class="page-intro"><div><div class="page-kicker">THIS BROWSER SESSION</div><h2>Temporary concepts</h2><p>${description}</p></div><button class="button button-primary" type="button" data-view="create">＋ New concept</button></div>${projects.length ? `<div class="project-grid">${projects.map(projectCard).join("")}</div>` : emptyMarkup("No concepts in this session", "Create a brief to generate a temporary concept without signing in.", "Create a concept", "create")}`;
}

function projectDetailMarkup(project, embedded = false) {
  const spec = project.spec || {};
  const cost = project.cost || {};
  const compliance = project.compliance || {};
  const id = projectIdValue(project);
  const isPublic = Boolean(project.is_public);
  const displayTypology = spec.project_typology === "apartment" ? "Apartment" : (spec.building_type || project.building_type || "Residential");
  const floorCount = conceptFloorCount(spec.floors || project.floors || 1);
  const configuredFloor = Number(spec.design_studio?.active_floor || 1);
  const initialPlanFloor = Math.min(floorCount, Math.max(1, Number.isFinite(configuredFloor) ? configuredFloor : 1));
  const floorPlanTabs = floorCount > 1 ? `<div id="plan-floor-tabs" class="plan-floor-tabs" role="group" aria-label="Choose a concept floor plan">${Array.from({ length: floorCount }, (_, index) => {
    const floor = index + 1;
    const label = floor === 1 ? "Ground" : `Level ${floor}`;
    return `<button class="plan-floor-button ${floor === initialPlanFloor ? "active" : ""}" type="button" data-plan-floor="${floor}" aria-pressed="${floor === initialPlanFloor}">${label}</button>`;
  }).join("")}</div>` : "";
  const planStyleTabs = `<div class="concept-style-tabs" role="group" aria-label="Choose 2D concept plan style"><button class="concept-style-button active" type="button" data-plan-style="technical" aria-pressed="true">Technical</button><button class="concept-style-button" type="button" data-plan-style="presentation" aria-pressed="false">Presentation</button></div>`;
  const modelStyleTabs = `<div class="concept-style-tabs" role="group" aria-label="Choose 3D concept view"><button class="concept-style-button active" type="button" data-model-style="dollhouse" aria-pressed="true">Dollhouse</button><button class="concept-style-button" type="button" data-model-style="exterior" aria-pressed="false">Exterior</button></div>`;
  const warningItems = [
    ...(compliance.issues || []).map((item) => ({ item, pass: false })),
    ...(compliance.warnings || []).slice(0, 6).map((item) => ({ item, pass: false })),
    ...(compliance.passes || []).slice(0, 2).map((item) => ({ item, pass: true })),
  ];
  const materials = cost.materials || [];
  return `
    ${embedded ? `<div class="panel-heading" style="margin-bottom:14px"><div><div class="page-kicker">GENERATED CONCEPT</div><h3>${escapeHtml(project.name || `${spec.building_type || "Building"} · ${spec.location || "Ghana"}`)}</h3><p>Generated ${shortDate(project.created_at)} · Concept-stage outputs are approximate.</p></div><span class="status-badge">${escapeHtml(compliance.status || project.compliance_status || "Review required")}</span></div>` : `<div class="detail-toolbar"><div class="detail-toolbar-left"><button class="back-button" type="button" data-action="back-projects">← Projects</button><h2 class="detail-title">${escapeHtml(project.name || "Project concept")}</h2></div>${isPublic ? `<div class="disclaimer-box public-concept-note">Temporary guest concept · artifact links expire after one hour.</div>` : `<div class="detail-actions"><button class="button button-secondary" type="button" data-action="download-model" data-project-id="${escapeHtml(id)}">↓ Download 3D</button><button class="button button-secondary" type="button" data-action="print-handoff" data-project-id="${escapeHtml(id)}">Print handoff</button><button class="button button-quiet" type="button" data-action="download-handoff" data-project-id="${escapeHtml(id)}">Handoff JSON</button><button class="button button-quiet" type="button" data-action="delete-project" data-project-id="${escapeHtml(id)}">Delete</button></div>`}</div>`}
    <section class="detail-summary"><div class="detail-summary-main"><span class="status-badge ${projectStatusClass(compliance.status || project.compliance_status)}">${escapeHtml(compliance.status || project.compliance_status || "Review required")}</span><p>${escapeHtml(project.description || spec.raw_text || "No description")}</p><div class="detail-metrics"><span class="detail-metric"><strong>${escapeHtml(displayTypology)}</strong></span><span class="detail-metric"><strong>${Number(spec.floors || project.floors || 1)}</strong> floor${Number(spec.floors || project.floors || 1) === 1 ? "" : "s"}</span><span class="detail-metric"><strong>${Number(spec.area_sqm || project.area_sqm || 0).toLocaleString("en-GH")} m²</strong> total area</span><span class="detail-metric"><strong>${Number(spec.bedrooms || 0)}</strong> bed · <strong>${Number(spec.bathrooms || 0)}</strong> bath</span><span class="detail-metric">${escapeHtml(spec.location || project.location || "Ghana")}</span></div></div><div class="detail-cost"><span>Indicative estimate</span><strong>${money(cost.total_ghs ?? project.estimated_cost_ghs)}</strong><small>GHS · concept estimate</small></div></section>
    <section class="panel studio-console" aria-label="Design studio console">
        <div class="panel-heading studio-console-heading"><div><div class="page-kicker">CONCEPT STUDIO</div><h3>2D / 3D design console</h3><p>Compare the generated plan and massing model. All geometry is a concept study for professional review.</p></div><div class="studio-view-toggle" role="group" aria-label="Choose studio view"><button class="studio-view-button" type="button" data-action="studio-view" data-studio-view="2d" aria-pressed="false">2D plan</button><button class="studio-view-button active" type="button" data-action="studio-view" data-studio-view="split" aria-pressed="true">Split</button><button class="studio-view-button" type="button" data-action="studio-view" data-studio-view="3d" aria-pressed="false">3D massing</button></div></div>
        <div id="studio-console" class="studio-viewport" data-studio-mode="split">
          <section class="studio-canvas-pane" data-studio-pane="plan"><div class="studio-canvas-header"><span>01 · Floor-plan study</span><span id="plan-floor-indicator" class="studio-canvas-chip">${floorCount > 1 ? `Level ${initialPlanFloor} of ${floorCount}` : "Approximate dimensions"}</span></div>${planStyleTabs}${floorPlanTabs}<div class="plan-stage"><img id="plan-image" alt="Technical schematic concept floor plan, level ${initialPlanFloor} of ${floorCount}" src="" /><span class="artifact-loading" id="plan-loading">Preparing floor plan…</span></div></section>
          <section class="studio-canvas-pane" data-studio-pane="model"><div class="studio-canvas-header"><span>02 · 3D concept study</span><span class="studio-canvas-chip">${floorCount} level${floorCount === 1 ? "" : "s"} · orbit to inspect</span></div>${modelStyleTabs}<div class="model-stage"><model-viewer id="model-viewer" camera-controls touch-action="pan-y" shadow-intensity="0.72" exposure="1" interaction-prompt="auto" loading="eager" reveal="auto" camera-orbit="45deg 62deg auto" alt="Interactive 3D cutaway dollhouse concept model"><span slot="poster" class="artifact-loading" id="model-loading">Preparing 3D concept…</span></model-viewer><canvas id="model-canvas" hidden data-floors="${Number(spec.floors || project.floors || 1)}" data-area="${Number(spec.area_sqm || project.area_sqm || 100)}" aria-label="Fallback schematic 3D building massing"></canvas><span class="artifact-loading" id="model-error" hidden>Could not load the GLB preview. You can still download the model.</span></div></section>
          <aside class="studio-inspector" aria-label="Spatial-program inspector"><div class="studio-inspector-heading"><span>SPATIAL PROGRAM</span><span class="studio-live-dot">CONCEPT</span></div><div class="studio-program-stats"><span><strong>${Number(spec.area_sqm || project.area_sqm || 0).toLocaleString("en-GH")}</strong> m² total</span><span><strong>${Number(spec.floors || project.floors || 1)}</strong> level${Number(spec.floors || project.floors || 1) === 1 ? "" : "s"}</span></div><div id="studio-spatial-program" class="studio-program-list"><div class="artifact-loading">Loading room program…</div></div><div id="studio-market-direction" class="studio-market-direction"><div class="artifact-loading">Loading concept direction…</div></div><div class="studio-review-note"><strong>Review state</strong><span>${escapeHtml(compliance.status || project.compliance_status || "Professional review required")}</span><p>Not a code screen, structural check, permit drawing, IFC model or construction issue.</p></div></aside>
        </div>
        <div class="studio-quantity-lens" aria-label="Concept quantity lens"><div class="studio-quantity-heading"><span>CONCEPT QTO LENS</span><small>Transparent allowances · not a procurement or construction quantity</small></div><div class="studio-quantity-metrics"><div><span>Indicative cost</span><strong>${money(cost.total_ghs ?? project.estimated_cost_ghs)}</strong></div><div><span>Gross floor area</span><strong>${Number(spec.area_sqm || project.area_sqm || 0).toLocaleString("en-GH")} m²</strong></div><div id="studio-qto-summary"><span>Quantity allowances load with the concept workspace.</span></div><div class="studio-carbon-note">Carbon/LCA requires verified material quantities and EPD inputs.</div></div></div>
    </section>
    <div class="detail-grid">
      <div class="detail-column">
        <section id="workbench-panel" class="panel workbench-panel"><div class="panel-heading"><div><h3>Design-to-delivery workbench</h3><p>Loading editable concept rooms, transparent take-off and delivery controls…</p></div></div><div class="artifact-loading">Preparing workbench…</div></section>
        <section class="panel"><div class="panel-heading"><div><h3>First-pass project schedule</h3><p>Sequential planning timeline with an indicative seasonal allowance.</p></div><span class="meta-pill">${Number(spec.floors || project.floors || 1)} floor${Number(spec.floors || project.floors || 1) === 1 ? "" : "s"}</span></div><div id="schedule-container"><div class="artifact-loading">Preparing schedule…</div></div></section>
      </div>
      <div class="detail-column secondary">
        <section class="panel"><div class="panel-heading"><div><h3>Cost overview</h3><p>Budget allocation by project category.</p></div>${isPublic ? `<span class="meta-pill">Temporary preview</span>` : `<button class="panel-link" type="button" data-action="download-cost" data-project-id="${escapeHtml(id)}">Download CSV →</button>`}</div><div class="cost-hero"><div><span>Indicative total</span><strong>${money(cost.total_ghs ?? project.estimated_cost_ghs)}</strong></div><div class="cost-range"><span>Planning range ±15%</span><strong>${money(cost.indicative_range_low_ghs)} – ${money(cost.indicative_range_high_ghs)}</strong></div></div><table class="cost-table"><tbody><tr><td>Materials allocation</td><td>${money(cost.total_materials_ghs)}</td></tr><tr><td>Labour allowance</td><td>${money(cost.labour_cost_ghs)}</td></tr><tr><td>Professional fees allowance</td><td>${money(cost.professional_fees_ghs)}</td></tr><tr><td>Contingency allowance</td><td>${money(cost.contingency_ghs)}</td></tr></tbody></table>${cost.budget_constraint_ghs ? `<div class="disclaimer-box">Budget target: <strong>${money(cost.budget_constraint_ghs)}</strong> · ${cost.within_budget ? "Indicative estimate is within target." : "Indicative estimate exceeds target."}</div>` : ""}<div class="disclaimer-box">${escapeHtml(cost.disclaimer || "Illustrative estimate only; obtain current local prices and a quantity-surveyor estimate.")}</div><table class="cost-table"><tbody>${materials.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${money(item.estimated_amount_ghs)}</td></tr>`).join("")}</tbody></table></section>
        <section class="panel"><div class="panel-heading"><div><h3>Preliminary review</h3><p>Automated screening only — not a code approval.</p></div></div><div class="compliance-status"><span class="status-badge ${projectStatusClass(compliance.status || project.compliance_status)}">${escapeHtml(compliance.status || project.compliance_status || "Review required")}</span></div><ul class="compliance-list">${warningItems.map((entry) => `<li class="${entry.pass ? "pass" : ""}">${escapeHtml(entry.item)}</li>`).join("") || `<li>${escapeHtml(compliance.disclaimer || "Have the design reviewed by licensed local professionals and the relevant authority.")}</li>`}</ul><div class="disclaimer-box">${escapeHtml(compliance.disclaimer || "For early planning only. Confirm all code, permit, structural and site requirements locally.")}</div></section>
        <section class="panel"><div class="panel-heading"><div><h3>Assumptions</h3><p>Values extracted from your brief.</p></div></div><table class="cost-table"><tbody><tr><td>Material concept</td><td>${escapeHtml(String(spec.material || "—").replaceAll("_", " "))}</td></tr><tr><td>Roof concept</td><td>${escapeHtml(String(spec.roof_type || "—").replaceAll("_", " "))}</td></tr><tr><td>Foundation concept</td><td>${escapeHtml(String(spec.foundation_type || "—").replaceAll("_", " "))}</td></tr><tr><td>Special features</td><td>${escapeHtml((spec.special_features || []).join(", ") || "None specified")}</td></tr>${spec.planning_guidance ? `<tr><td>Planning template</td><td>${spec.planning_guidance.applied_bathroom_template ? "Applied at your request" : "Suggestions only — your stated bathroom count kept"}</td></tr>` : ""}</tbody></table>${spec.planning_guidance ? `<div class="disclaimer-box">${escapeHtml(spec.planning_guidance.disclaimer || "Planning suggestions only; obtain a professional review.")}</div>` : ""}<div class="disclaimer-box">${escapeHtml(cost.rate_note || "The included starter cost rates are not independently verified.")}</div></section>
      </div>
    </div>`;
}

async function openProject(projectId) {
  try {
    const localProject = state.projects.find((project) => projectIdValue(project) === String(projectId));
    const project = localProject?.is_public ? localProject : await api(`/api/projects/${Number(projectId)}`);
    state.currentProject = project;
    state.view = "projectDetail";
    $("#page-eyebrow").textContent = "PROJECT DETAILS";
    $("#page-title").textContent = "Project concept";
    $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === "projects"));
    $("#view-content").innerHTML = projectDetailMarkup(project, false);
    await initProjectArtifacts(project);
    $("#sidebar").classList.remove("open");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function initProjectArtifacts(project) {
  const id = projectIdValue(project);
  const isPublic = Boolean(project.is_public);
  const artifactUrl = (name) => {
    if (isPublic) {
      if (name === "model") return project.model_3d_url;
      if (name === "dollhouse") return project.dollhouse_3d_url || project.model_3d_url;
      if (name === "plan") return project.plan_url;
      if (name === "technical-plan") return project.technical_plan_url || project.plan_url;
      return project.schedule_url;
    }
    const artifact = name === "model" ? "model.glb" : name === "dollhouse" ? "dollhouse.glb" : name === "plan" || name === "technical-plan" ? "plan.svg" : "schedule.json";
    return `/api/projects/${id}/artifacts/${artifact}`;
  };
  const modelViewer = $("#model-viewer");
  const fallbackCanvas = $("#model-canvas");
  const modelError = $("#model-error");
  const showFallbackModel = () => {
    if (modelViewer) modelViewer.hidden = true;
    if (modelError) modelError.hidden = false;
    if (fallbackCanvas) {
      fallbackCanvas.hidden = false;
      window.drawBuilding(fallbackCanvas);
    }
  };
  let modelRequestId = 0;
  const loadModelStyle = async (style) => {
    if (!modelViewer) return;
    const selectedStyle = style === "exterior" ? "exterior" : "dollhouse";
    const requestId = ++modelRequestId;
    const urlToLoad = artifactUrl(selectedStyle === "dollhouse" ? "dollhouse" : "model");
    $$("[data-model-style]").forEach((button) => {
      const active = button.dataset.modelStyle === selectedStyle;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    if (modelError) modelError.hidden = true;
    if (fallbackCanvas) fallbackCanvas.hidden = true;
    modelViewer.hidden = false;
    modelViewer.alt = selectedStyle === "dollhouse" ? "Interactive 3D cutaway dollhouse concept model" : "Interactive 3D exterior concept massing model";
    try {
      const blob = await api(urlToLoad);
      if (requestId !== modelRequestId) return;
      const previousUrl = modelViewer.dataset.objectUrl;
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      const url = URL.createObjectURL(blob);
      modelViewer.dataset.objectUrl = url;
      modelViewer.addEventListener("error", showFallbackModel, { once: true });
      modelViewer.setAttribute("src", url);
    } catch (error) {
      if (requestId === modelRequestId) showFallbackModel();
    }
  };
  if (modelViewer) {
    $$("[data-model-style]").forEach((button) => button.addEventListener("click", () => loadModelStyle(button.dataset.modelStyle)));
    await loadModelStyle("dollhouse");
  } else if (fallbackCanvas) {
    fallbackCanvas.hidden = false;
    window.drawBuilding(fallbackCanvas);
  }
  const planImage = $("#plan-image");
  const planLoading = $("#plan-loading");
  const floorCount = conceptFloorCount(project.spec?.floors || project.floors || 1);
  const startingFloor = Math.min(floorCount, Math.max(1, Number(project.spec?.design_studio?.active_floor || 1)));
  const floorPlanUrls = Array.isArray(project.floor_plan_urls) ? project.floor_plan_urls : [];
  const technicalFloorPlanUrls = Array.isArray(project.technical_floor_plan_urls) ? project.technical_floor_plan_urls : [];
  let selectedPlanStyle = "technical";
  const planUrlForFloor = (floor, style) => {
    const technical = style === "technical";
    if (isPublic) {
      const urls = technical ? technicalFloorPlanUrls : floorPlanUrls;
      const baseUrl = technical ? (project.technical_plan_url || project.plan_url) : project.plan_url;
      const generatedName = technical ? `plan-technical-floor-${floor}.svg` : `plan-floor-${floor}.svg`;
      return urls[floor - 1] || (baseUrl ? baseUrl.replace(/plan(?:-technical)?\.svg$/, generatedName) : "");
    }
    return `${artifactUrl(technical ? "technical-plan" : "plan")}?floor=${encodeURIComponent(floor)}&style=${encodeURIComponent(technical ? "technical" : "presentation")}`;
  };
  let planRequestId = 0;
  const loadPlanFloor = async (floor, style = selectedPlanStyle) => {
    if (!planImage) return;
    const selectedFloor = Math.min(floorCount, Math.max(1, Number(floor) || 1));
    selectedPlanStyle = style === "presentation" ? "presentation" : "technical";
    const requestId = ++planRequestId;
    const urlToLoad = planUrlForFloor(selectedFloor, selectedPlanStyle);
    const indicator = $("#plan-floor-indicator");
    if (planLoading) {
      planLoading.hidden = false;
      planLoading.textContent = "Preparing floor plan…";
    }
    $$("[data-plan-floor]").forEach((button) => {
      const active = Number(button.dataset.planFloor) === selectedFloor;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    $$("[data-plan-style]").forEach((button) => {
      const active = button.dataset.planStyle === selectedPlanStyle;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    if (indicator && floorCount > 1) indicator.textContent = `Level ${selectedFloor} of ${floorCount}`;
    planImage.alt = `${selectedPlanStyle === "technical" ? "Technical" : "Presentation"} schematic concept floor plan, level ${selectedFloor} of ${floorCount}`;
    if (!urlToLoad) {
      if (planLoading) planLoading.textContent = "This floor plan is unavailable.";
      return;
    }
    try {
      const blob = await api(urlToLoad);
      if (requestId !== planRequestId) return;
      const previousUrl = planImage.dataset.objectUrl;
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      const objectUrl = URL.createObjectURL(blob);
      planImage.dataset.objectUrl = objectUrl;
      planImage.onload = () => { if (requestId === planRequestId && planLoading) planLoading.hidden = true; };
      planImage.onerror = () => { if (requestId === planRequestId && planLoading) planLoading.textContent = "Could not display this floor plan."; };
      planImage.src = objectUrl;
      if (planImage.complete && planImage.naturalWidth && planLoading) planLoading.hidden = true;
    } catch (error) {
      if (requestId === planRequestId && planLoading) planLoading.textContent = "Could not prepare this floor plan.";
    }
  };
  if (planImage) {
    $$("[data-plan-floor]").forEach((button) => button.addEventListener("click", () => loadPlanFloor(Number(button.dataset.planFloor))));
    $$("[data-plan-style]").forEach((button) => button.addEventListener("click", () => loadPlanFloor(Number($("[data-plan-floor].active")?.dataset.planFloor || startingFloor), button.dataset.planStyle)));
    await loadPlanFloor(startingFloor, "technical");
  }
  const scheduleContainer = $("#schedule-container");
  if (scheduleContainer) {
    try {
      const schedule = await api(artifactUrl("schedule"));
      scheduleContainer.innerHTML = timelineMarkup(schedule);
    } catch (error) {
      scheduleContainer.innerHTML = `<div class="form-error">${escapeHtml(error.message)}</div>`;
    }
  }
  renderStudioMarketDirections(project.market_directions);
  await initWorkbench(project);
}

function studioRoomRow(room, index, activeFloor) {
  const safeId = escapeHtml(room.id || `room-${index + 1}`);
  return `<div class="studio-room-row" data-row-index="${Number(index)}"><input data-field="id" value="${safeId}" maxlength="64" aria-label="Room ID"><input data-field="label" value="${escapeHtml(room.label || `Room ${index + 1}`)}" maxlength="60" aria-label="Room name"><input data-field="room_type" value="${escapeHtml(room.type || room.room_type || "room")}" maxlength="40" aria-label="Room type"><input data-field="floor" type="number" value="${Number(activeFloor)}" aria-label="Floor" readonly aria-readonly="true"><input data-field="x" type="number" min="0" max="1000" step="0.1" value="${Number(room.x || 0)}" aria-label="X position metres"><input data-field="y" type="number" min="0" max="1000" step="0.1" value="${Number(room.y || 0)}" aria-label="Y position metres"><input data-field="width" type="number" min="0.5" max="200" step="0.1" value="${Number(room.w || room.width || 3)}" aria-label="Width metres"><input data-field="depth" type="number" min="0.5" max="200" step="0.1" value="${Number(room.h || room.depth || 3)}" aria-label="Depth metres"><button type="button" class="button button-quiet studio-remove">Remove</button></div>`;
}

function seismicWaveformMarkup(trace) {
  const values = trace?.chart_acceleration_g;
  if (!Array.isArray(values) || values.length < 2) return "";
  const peak = Math.max(...values.map((value) => Math.abs(Number(value) || 0)), 0.001);
  const points = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 300;
    const y = 60 - (Number(value) / peak) * 48;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<div class="waveform"><svg viewBox="0 0 300 120" role="img" aria-label="User-provided acceleration waveform visual summary"><line x1="0" y1="60" x2="300" y2="60" stroke="#dce7df"/><polyline fill="none" stroke="#2f7956" stroke-width="2" points="${points}"/></svg><span>${Number(trace.duration_seconds || 0).toFixed(2)} s · peak ${Number(trace.peak_absolute_acceleration_g || 0).toFixed(3)} g · visual summary only</span></div>`;
}

function workbenchMarkup(data) {
  const design = data.design_studio || {};
  const qto = data.quantity_takeoff || {};
  const blocks = data.block_modules || {};
  const energy = data.energy_planning || {};
  const delivery = data.delivery_tracking || {};
  const drawing = data.drawing_review || {};
  const site = data.site_and_engineering || {};
  const bim = data.bim_interoperability || {};
  const seismic = site.seismic_trace || null;
  const capture = site.site_capture_manifest || null;
  const vector = drawing.vector_inventory || null;
  const ifc = bim.ifc_manifest || null;
  const rooms = design.rooms || [];
  const designFloors = conceptFloorCount(design.floors || 1);
  const activeDesignFloor = Math.min(designFloors, Math.max(1, Number(design.active_floor) || 1));
  const designFloorPicker = designFloors > 1 ? `<label class="form-field compact-field"><span>Edit concept level</span><select id="studio-design-floor">${Array.from({ length: designFloors }, (_, index) => { const floor = index + 1; return `<option value="${floor}" ${floor === activeDesignFloor ? "selected" : ""}>${floor === 1 ? "Ground floor" : `Level ${floor}`}</option>`; }).join("")}</select><small class="form-hint">Each level keeps its own room-block layout.</small></label>` : "";
  const qtoRows = (qto.items || []).map((item) => `<tr><td>${escapeHtml(item.item)}</td><td>${Number(item.quantity || 0).toLocaleString("en-GH")} ${escapeHtml(item.unit || "")}</td><td>${escapeHtml(item.basis || "")}</td></tr>`).join("");
  const phaseOptions = (delivery.phases || []).map((phase) => `<option value="${escapeHtml(phase.key)}">${escapeHtml(phase.phase)} · ${Number(phase.progress_percent || 0)}%</option>`).join("");
  const phaseRows = (delivery.phases || []).map((phase) => `<tr><td>${escapeHtml(phase.phase)}</td><td><span class="progress-value">${Number(phase.progress_percent || 0)}%</span></td><td>${escapeHtml(phase.status || "Not started")}</td></tr>`).join("");
  return `
    <div class="workbench-summary"><span class="meta-pill">Original Buildwise workflow</span><span class="meta-pill">${escapeHtml(data.status || "concept-review-required")}</span></div>
    <details class="studio-details" open><summary><strong>Design Studio</strong> · editable room blocks for level ${activeDesignFloor}</summary><p class="form-hint">Adjust one selected level at a time in metres, then save. Other saved levels remain intact. This remains a conceptual layout, not a construction drawing.</p><form id="design-studio-form">${designFloorPicker}<label class="form-field compact-field"><span>Concept variant name</span><input id="studio-variant-name" value="${escapeHtml(design.uses_custom_layout ? "Working concept" : "Starter concept")}" maxlength="80"></label><div class="studio-grid-head"><span>ID</span><span>Room</span><span>Type</span><span>Floor</span><span>X m</span><span>Y m</span><span>Width m</span><span>Depth m</span><span></span></div><div id="studio-room-list">${rooms.map((room, index) => studioRoomRow(room, index, design.active_floor || 1)).join("")}</div><div class="studio-actions"><button id="studio-add-room" type="button" class="button button-secondary">＋ Add room</button><button type="submit" class="button button-primary">Save concept layout</button></div></form></details>
    <details class="studio-details"><summary><strong>Transparent QTO & block modules</strong> · early-planning allowances</summary><table class="cost-table workbench-table"><thead><tr><th>Item</th><th>Quantity</th><th>Basis</th></tr></thead><tbody>${qtoRows}</tbody></table><div class="workbench-stats"><span><strong>${Number(blocks.estimated_blocks || 0).toLocaleString("en-GH")}</strong> conceptual blocks</span><span><strong>${Number(blocks.pallets_at_120_blocks || 0)}</strong> pallets at 120 blocks</span></div><div class="disclaimer-box">${escapeHtml(qto.disclaimer || "Review quantities professionally.")}</div></details>
    <details class="studio-details"><summary><strong>Energy planning</strong> · review-first prompts</summary><div class="workbench-stats"><span><strong>${Number(energy.concept_pv_capacity_range_kwp?.[0] || 0)}–${Number(energy.concept_pv_capacity_range_kwp?.[1] || 0)} kWp</strong> concept PV range</span><span>${energy.solar_requested_in_brief ? "Solar noted in the brief" : "Solar not specified in the brief"}</span></div><ul class="compliance-list">${(energy.planning_prompts || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><div class="disclaimer-box">${escapeHtml(energy.disclaimer || "Professional electrical review required.")}</div></details>
    <details class="studio-details"><summary><strong>Delivery tracker</strong> · user-entered progress</summary><div class="workbench-stats"><span><strong>${Number(delivery.overall_progress_percent || 0)}%</strong> duration-weighted progress</span><span>Not a quality, payment or completion certificate</span></div><table class="cost-table workbench-table"><thead><tr><th>Planned phase</th><th>Progress</th><th>Status</th></tr></thead><tbody>${phaseRows}</tbody></table><form id="delivery-progress-form" class="progress-form"><label class="form-field compact-field"><span>Phase</span><select id="delivery-phase">${phaseOptions}</select></label><label class="form-field compact-field"><span>Progress %</span><input id="delivery-percent" type="number" min="0" max="100" value="0"></label><label class="form-field compact-field"><span>Status</span><select id="delivery-status"><option>Not started</option><option>In progress</option><option>Blocked</option><option>Complete</option></select></label><label class="form-field compact-field"><span>Update note</span><input id="delivery-note" maxlength="800" placeholder="Optional site update"></label><button class="button button-primary" type="submit">Save progress</button></form><div class="disclaimer-box">${escapeHtml(delivery.disclaimer || "User-entered progress only.")}</div></details>
    <details class="studio-details"><summary><strong>Drawing, site, engineering & BIM review records</strong></summary><p><strong>Drawing review:</strong> ${escapeHtml(drawing.status || "No source drawing uploaded")}</p>${vector ? `<p class="form-hint">Vector inventory: ${Number(vector.total_declared_entities || 0).toLocaleString("en-GH")} declared entities · ${Number(vector.confirmed_closed_area_sqm || 0).toLocaleString("en-GH")} m² confirmed closed area.</p>` : ""}<p><strong>Seismic/site data:</strong> ${escapeHtml(site.seismic_visualization_status || "No dataset supplied")}</p>${seismicWaveformMarkup(seismic)}${capture ? `<p class="form-hint">Capture manifest: ${Number(capture.image_count || 0).toLocaleString("en-GH")} images · ${Number(capture.ground_control_points || 0)} control points · ${escapeHtml(capture.readiness || "")}</p>` : ""}<p><strong>IFC/BIM:</strong> ${escapeHtml(bim.ifc_import_status || "Not enabled")}</p>${ifc ? `<p class="form-hint">IFC manifest: ${escapeHtml(ifc.schema || "UNKNOWN")} · ${Number(ifc.total_declared_elements || 0).toLocaleString("en-GH")} declared elements.</p>` : ""}<div class="review-intake-grid"><form id="seismic-input-form" class="review-form"><strong>Seismic trace visualizer</strong><label class="form-field compact-field"><span>Sample rate · Hz</span><input id="seismic-rate" type="number" min="0.1" max="10000" step="0.1" value="100"></label><label class="form-field compact-field"><span>Acceleration samples · g, comma-separated</span><textarea id="seismic-values" maxlength="30000" placeholder="e.g. 0, 0.02, -0.03, 0.01, 0.04, -0.01, 0, 0.01"></textarea></label><label class="form-field compact-field"><span>Professional data source note</span><input id="seismic-note" maxlength="240" placeholder="Optional provenance"></label><button class="button button-secondary" type="submit">Visualize trace</button></form><form id="capture-input-form" class="review-form"><strong>Site-capture manifest</strong><label class="form-field compact-field"><span>Image count</span><input id="capture-count" type="number" min="1" max="100000" value="1"></label><label class="form-field compact-field"><span>Control points</span><input id="capture-control-points" type="number" min="0" max="10000" value="0"></label><label class="form-field compact-field"><span>Declared overlap %</span><input id="capture-overlap" type="number" min="0" max="100" value="60"></label><label class="form-field compact-field"><span>Coverage m² · optional</span><input id="capture-area" type="number" min="0.1" max="1000000" step="0.1"></label><button class="button button-secondary" type="submit">Save manifest</button></form><form id="ifc-input-form" class="review-form"><strong>IFC inventory manifest</strong><label class="form-field compact-field"><span>Filename</span><input id="ifc-filename" maxlength="160" placeholder="project.ifc"></label><label class="form-field compact-field"><span>Schema</span><select id="ifc-schema"><option>UNKNOWN</option><option>IFC2X3</option><option>IFC4</option><option>IFC4X3</option></select></label><label class="form-field compact-field"><span>Element counts JSON</span><textarea id="ifc-counts" placeholder='{"IfcWall": 20, "IfcDoor": 8}'></textarea></label><button class="button button-secondary" type="submit">Save IFC manifest</button></form><form id="vector-input-form" class="review-form"><strong>Vector inventory</strong><label class="form-field compact-field"><span>Source filename</span><input id="vector-filename" maxlength="160" placeholder="concept-plan.dxf"></label><label class="form-field compact-field"><span>Declared unit</span><select id="vector-unit"><option>unknown</option><option>m</option><option>mm</option><option>ft</option></select></label><label class="form-field compact-field"><span>Layer counts JSON</span><textarea id="vector-layers" placeholder='{"Walls": 28, "Openings": 10}'></textarea></label><label class="form-field compact-field"><span>Closed areas m², comma-separated</span><input id="vector-areas" placeholder="20.5, 14.2"></label><button class="button button-secondary" type="submit">Save vector inventory</button></form></div><div class="disclaimer-box">${escapeHtml(data.method_note || "Professional review remains required.")}</div></details>`;
}

function setStudioView(mode) {
  const allowedModes = new Set(["2d", "split", "3d"]);
  if (!allowedModes.has(mode)) return;
  const consoleElement = $("#studio-console");
  if (!consoleElement) return;
  consoleElement.dataset.studioMode = mode;
  $$("[data-action=\"studio-view\"]").forEach((button) => {
    const active = button.dataset.studioView === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  // A hidden model-viewer may need a render tick after it returns to view.
  if (mode !== "2d") $("#model-viewer")?.requestUpdate?.();
}

function renderStudioIntelligence(data) {
  const program = $("#studio-spatial-program");
  const qtoSummary = $("#studio-qto-summary");
  const design = data?.design_studio || {};
  const rooms = Array.isArray(design.rooms) ? design.rooms : [];
  if (program) {
    if (!rooms.length) {
      program.innerHTML = '<p class="studio-empty">Room blocks will appear here when the concept layout is available.</p>';
    } else {
      program.innerHTML = rooms.slice(0, 12).map((room, index) => {
        const width = Number(room.width ?? room.w ?? 0);
        const depth = Number(room.depth ?? room.h ?? 0);
        const area = width > 0 && depth > 0 ? width * depth : 0;
        const type = String(room.room_type || room.type || "room").replaceAll("_", " ");
        return `<div class="studio-program-row"><span class="studio-program-index">${String(index + 1).padStart(2, "0")}</span><span class="studio-program-copy"><strong>${escapeHtml(room.label || `Room ${index + 1}`)}</strong><small>${escapeHtml(type)} · floor ${Number(room.floor || design.active_floor || 1)}</small></span><span class="studio-program-area">${area ? `${area.toFixed(1)} m²` : "—"}</span></div>`;
      }).join("") + (rooms.length > 12 ? `<p class="studio-empty">+ ${rooms.length - 12} additional room blocks in Design Studio</p>` : "");
    }
  }
  if (qtoSummary) {
    const items = Array.isArray(data?.quantity_takeoff?.items) ? data.quantity_takeoff.items : [];
    if (!items.length) {
      qtoSummary.innerHTML = "<span>Quantity allowances are not available for this concept.</span>";
    } else {
      qtoSummary.innerHTML = `<span>${items.length} planning allowances</span><div class="studio-qto-items">${items.slice(0, 3).map((item) => `<span>${escapeHtml(item.item || "Allowance")}: <strong>${Number(item.quantity || 0).toLocaleString("en-GH")} ${escapeHtml(item.unit || "")}</strong></span>`).join("")}</div>`;
    }
  }
}

function renderStudioMarketDirections(payload) {
  const host = $("#studio-market-direction");
  if (!host) return;
  const directions = Array.isArray(payload?.directions) ? payload.directions : [];
  const selected = directions.find((direction) => direction?.selected) || directions.find((direction) => direction?.key === payload?.selected_focus);
  if (!selected) {
    host.innerHTML = '<p class="studio-empty">Concept direction prompts are unavailable for this legacy project.</p>';
    return;
  }
  const prompts = Array.isArray(selected.priority_prompts) ? selected.priority_prompts.slice(0, 2) : [];
  host.innerHTML = `<div class="studio-market-heading"><span>CONCEPT DIRECTION</span><b>${escapeHtml(selected.label || "Balanced briefing")}</b></div><p>${escapeHtml(selected.tagline || "Review-first client briefing prompts.")}</p><ul>${prompts.map((prompt) => `<li>${escapeHtml(prompt)}</li>`).join("")}</ul><small>${escapeHtml(selected.not_claimed || "Professional review is required.")}</small>`;
}

async function initWorkbench(project, selectedFloor = null) {
  const panel = $("#workbench-panel");
  const id = projectIdValue(project);
  if (!panel || !id) return;
  try {
    const isPublic = Boolean(project.is_public);
    const floorQuery = selectedFloor ? `?floor=${encodeURIComponent(selectedFloor)}` : "";
    const data = isPublic ? project.workbench : await api(`/api/projects/${id}/workbench${floorQuery}`);
    panel.innerHTML = `<div class="panel-heading"><div><h3>Design-to-delivery workbench</h3><p>${isPublic ? "Read-only temporary concept allowances. Create another concept to revise this public session." : "Editable concept geometry, transparent quantities and controlled progress records."}</p></div></div>${workbenchMarkup(data)}${isPublic ? `<div class="disclaimer-box">Guest concepts are not stored. Editing, delivery updates and review manifests require a future saved-workspace mode.</div>` : ""}`;
    renderStudioIntelligence(data);
    if (isPublic) {
      panel.querySelectorAll("form button, form input, form textarea, form select").forEach((element) => { element.disabled = true; });
      return;
    }
    const floorPicker = $("#studio-design-floor", panel);
    floorPicker?.addEventListener("change", async () => {
      const nextFloor = conceptFloorCount(floorPicker.value);
      await initWorkbench(project, nextFloor);
    });
    initDesignStudio(project, data.design_studio || {});
    initDeliveryTracker(project);
    initReviewInputs(project);
  } catch (error) {
    panel.innerHTML = `<div class="panel-heading"><div><h3>Design-to-delivery workbench</h3><p>Could not load this project workspace.</p></div></div><div class="form-error">${escapeHtml(error.message)}</div>`;
  }
}

function initDesignStudio(project, design) {
  const form = $("#design-studio-form");
  const roomList = $("#studio-room-list");
  const add = $("#studio-add-room");
  if (!form || !roomList || !add) return;
  add.addEventListener("click", () => {
    const index = roomList.querySelectorAll(".studio-room-row").length;
    roomList.insertAdjacentHTML("beforeend", studioRoomRow({ id: `room-${Date.now()}`, label: `Room ${index + 1}`, room_type: "room", floor: design.active_floor || 1, x: 0, y: 0, width: 3, depth: 3 }, index, design.active_floor || 1));
  });
  roomList.addEventListener("click", (event) => {
    const remove = event.target.closest(".studio-remove");
    if (remove && roomList.querySelectorAll(".studio-room-row").length > 1) remove.closest(".studio-room-row").remove();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const rooms = [...roomList.querySelectorAll(".studio-room-row")].map((row) => {
      const get = (field) => row.querySelector(`[data-field="${field}"]`).value;
      return { id: get("id").trim(), label: get("label").trim(), room_type: get("room_type").trim(), floor: Number(get("floor")), x: Number(get("x")), y: Number(get("y")), width: Number(get("width")), depth: Number(get("depth")) };
    });
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const result = await api(`/api/projects/${Number(project.id)}/design-studio`, { method: "PUT", body: { active_floor: Number(design.active_floor || 1), variant_name: $("#studio-variant-name").value.trim() || "Working concept", rooms } });
      project.spec = result.spec;
      if (state.currentProject && Number(state.currentProject.id) === Number(project.id)) state.currentProject.spec = result.spec;
      showToast("Concept layout saved. The SVG plan has been regenerated.");
      await initProjectArtifacts(project);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });
}

function initDeliveryTracker(project) {
  const form = $("#delivery-progress-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      await api(`/api/projects/${Number(project.id)}/delivery/progress`, { method: "PUT", body: { phase_key: $("#delivery-phase").value, progress_percent: Number($("#delivery-percent").value), status: $("#delivery-status").value, note: $("#delivery-note").value.trim() } });
      showToast("Delivery progress saved as a project update.");
      await initWorkbench(project);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });
}

function initReviewInputs(project) {
  const id = Number(project.id);
  const submitReview = async (form, path, body) => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    try {
      await api(`/api/projects/${id}${path}`, { method: "PUT", body });
      showToast("Project review record saved.");
      await initWorkbench(project);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      button.disabled = false;
    }
  };
  const seismic = $("#seismic-input-form");
  seismic?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = $("#seismic-values").value.split(",").map((value) => Number(value.trim())).filter((value) => !Number.isNaN(value));
    await submitReview(seismic, "/site-review/seismic-trace", { sample_rate_hz: Number($("#seismic-rate").value), acceleration_g: values, source_note: $("#seismic-note").value.trim() });
  });
  const capture = $("#capture-input-form");
  capture?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const area = $("#capture-area").value.trim();
    await submitReview(capture, "/site-review/capture-manifest", { image_count: Number($("#capture-count").value), ground_control_points: Number($("#capture-control-points").value), overlap_percent: Number($("#capture-overlap").value), coverage_area_sqm: area ? Number(area) : null, capture_note: "" });
  });
  const parseObject = (value, label) => {
    const parsed = JSON.parse(value);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label} must be a JSON object.`);
    return parsed;
  };
  const ifc = $("#ifc-input-form");
  ifc?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await submitReview(ifc, "/bim/ifc-manifest", { schema: $("#ifc-schema").value, filename: $("#ifc-filename").value.trim(), element_counts: parseObject($("#ifc-counts").value, "Element counts"), author_note: "" });
    } catch (error) { showToast(error.message, "error"); }
  });
  const vector = $("#vector-input-form");
  vector?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const areas = $("#vector-areas").value.trim() ? $("#vector-areas").value.split(",").map((value) => Number(value.trim())) : [];
      await submitReview(vector, "/drawing-review/vector-inventory", { filename: $("#vector-filename").value.trim(), unit: $("#vector-unit").value, layer_counts: parseObject($("#vector-layers").value, "Layer counts"), closed_area_sqm: areas, source_note: "" });
    } catch (error) { showToast(error.message, "error"); }
  });
}

function timelineMarkup(schedule) {
  const rows = (schedule.phases || []).map((phase, index) => {
    const width = Math.max(2, Number(schedule.gantt_data?.[index]?.width || 0));
    const offset = Math.max(0, Number(schedule.gantt_data?.[index]?.left || 0));
    return `<div class="timeline-item"><span class="timeline-name" title="${escapeHtml(phase.phase)}">${escapeHtml(phase.phase)}</span><div class="timeline-track"><span class="timeline-bar ${phase.critical ? "critical" : ""}" style="left:${Math.min(offset, 98)}%;width:${Math.min(width, 100 - Math.min(offset, 98))}%"></span></div><span class="timeline-date">${Number(phase.duration_days)} days</span></div>`;
  }).join("");
  return `<div class="timeline">${rows}</div><div class="schedule-foot"><span><strong>${Number(schedule.total_duration_days || 0)} days</strong> indicative duration</span><span>${shortDate(schedule.start_date)} → ${shortDate(schedule.estimated_completion)}</span></div><div class="form-hint">${escapeHtml(schedule.planning_note || "Dates are indicative and depend on site, approvals, procurement and delivery capacity.")}</div>`;
}

function contractorsMarkup() {
  const locations = ["Accra", "Kumasi", "Tema", "Tamale", "Cape Coast", "Takoradi", "Ho", "Koforidua", "Obuasi", "Bolgatanga", "Aflao"];
  return `<div class="page-intro"><div><div class="page-kicker">LOCAL DIRECTORY</div><h2>Find a contractor match.</h2><p>Search the directory by location, project budget and building type. Listings must be supplied and verified by your team before use.</p></div></div><div class="contractor-layout"><section class="panel"><div class="panel-heading"><div><h3>Search criteria</h3><p>Use the full project budget in GHS.</p></div></div><form id="contractor-form" class="contractor-form"><label class="form-field"><span>Location</span><select id="contractor-location">${locations.map((location) => `<option value="${escapeHtml(location)}" ${location === "Kumasi" ? "selected" : ""}>${escapeHtml(location)}</option>`).join("")}</select></label><label class="form-field"><span>Budget · GHS</span><input id="contractor-budget" type="number" min="1" step="1000" required placeholder="e.g. 750000"></label><label class="form-field"><span>Building type</span><select id="contractor-type"><option value="residential">Residential</option><option value="commercial">Commercial</option><option value="institutional">Institutional</option></select></label><button class="button button-primary button-full" type="submit">Search directory <span>→</span></button></form><div class="directory-warning">Contractor profiles and contact details are not independently verified by this demo. Verify licences, insurance, references and scope directly before engaging anyone.</div></section><section class="panel"><div class="panel-heading"><div><h3>Matching contractors</h3><p id="contractor-count">Results appear here after a search.</p></div></div><div id="contractor-results">${emptyMarkup("Search the directory", "Enter your project budget and criteria to see matching listings.", "", "")}</div></section></div>`;
}

function initContractorForm() {
  const form = $("#contractor-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultsNode = $("#contractor-results");
    const countNode = $("#contractor-count");
    resultsNode.innerHTML = '<div class="loading-block"><span class="spinner"></span><span>Checking the directory…</span></div>';
    countNode.textContent = "Searching…";
    try {
      const result = await api("/api/contractors/match", {
        method: "POST",
        body: {
          location: $("#contractor-location").value,
          budget: Number($("#contractor-budget").value),
          building_type: $("#contractor-type").value,
        },
      });
      countNode.textContent = `${Number(result.count || 0)} matching listing${Number(result.count || 0) === 1 ? "" : "s"}`;
      if (!result.contractors?.length) {
        resultsNode.innerHTML = emptyMarkup("No listings match yet", "The contractor directory is empty until you add vetted profiles in data/contractors_gh.json. We do not fabricate contractor contacts.", "", "");
      } else {
        resultsNode.innerHTML = `<div class="contractor-results">${result.contractors.map(contractorCard).join("")}<div class="form-hint">${escapeHtml(result.directory_note || "Verify all profile details independently.")}</div></div>`;
      }
    } catch (error) {
      countNode.textContent = "Search could not be completed";
      resultsNode.innerHTML = `<div class="form-error">${escapeHtml(error.message)}</div>`;
    }
  });
}

function contractorCard(contractor) {
  const specialties = (contractor.specialties || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  const locations = (contractor.locations || []).map((item) => escapeHtml(item)).join(", ");
  return `<article class="contractor-card"><div class="contractor-card-head"><div><h3>${escapeHtml(contractor.name || "Contractor listing")}</h3><p>${locations}</p></div><span class="contractor-rating">★ ${Number(contractor.rating || 0).toFixed(1)}</span></div><div class="contractor-chips">${specialties}<span>${Number(contractor.years_experience || 0)} years</span><span>${contractor.is_verified ? "Verified by directory admin" : "Unverified listing"}</span></div><div class="contractor-contact">${escapeHtml(contractor.contact_phone || "No contact details on file")} · ${escapeHtml(contractor.contact_email || "")}</div></article>`;
}

async function downloadModel(projectId) {
  try {
    const blob = await api(`/api/projects/${Number(projectId)}/artifacts/model.glb`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `buildwise-concept-${Number(projectId)}.glb`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function downloadPlan(projectId) {
  try {
    const blob = await api(`/api/projects/${Number(projectId)}/artifacts/plan.svg`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `buildwise-concept-plan-${Number(projectId)}.svg`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function downloadHandoff(projectId) {
  try {
    const blob = await api(`/api/projects/${Number(projectId)}/artifacts/handoff.json`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `buildwise-professional-handoff-${Number(projectId)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function printHandoff(projectId) {
  const printWindow = window.open("", "_blank", "noopener");
  try {
    const blob = await api(`/api/projects/${Number(projectId)}/artifacts/handoff.html`);
    const url = URL.createObjectURL(blob);
    if (!printWindow) {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      link.click();
    } else {
      printWindow.location.href = url;
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) {
    printWindow?.close();
    showToast(error.message, "error");
  }
}

async function downloadCost(projectId) {
  try {
    const blob = await api(`/api/projects/${Number(projectId)}/artifacts/cost.csv`);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `buildwise-estimate-${Number(projectId)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function deleteProject(projectId) {
  const id = Number(projectId);
  if (!window.confirm("Delete this project and its saved concept data? This cannot be undone.")) return;
  try {
    await api(`/api/projects/${id}`, { method: "DELETE" });
    state.projects = state.projects.filter((project) => Number(project.id) !== id);
    state.currentProject = null;
    updateNavCount();
    setView("projects");
    showToast("Project deleted.");
  } catch (error) {
    showToast(error.message, "error");
  }
}

$("#mobile-menu-toggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));

document.addEventListener("click", async (event) => {
  const viewButton = event.target.closest("[data-view]");
  if (viewButton) {
    event.preventDefault();
    setView(viewButton.dataset.view);
    return;
  }
  const actionButton = event.target.closest("[data-action]");
  if (!actionButton) return;
  const action = actionButton.dataset.action;
  if (action === "project-open") await openProject(actionButton.dataset.projectId);
  else if (action === "back-projects") setView("projects");
  else if (action === "download-model") await downloadModel(actionButton.dataset.projectId);
  else if (action === "download-cost") await downloadCost(actionButton.dataset.projectId);
  else if (action === "print-handoff") await printHandoff(actionButton.dataset.projectId);
  else if (action === "download-handoff") await downloadHandoff(actionButton.dataset.projectId);
  else if (action === "delete-project") await deleteProject(actionButton.dataset.projectId);
  else if (action === "studio-view") setStudioView(actionButton.dataset.studioView);
  else if (action === "download-plan") {
    event.preventDefault();
    await downloadPlan(actionButton.dataset.projectId);
  }
});

window.addEventListener("resize", () => {
  const canvas = $("#model-canvas");
  if (canvas && !canvas.hidden) window.drawBuilding(canvas);
});

boot();
