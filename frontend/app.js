"use strict";

/* ============================================================
   CONFIG
============================================================ */
const API = "http://127.0.0.1:8000";
let currentView = "dashboard";
let allLeads = [];
let refreshTimer = null;

/* ============================================================
   DOM HELPERS
============================================================ */
const $ = (id) => document.getElementById(id);

function escapeHTML(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatMoney(value) {
    const number = Number(value || 0);
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 0,
    }).format(number);
}

function formatNumber(value) {
    return new Intl.NumberFormat("en-US").format(Number(value || 0));
}

function formatStatus(status) {
    if (!status) return "-";
    return String(status)
        .replaceAll("_", " ")
        .toUpperCase();
}

function classificationFromScore(score) {
    const value = Number(score || 0);
    if (value >= 70) return "HOT";
    if (value >= 40) return "WARM";
    return "COLD";
}

function badge(text, type = "") {
    const safe = escapeHTML(text);
    return `<span class="badge ${type ? `badge-${type.toLowerCase()}` : ""}">${safe}</span>`;
}

function statusBadge(status) {
    const value = String(status || "NEW").toUpperCase();
    let className = "badge-cold";
    if (value === "HOT") className = "badge-hot";
    else if (value === "WARM") className = "badge-warm";
    else if (["CONTACTED", "REPLIED", "QUALIFIED"].includes(value)) className = "badge-contacted";
    return `<span class="badge ${className}">${escapeHTML(value)}</span>`;
}

/* ============================================================
   TOAST
============================================================ */
function showToast(message, type = "success") {
    const container = $("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

/* ============================================================
   API
============================================================ */
async function api(endpoint, options = {}) {
    try {
        const response = await fetch(`${API}${endpoint}`, {
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {}),
            },
            ...options,
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || data.message || "API Error");
        }
        return data;
    } catch (error) {
        console.error(`API Error [${endpoint}]`, error);
        throw error;
    }
}

/* ============================================================
   NAVIGATION
============================================================ */
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".nav-item").forEach((button) => {
        button.addEventListener("click", () => {
            const view = button.dataset.view;
            showView(view);
        });
    });
    checkAPI();
    loadDashboard();
    startAutoRefresh();
});

function showView(view) {
    currentView = view;

    document.querySelectorAll(".view").forEach((section) => {
        section.classList.remove("active");
    });
    const target = document.getElementById(`${view}-view`);
    if (target) target.classList.add("active");

    document.querySelectorAll(".nav-item").forEach((button) => {
        button.classList.remove("active");
    });
    const activeButton = document.querySelector(`.nav-item[data-view="${view}"]`);
    if (activeButton) activeButton.classList.add("active");

    const titles = {
        dashboard: "Dashboard",
        leads: "Leads",
        pipeline: "Pipeline",
        priorities: "Priorities",
        followups: "Follow-ups",
    };
    const titleEl = document.getElementById("page-title");
    if (titleEl) titleEl.textContent = titles[view] || "Dashboard";

    loadView(view);
}

async function loadView(view) {
    switch (view) {
        case "dashboard":
            await loadDashboard();
            break;
        case "leads":
            await loadLeads();
            break;
        case "pipeline":
            await loadPipeline();
            break;
        case "priorities":
            await loadPriorities();
            break;
        case "followups":
            await loadFollowUps();
            break;
    }
}

/* ============================================================
   API HEALTH
============================================================ */
async function checkAPI() {
    try {
        await api("/health");
        document.querySelectorAll(".status-dot").forEach((dot) => dot.classList.remove("offline"));
    } catch (error) {
        document.querySelectorAll(".status-dot").forEach((dot) => dot.classList.add("offline"));
        console.error("API Offline", error);
    }
}

/* ============================================================
   DASHBOARD
============================================================ */
async function loadDashboard() {
    try {
        const data = await api("/dashboard");
        const stats = data.dashboard || data.stats || data || {};
        updateStats(stats);
        await Promise.all([loadPipelineSummary(), loadPriorityPreview()]);
    } catch (error) {
        console.error(error);
        showToast("Dashboard: " + error.message, "error");
    }
}

