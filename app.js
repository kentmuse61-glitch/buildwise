"use strict";

const state = {
  token: sessionStorage.getItem("buildwise_token"),
  user: null,
  projects: [],
  view: "overview",
  authMode: "login",
  currentProject: null,
};

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function money(value) {
  const amount = Number(value || 0);
  return `GHS ${Math.round(amount).toLocaleString("en-GH")}`;
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
  if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
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
    if (response.status === 401 && state.token) {
      clearSession();
      showAuth("login");
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  if (contentType.includes("application/json")) return response.json();
  return response.blob();
}

function clearSession() {
  state.token = null;
  state.user = null;
  state.projects = [];
  sessionStorage.removeItem("buildwise_token");
}

function showAuth(mode = "login") {
  state.authMode = mode;
  $("#workspace").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
  const registering = mode === "register";
  $("#auth-heading").textContent = registering ? "Create your account" : "Welcome back";
  $("#auth-subheading").textContent = registering
    ? "Set up a private workspace for your project concepts."
    : "Sign in to see your projects and continue planning.";
  $("#auth-eyebrow").textContent = registering ? "START YOUR WORKSPACE" : "YOUR PROJECT WORKSPACE";
  $("#auth-submit").innerHTML = registering ? 'Create account <span aria-hidden="true">→</span>' : 'Sign in <span aria-hidden="true">→</span>';
  $("#auth-switch-label").textContent = registering ? "Already have an account?" : "New to Buildwise?";
  $("#auth-switch").textContent = registering ? "Sign in" : "Create an account";
  $("#email-field-wrap").hidden = !registering;
  $("#company-field-wrap").hidden = !registering;
  $("#auth-email").required = registering;
  $("#auth-password").autocomplete = registering ? "new-password" : "current-password";
  $("#auth-error").hidden = true;
  $("#auth-error").textContent = "";
}

function showWorkspace() {
  $("#auth-screen").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
  const username = state.user?.username || "Your account";
  $("#user-label").textContent = username;
  $("#user-avatar").textContent = username.slice(0, 1).toUpperCase();
  updateNavCount();
  setView("overview");
}

async function boot() {
  if (!state.token) {
    showAuth("login");
    return;
  }
  try {
    state.user = await api("/api/auth/me");
    const result = await api("/api/projects");
    state.projects = result.projects || [];
    showWorkspace();
  } catch (error) {
    clearSession();
    showAuth("login");
  }
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
    projects: ["YOUR WORKSPACE", "My projects"],
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
      <button class="card-open" type="button" data-action="project-open" data-project-id="${Number(project.id)}" aria-label="Open ${escapeHtml(project.name)}"></button>
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
      <article class="stat-card"><div class="stat-head"><span>Saved concepts</span><span class="stat-icon">▤</span></div><div class="stat-value">${projects.length}</div><div class="stat-foot">Private to your workspace</div></article>
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
  return `<button class="project-row" type="button" data-action="project-open" data-project-id="${Number(project.id)}"><span class="project-thumb" aria-hidden="true">⌂</span><span class="project-row-copy"><strong>${escapeHtml(project.name || "Untitled concept")}</strong><span>${escapeHtml(project.location || "Ghana")} · ${Number(project.floors || 1)} floor${Number(project.floors || 1) === 1 ? "" : "s"} · ${Number(project.area_sqm || 0)} m²</span></span><span class="project-row-cost"><strong>${money(project.estimated_cost_ghs)}</strong><span>${shortDate(project.created_at)}</span></span></button>`;
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
          <label class="form-field"><span>What are you planning?</span><textarea id="project-description" required minlength="10" maxlength="4000" placeholder="Example: A 3-bedroom, 2-bathroom bungalow in Kumasi, about 150 sqm total floor area, cement blocks, metal roof, with a porch and solar power."></textarea><small class="form-hint">Tip: State the total floor area (all floors combined) in m² if you know it. This tool creates a concept, not permit-ready drawings.</small></label>
          <div class="input-grid">
            <label class="form-field"><span>Project location</span><select id="project-location">${locations.map((location, index) => `<option value="${index === 0 ? "auto" : escapeHtml(location)}" ${index === 0 ? "selected" : ""}>${escapeHtml(location)}</option>`).join("")}</select><small class="form-hint">Choose a city or use the location mentioned in your brief.</small></label>
            <label class="form-field"><span>Budget ceiling <small>Optional · GHS</small></span><input id="project-budget" type="number" min="1" step="1000" placeholder="e.g. 500000"><small class="form-hint">Used only to compare the estimate with your target.</small></label>
          </div>
          <div class="form-actions"><span>Usually takes a few seconds. No external AI model is required.</span><button id="generate-button" class="button button-primary" type="submit">Generate concept <span>→</span></button></div>
        </form>
      </section>
      <aside class="tip-panel"><div class="page-kicker">GET A BETTER RESULT</div><h3>Brief checklist</h3><p>Use plain English and call out anything that should shape the first concept.</p><div class="example-prompt"><strong>Example brief</strong>“A 2-storey family house in Kumasi, 4 bedrooms, 3 bathrooms, 220 m² total floor area, block walls, metal roof, a balcony and solar power.”</div><div class="safety-list"><span><i>✓</i> Building type and number of floors</span><span><i>✓</i> Bedrooms, bathrooms and total area</span><span><i>✓</i> Location, materials and special features</span><span><i>!</i> Estimates use starter rates; verify current prices</span><span><i>!</i> Plans and code checks need a professional review</span></div></aside>
    </div>
    <div id="generated-output" class="generated-wrap"></div>`;
}

function initCreateForm() {
  const form = $("#create-form");
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const description = $("#project-description").value.trim();
    const location = $("#project-location").value;
    const budgetValue = $("#project-budget").value.trim();
    const output = $("#generated-output");
    const button = $("#generate-button");
    button.disabled = true;
    output.innerHTML = '<div class="loading-block"><span class="spinner"></span><span>Turning your brief into a first-pass project concept…</span></div>';
    try {
      const payload = { description, location: location === "auto" ? null : location };
      if (budgetValue) payload.budget = Number(budgetValue);
      const result = await api("/api/project/generate", { method: "POST", body: payload });
      state.projects = [result, ...state.projects.filter((project) => Number(project.id) !== Number(result.id))];
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
  return `<div class="page-intro"><div><div class="page-kicker">YOUR SAVED WORK</div><h2>My projects</h2><p>Concepts are saved to your account. Open one to view its schematic plan, estimate, timeline and downloadable 3D massing model.</p></div><button class="button button-primary" type="button" data-view="create">＋ New concept</button></div>${projects.length ? `<div class="project-grid">${projects.map(projectCard).join("")}</div>` : emptyMarkup("Your project list is empty", "Create a project brief to save your first concept.", "Create a concept", "create")}`;
}

function projectDetailMarkup(project, embedded = false) {
  const spec = project.spec || {};
  const cost = project.cost || {};
  const compliance = project.compliance || {};
  const id = Number(project.id || project.project_id || project.db_id);
  const warningItems = [
    ...(compliance.issues || []).map((item) => ({ item, pass: false })),
    ...(compliance.warnings || []).slice(0, 6).map((item) => ({ item, pass: false })),
    ...(compliance.passes || []).slice(0, 2).map((item) => ({ item, pass: true })),
  ];
  const materials = cost.materials || [];
  return `
    ${embedded ? `<div class="panel-heading" style="margin-bottom:14px"><div><div class="page-kicker">GENERATED CONCEPT</div><h3>${escapeHtml(project.name || `${spec.building_type || "Building"} · ${spec.location || "Ghana"}`)}</h3><p>Generated ${shortDate(project.created_at)} · Concept-stage outputs are approximate.</p></div><span class="status-badge">${escapeHtml(compliance.status || project.compliance_status || "Review required")}</span></div>` : `<div class="detail-toolbar"><div class="detail-toolbar-left"><button class="back-button" type="button" data-action="back-projects">← Projects</button><h2 class="detail-title">${escapeHtml(project.name || "Project concept")}</h2></div><div class="detail-actions"><button class="button button-secondary" type="button" data-action="download-model" data-project-id="${id}">↓ Download 3D</button></div></div>`}
    <section class="detail-summary"><div class="detail-summary-main"><span class="status-badge ${projectStatusClass(compliance.status || project.compliance_status)}">${escapeHtml(compliance.status || project.compliance_status || "Review required")}</span><p>${escapeHtml(project.description || spec.raw_text || "No description")}</p><div class="detail-metrics"><span class="detail-metric"><strong>${escapeHtml(spec.building_type || project.building_type || "Residential")}</strong></span><span class="detail-metric"><strong>${Number(spec.floors || project.floors || 1)}</strong> floor${Number(spec.floors || project.floors || 1) === 1 ? "" : "s"}</span><span class="detail-metric"><strong>${Number(spec.area_sqm || project.area_sqm || 0).toLocaleString("en-GH")} m²</strong> total area</span><span class="detail-metric"><strong>${Number(spec.bedrooms || 0)}</strong> bed · <strong>${Number(spec.bathrooms || 0)}</strong> bath</span><span class="detail-metric">${escapeHtml(spec.location || project.location || "Ghana")}</span></div></div><div class="detail-cost"><span>Indicative estimate</span><strong>${money(cost.total_ghs ?? project.estimated_cost_ghs)}</strong><small>GHS · concept estimate</small></div></section>
    <div class="detail-grid">
      <div class="detail-column">
        <section class="panel"><div class="panel-heading"><div><h3>3D building massing</h3><p>Drag to rotate the schematic. Download a GLB model for a compatible 3D viewer.</p></div></div><div class="model-stage"><canvas id="model-canvas" data-floors="${Number(spec.floors || project.floors || 1)}" data-area="${Number(spec.area_sqm || project.area_sqm || 100)}" aria-label="Interactive schematic 3D building massing"></canvas></div><div class="model-caption"><span>Concept massing only · no structural detail</span><button class="panel-link" type="button" data-action="download-model" data-project-id="${id}">Download GLB →</button></div></section>
        <section class="panel"><div class="panel-heading"><div><h3>Schematic floor plan</h3><p>Ground-floor room blocks · approximate footprint.</p></div><a class="panel-link" href="#" data-action="download-plan" data-project-id="${id}">Download SVG →</a></div><div class="plan-stage"><img id="plan-image" alt="Schematic concept floor plan" src="" /><span class="artifact-loading" id="plan-loading">Preparing plan…</span></div></section>
        <section class="panel"><div class="panel-heading"><div><h3>First-pass project schedule</h3><p>Sequential planning timeline with an indicative seasonal allowance.</p></div><span class="meta-pill">${Number(spec.floors || project.floors || 1)} floor${Number(spec.floors || project.floors || 1) === 1 ? "" : "s"}</span></div><div id="schedule-container"><div class="artifact-loading">Preparing schedule…</div></div></section>
      </div>
      <div class="detail-column secondary">
        <section class="panel"><div class="panel-heading"><div><h3>Cost overview</h3><p>Budget allocation by project category.</p></div></div><div class="cost-hero"><div><span>Indicative total</span><strong>${money(cost.total_ghs ?? project.estimated_cost_ghs)}</strong></div><div class="cost-range"><span>Planning range ±15%</span><strong>${money(cost.indicative_range_low_ghs)} – ${money(cost.indicative_range_high_ghs)}</strong></div></div><table class="cost-table"><tbody><tr><td>Materials allocation</td><td>${money(cost.total_materials_ghs)}</td></tr><tr><td>Labour allowance</td><td>${money(cost.labour_cost_ghs)}</td></tr><tr><td>Professional fees allowance</td><td>${money(cost.professional_fees_ghs)}</td></tr><tr><td>Contingency allowance</td><td>${money(cost.contingency_ghs)}</td></tr></tbody></table>${cost.budget_constraint_ghs ? `<div class="disclaimer-box">Budget target: <strong>${money(cost.budget_constraint_ghs)}</strong> · ${cost.within_budget ? "Indicative estimate is within target." : "Indicative estimate exceeds target."}</div>` : ""}<div class="disclaimer-box">${escapeHtml(cost.disclaimer || "Illustrative estimate only; obtain current local prices and a quantity-surveyor estimate.")}</div><table class="cost-table"><tbody>${materials.map((item) => `<tr><td>${escapeHtml(item.name)}</td><td>${money(item.estimated_amount_ghs)}</td></tr>`).join("")}</tbody></table></section>
        <section class="panel"><div class="panel-heading"><div><h3>Preliminary review</h3><p>Automated screening only — not a code approval.</p></div></div><div class="compliance-status"><span class="status-badge ${projectStatusClass(compliance.status || project.compliance_status)}">${escapeHtml(compliance.status || project.compliance_status || "Review required")}</span></div><ul class="compliance-list">${warningItems.map((entry) => `<li class="${entry.pass ? "pass" : ""}">${escapeHtml(entry.item)}</li>`).join("") || `<li>${escapeHtml(compliance.disclaimer || "Have the design reviewed by licensed local professionals and the relevant authority.")}</li>`}</ul><div class="disclaimer-box">${escapeHtml(compliance.disclaimer || "For early planning only. Confirm all code, permit, structural and site requirements locally.")}</div></section>
        <section class="panel"><div class="panel-heading"><div><h3>Assumptions</h3><p>Values extracted from your brief.</p></div></div><table class="cost-table"><tbody><tr><td>Material concept</td><td>${escapeHtml(String(spec.material || "—").replaceAll("_", " "))}</td></tr><tr><td>Roof concept</td><td>${escapeHtml(String(spec.roof_type || "—").replaceAll("_", " "))}</td></tr><tr><td>Foundation concept</td><td>${escapeHtml(String(spec.foundation_type || "—").replaceAll("_", " "))}</td></tr><tr><td>Special features</td><td>${escapeHtml((spec.special_features || []).join(", ") || "None specified")}</td></tr></tbody></table><div class="disclaimer-box">${escapeHtml(cost.rate_note || "The included starter cost rates are not independently verified.")}</div></section>
      </div>
    </div>`;
}

async function openProject(projectId) {
  try {
    const project = await api(`/api/projects/${Number(projectId)}`);
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
  const id = Number(project.id || project.project_id || project.db_id);
  const canvas = $("#model-canvas");
  if (canvas) window.drawBuilding(canvas);
  const planImage = $("#plan-image");
  const planLoading = $("#plan-loading");
  if (planImage) {
    try {
      const blob = await api(`/api/projects/${id}/artifacts/plan.svg`);
      const url = URL.createObjectURL(blob);
      planImage.onload = () => { if (planLoading) planLoading.hidden = true; };
      planImage.onerror = () => { if (planLoading) planLoading.textContent = "Could not display the plan."; };
      planImage.src = url;
      if (planImage.complete && planImage.naturalWidth && planLoading) planLoading.hidden = true;
    } catch (error) {
      if (planLoading) planLoading.textContent = "Could not prepare the plan.";
    }
  }
  const scheduleContainer = $("#schedule-container");
  if (scheduleContainer) {
    try {
      const schedule = await api(`/api/projects/${id}/artifacts/schedule.json`);
      scheduleContainer.innerHTML = timelineMarkup(schedule);
    } catch (error) {
      scheduleContainer.innerHTML = `<div class="form-error">${escapeHtml(error.message)}</div>`;
    }
  }
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

$("#auth-switch").addEventListener("click", () => showAuth(state.authMode === "login" ? "register" : "login"));
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#auth-submit");
  const errorNode = $("#auth-error");
  const username = $("#auth-username").value.trim();
  const password = $("#auth-password").value;
  button.disabled = true;
  errorNode.hidden = true;
  try {
    if (state.authMode === "register") {
      await api("/api/auth/register", {
        method: "POST",
        body: {
          username,
          password,
          email: $("#auth-email").value.trim(),
          company_name: $("#auth-company").value.trim(),
          phone: "",
        },
      });
    }
    const loginResult = await api("/api/auth/login", { method: "POST", body: { username, password } });
    state.token = loginResult.access_token;
    sessionStorage.setItem("buildwise_token", state.token);
    state.user = await api("/api/auth/me");
    const result = await api("/api/projects");
    state.projects = result.projects || [];
    showWorkspace();
    showToast(state.authMode === "register" ? "Account ready. Welcome to Buildwise GH." : "Welcome back.");
  } catch (error) {
    errorNode.textContent = error.message;
    errorNode.hidden = false;
  } finally {
    button.disabled = false;
  }
});

$("#logout-btn").addEventListener("click", () => {
  clearSession();
  showAuth("login");
});

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
  else if (action === "download-plan") {
    event.preventDefault();
    await downloadPlan(actionButton.dataset.projectId);
  }
});

window.addEventListener("resize", () => {
  const canvas = $("#model-canvas");
  if (canvas) window.drawBuilding(canvas);
});

boot();