function updateStats(stats) {
    setText("total-leads", stats.total_leads ?? stats.total ?? 0);
    setText("hot-leads", stats.hot_leads ?? stats.hot ?? 0);
    setText("warm-leads", stats.warm_leads ?? stats.warm ?? 0);
    setText("potential-revenue", formatMoney(stats.potential_revenue ?? stats.potential ?? 0));
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

/* ============================================================
   PIPELINE SUMMARY (DASHBOARD)
============================================================ */
async function loadPipelineSummary() {
    const container = document.getElementById("pipeline-summary");
    if (!container) return;
    try {
        const data = await api("/pipeline");
        const pipeline = data.pipeline || {};

        const entries = Object.entries(pipeline);
        if (!entries.length) {
            container.innerHTML = "<p>No pipeline data.</p>";
            return;
        }

        const getCount = (value) => {
            if (Array.isArray(value)) return value.length;
            if (typeof value === "number") return value;
            if (value && typeof value.count === "number") return value.count;
            return 0;
        };

        const total = entries.reduce((sum, [, value]) => sum + getCount(value), 0);

        container.innerHTML = entries
            .map(([status, value]) => {
                const count = getCount(value);
                const percentage = total > 0 ? Math.round((count / total) * 100) : 0;
                return `
                    <div class="pipeline-row">
                        <span>${escapeHTML(formatStatus(status))}</span>
                        <div class="pipeline-bar">
                            <div class="pipeline-fill" style="width:${percentage}%"></div>
                        </div>
                        <strong>${count}</strong>
                    </div>
                `;
            })
            .join("");
    } catch (error) {
        container.innerHTML = "<p style='color:#8994a6'>Pipeline unavailable.</p>";
    }
}

/* ============================================================
   PRIORITY PREVIEW (DASHBOARD)
============================================================ */
async function loadPriorityPreview() {
    const container = document.getElementById("priority-list");
    if (!container) return;
    try {
        const data = await api("/leads/priorities");
        const priorities = data.priorities || [];
        if (!priorities.length) {
            container.innerHTML = "<p style='padding:20px;color:#8994a6'>No priorities.</p>";
            return;
        }
        container.innerHTML = priorities
            .filter((item) => item.priority === "URGENT")
            .slice(0, 5)
            .map((item) => `
                <div class="priority-item">
                    <div>
                        <div class="priority-name">${escapeHTML(item.name)}</div>
                        <div class="priority-company">${escapeHTML(item.company || "")}</div>
                    </div>
                    <div class="priority-score">${item.score}</div>
                </div>
            `)
            .join("");
    } catch (error) {
        container.innerHTML = "<p style='padding:20px;color:#8994a6'>Unable to load priorities.</p>";
    }
}

/* ============================================================
   LEADS
============================================================ */
async function loadLeads() {
    const table = document.getElementById("leads-table");
    if (!table) return;
    table.innerHTML = `<tr><td colspan="7">Loading...</td></tr>`;

    try {
        const status = document.getElementById("status-filter")?.value || "";
        const classification = document.getElementById("classification-filter")?.value || "";
        const params = new URLSearchParams();
        if (status) params.set("status", status);
        if (classification) params.set("classification", classification);
        const query = params.toString() ? `?${params.toString()}` : "";

        const data = await api(`/leads${query}`);
        allLeads = data.leads || [];
        renderLeads(allLeads);
    } catch (error) {
        table.innerHTML = `<tr><td colspan="7">Error: ${escapeHTML(error.message)}</td></tr>`;
    }
}

function renderLeads(leads) {
    const table = document.getElementById("leads-table");
    if (!table) return;
    const countEl = document.getElementById("leads-count");
    if (countEl) countEl.textContent = `(${leads.length} total)`;

    if (!leads.length) {
        table.innerHTML = `<tr><td colspan="7">No leads found.</td></tr>`;
        return;
    }

    table.innerHTML = leads
        .map((lead) => `
            <tr>
                <td>
                    <div class="lead-name">${escapeHTML(lead.name || "No name")}</div>
                    <div class="lead-email">${escapeHTML(lead.email || "")}</div>
                </td>
                <td>${escapeHTML(lead.company || "-")}</td>
                <td><strong>${lead.score ?? 0}</strong></td>
                <td>${statusBadge(lead.status)}</td>
                <td>${formatMoney(lead.budget ?? 0)}</td>
                <td>${escapeHTML(lead.urgency || "normal")}</td>
                <td>
                    <button class="text-btn" onclick="openLeadDetails(${lead.id})">View</button>
                    <button onclick="deleteLead(${lead.id})" style="color:#ff5f6d;border:none;background:none;cursor:pointer;margin-left:8px;font-size:14px;" title="Delete">✕</button>
                </td>
            </tr>
        `)
        .join("");
}

/* ============================================================
   SEARCH LEADS
============================================================ */
let searchTimeout = null;
async function searchLeads() {
    const input = document.getElementById("search-input");
    if (!input) return;
    const query = input.value.trim();
    clearTimeout(searchTimeout);

    searchTimeout = setTimeout(async () => {
        if (!query) {
            renderLeads(allLeads);
            return;
        }
        try {
            const data = await api(`/leads/search?q=${encodeURIComponent(query)}`);
            renderLeads(data.leads || []);
        } catch (error) {
            const filtered = allLeads.filter((lead) => {
                const text = `${lead.name} ${lead.email} ${lead.company} ${lead.need}`.toLowerCase();
                return text.includes(query.toLowerCase());
            });
            renderLeads(filtered);
        }
    }, 250);
}

/* ============================================================
   HOT LEADS
============================================================ */
async function loadHotLeads() {
    const container = document.getElementById("hot-table");
    if (!container) return;
    container.innerHTML = "Loading...";
    try {
        const data = await api("/leads/hot");
        if (!data.leads.length) {
            container.innerHTML = "<div class='empty'>No Hot Leads.</div>";
            return;
        }
        container.innerHTML = `
            <div class="table-wrap">
                <table class="data-table">
                    <thead>
                        <tr><th>Lead</th><th>Score</th><th>Budget</th><th>Urgency</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        ${data.leads.map((lead) => `
                            <tr>
                                <td class="clickable" onclick="openLeadDetails(${lead.id})">
                                    <div class="lead-name">${escapeHTML(lead.name)}</div>
                                    <div class="lead-company">${escapeHTML(lead.company)}</div>
                                </td>
                                <td><strong>${lead.score ?? 0}</strong></td>
                                <td>${formatMoney(lead.budget)}</td>
                                <td>${escapeHTML(lead.urgency || "—")}</td>
                                <td>${statusBadge(lead.status)}</td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="error-box">${escapeHTML(error.message)}</div>`;
    }
}

/* ============================================================
   PIPELINE
============================================================ */
async function loadPipeline() {
    const board = document.getElementById("pipeline-board");
    if (!board) return;
    board.innerHTML = "Loading...";
    try {
        const data = await api("/pipeline");
        const pipeline = data.pipeline || {};
        renderPipeline(pipeline);
    } catch (error) {
        board.innerHTML = "<p style='color:#ff7b86'>Unable to load pipeline.</p>";
    }
}

function renderPipeline(pipeline) {
    const board = document.getElementById("pipeline-board");
    if (!board) return;
    const statuses = ["NEW", "CONTACTED", "REPLIED", "QUALIFIED", "MEETING_BOOKED", "WON", "LOST", "OTHER"];

    board.innerHTML = statuses
        .map((status) => {
            const items = Array.isArray(pipeline[status]) ? pipeline[status] : [];
            return `
                <div class="pipeline-column">
                    <div class="pipeline-column-header">
                        <strong>${escapeHTML(formatStatus(status))}</strong>
                        <span>${items.length}</span>
                    </div>
                    ${items.length ? items.map((lead) => `
                        <div class="pipeline-card" onclick="openLeadDetails(${lead.id})">
                            <strong>${escapeHTML(lead.name || "No name")}</strong>
                            <small>${escapeHTML(lead.company || "")}</small>
                            <small>Score: ${lead.score ?? 0}</small>
                            <small>Budget: ${formatMoney(lead.budget ?? 0)}</small>
                        </div>
                    `).join("") : `<div style="padding:20px;color:#8994a6;font-size:10px;">No leads</div>`}
                </div>
            `;
        })
        .join("");
}

/* ============================================================
   PRIORITIES
============================================================ */
async function loadPriorities() {
    const container = document.getElementById("priorities-list");
    if (!container) return;
    container.innerHTML = "Loading...";
    try {
        const data = await api("/leads/priorities");
        const priorities = data.priorities || [];
        if (!priorities.length) {
            container.innerHTML = "<p>No priorities.</p>";
            return;
        }
        container.innerHTML = priorities
            .map((item) => `
                <div class="priority-card">
                    <div class="card-main">
                        <strong>${escapeHTML(item.name)}</strong>
                        <p>${escapeHTML(item.company || "")} · ${escapeHTML(item.email || "")}</p>
                        <p>Urgency: ${escapeHTML(item.urgency)}</p>
                    </div>
                    <div class="card-meta">
                        <div class="score-large">${item.score}</div>
                        <div>
                            <div class="badge badge-hot">${escapeHTML(item.priority)}</div>
                            <div class="action">${escapeHTML(item.recommended_action || "")}</div>
                        </div>
                    </div>
                </div>
            `)
            .join("");
    } catch (error) {
        container.innerHTML = `<p>Error: ${escapeHTML(error.message)}</p>`;
    }
}

/* ============================================================
   FOLLOW-UPS
============================================================ */
async function loadFollowUps() {
    const container = document.getElementById("followups-list");
    if (!container) return;
    container.innerHTML = "Loading...";
    try {
        const data = await api("/leads/follow-ups");
        const followups = data.follow_ups || [];
        if (!followups.length) {
            container.innerHTML = "<p>No follow-ups.</p>";
            return;
        }
        container.innerHTML = followups
            .map((item) => `
                <div class="followup-card">
                    <div class="card-main">
                        <strong>${escapeHTML(item.name)}</strong>
                        <p>${escapeHTML(item.company || "")} · ${escapeHTML(item.email || "")}</p>
                        <p>Action: ${escapeHTML(item.action || "")}</p>
                    </div>
                    <div class="card-meta">
                        <div class="score-large">${item.score}</div>
                        <div class="action">${item.due ? "DUE NOW" : "UPCOMING"}</div>
                    </div>
                </div>
            `)
            .join("");
    } catch (error) {
        container.innerHTML = `<p>Error: ${escapeHTML(error.message)}</p>`;
    }
}

/* ============================================================
   CREATE LEAD (MODAL)
============================================================ */
function openLeadModal() {
    const modal = document.getElementById("lead-modal");
    if (modal) {
        modal.classList.add("show");
        const form = document.getElementById("lead-form");
        if (form) form.reset();
    }
}

function closeLeadModal() {
    const modal = document.getElementById("lead-modal");
    if (modal) modal.classList.remove("show");
}

async function createLead(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const payload = {
        name: formData.get("name"),
        email: formData.get("email"),
        company: formData.get("company"),
        need: formData.get("need"),
        budget: Number(formData.get("budget")),
        urgency: formData.get("urgency"),
    };
    try {
        const data = await api("/leads", { method: "POST", body: JSON.stringify(payload) });
        closeLeadModal();
        showToast(`Lead created (#${data.lead_id})`);
        await loadView(currentView);
        if (currentView === "dashboard") await loadDashboard();
    } catch (error) {
        showToast(error.message, "error");
    }
}

/* ============================================================
   LEAD DETAILS (MODAL)
============================================================ */
async function openLeadDetails(leadId) {
    const modal = document.getElementById("details-modal");
    const title = document.getElementById("details-title");
    const container = document.getElementById("lead-details");
    if (!modal || !container) return;

    modal.classList.add("show");
    title.textContent = "Loading...";
    container.innerHTML = "<div class='loading'>Loading lead...</div>";

    try {
        const data = await api(`/leads/${leadId}`);
        const lead = data.lead;
        title.textContent = lead.name;

        container.innerHTML = `
            <div class="detail-grid">
                <div class="detail-item"><span>Name</span><strong>${escapeHTML(lead.name)}</strong></div>
                <div class="detail-item"><span>Company</span><strong>${escapeHTML(lead.company)}</strong></div>
                <div class="detail-item"><span>Email</span><strong>${escapeHTML(lead.email)}</strong></div>
                <div class="detail-item"><span>Budget</span><strong>${formatMoney(lead.budget)}</strong></div>
                <div class="detail-item"><span>AI Score</span><strong>${lead.score ?? 0}/100</strong></div>
                <div class="detail-item"><span>Classification</span><strong>${badge(data.classification, data.classification.toLowerCase())}</strong></div>
                <div class="detail-item"><span>Urgency</span><strong>${escapeHTML(lead.urgency)}</strong></div>
                <div class="detail-item"><span>Status</span><strong>${escapeHTML(lead.status)}</strong></div>
            </div>
            <div class="detail-item" style="margin-top:14px"><span>Need</span><strong>${escapeHTML(lead.need)}</strong></div>
            <div class="detail-message"><strong>Recommended Action</strong><p>${escapeHTML(data.action)}</p></div>
            <div class="detail-message"><strong>Generated Sales Message</strong><p>${escapeHTML(data.sales_message)}</p></div>
            <div class="detail-status">
                <strong style="width:100%">Change Status</strong>
                ${["NEW","CONTACTED","REPLIED","QUALIFIED","MEETING_BOOKED","WON","LOST"].map((status) => `
                    <button class="${String(lead.status).toUpperCase() === status ? "primary-btn" : "secondary-btn"}" 
                            onclick="updateLeadStatus(${lead.id}, '${status}', true)">
                        ${status}
                    </button>
                `).join("")}
            </div>
        `;
    } catch (error) {
        container.innerHTML = `<div class="error-box">${escapeHTML(error.message)}</div>`;
    }
}

function closeDetailsModal() {
    const modal = document.getElementById("details-modal");
    if (modal) modal.classList.remove("show");
}

/* ============================================================
   UPDATE STATUS
============================================================ */
async function updateLeadStatus(leadId, status, fromDetails = false) {
    try {
        await api(`/leads/${leadId}/status`, {
            method: "PUT",
            body: JSON.stringify({ status }),
        });
        showToast(`Lead #${leadId} → ${status}`);
        if (fromDetails) await openLeadDetails(leadId);
        await loadView(currentView);
        if (currentView === "dashboard") await loadDashboard();
    } catch (error) {
        showToast(error.message, "error");
    }
}

/* ============================================================
   DELETE LEAD
============================================================ */
async function deleteLead(id) {
    const modal = document.getElementById('confirm-modal');
    const title = document.getElementById('confirm-title');
    const message = document.getElementById('confirm-message');
    const okBtn = document.getElementById('confirm-ok-btn');
    const cancelBtn = document.getElementById('confirm-cancel-btn');

    title.textContent = `Delete lead #${id}?`;
    message.textContent = `"${document.querySelector(`tr td:first-child`)?.textContent || 'Lead'}" will be permanently lost.`;
    modal.classList.add('show');

    const newOk = okBtn.cloneNode(true);
    const newCancel = cancelBtn.cloneNode(true);
    okBtn.parentNode.replaceChild(newOk, okBtn);
    cancelBtn.parentNode.replaceChild(newCancel, cancelBtn);

    newOk.addEventListener('click', async () => {
        modal.classList.remove('show');
        try {
            await api(`/leads/${id}`, { method: "DELETE" });
            showToast(`Lead #${id} deleted`);
            await loadView(currentView);
            if (currentView === "dashboard") await loadDashboard();
        } catch (error) {
            showToast(error.message, "error");
        }
    });

    newCancel.addEventListener('click', () => {
        modal.classList.remove('show');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('show');
    });
}

/* ============================================================
   MODAL EVENTS (click outside)
============================================================ */
window.addEventListener("click", (event) => {
    const leadModal = document.getElementById("lead-modal");
    const detailsModal = document.getElementById("details-modal");
    if (event.target === leadModal) closeLeadModal();
    if (event.target === detailsModal) closeDetailsModal();
});

/* ============================================================
   AUTO REFRESH
============================================================ */
function startAutoRefresh() {
    clearInterval(refreshTimer);
    refreshTimer = setInterval(async () => {
        try {
            await checkAPI();
            await loadView(currentView);
            if (currentView === "dashboard") await loadDashboard();
        } catch (error) {
            console.error("Auto refresh error:", error);
        }
    }, 30000);
}

/* ============================================================
   REFRESH CURRENT VIEW
============================================================ */
async function refreshCurrentView() {
    await checkAPI();
    await loadView(currentView);
    if (currentView === "dashboard") await loadDashboard();
    showToast("Data refreshed");
}