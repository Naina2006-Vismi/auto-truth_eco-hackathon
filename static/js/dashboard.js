/* AutoTruth Institutional Dashboard JS */

let compareMode = false;
let compareIds = [];
let currentData = null;
let allClaims = [];
let universeCompanies = [];

let gaugeChart = null;
let radarChart = null;
let offsetRingChart = null;
let claimSparklineChart = null;
let volatilityChart = null;
let driftChart = null;
let compareRadarChart = null;
let compareDeltaChart = null;

const PILLAR_LABELS = {
    raw_materials: "Raw Materials",
    manufacturing: "Manufacturing",
    supply_chain: "Supply Chain",
    use_phase: "Use Phase",
    end_of_life: "End of Life",
    offsets: "Offset Strategy",
};

const PILLAR_KEYS = Object.keys(PILLAR_LABELS);
const PILLAR_COLORS = ["#00e676", "#00d4ff", "#34d399", "#22d3ee", "#facc15", "#f59e0b"];

const API_BASE_CANDIDATES = [];
if (window.location.origin && window.location.origin !== "null") {
    API_BASE_CANDIDATES.push("");
}
API_BASE_CANDIDATES.push("http://localhost:5001");
API_BASE_CANDIDATES.push("http://127.0.0.1:5001");

const chartTextColor = "#9fb0c4";
const UPLOAD_ANALYSIS_KEY = "autotruth_uploaded_analysis";

window.toggleCompareMode = toggleCompareMode;
window.filterClaims = filterClaims;

document.addEventListener("DOMContentLoaded", async () => {
    const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
    if (isSafari && "scrollRestoration" in history) {
        history.scrollRestoration = "manual";
        window.scrollTo(0, 0);
    }

    window.addEventListener("error", (e) => {
        showRuntimeError(e?.message || "Unexpected runtime error");
    });

    if (typeof Chart === "undefined") {
        showRuntimeError("Chart.js failed to load. Verify internet access to CDN.");
        return;
    }

    bindHeroParallax();
    await loadSidebar();

    const params = new URLSearchParams(window.location.search);
    const cid = params.get("company");
    const model = params.get("model");
    const source = params.get("source");
    if (cid) {
        analyzeCompany(cid, model);
        return;
    }

    if (source === "upload") {
        const uploaded = loadUploadedAnalysis();
        if (uploaded) {
            currentData = uploaded;
            allClaims = uploaded.claims || [];
            document.getElementById("empty-state").style.display = "none";
            document.getElementById("loading-state").style.display = "none";
            document.getElementById("dash-content").style.display = "flex";
            document.getElementById("mode-label").textContent = "Uploaded Report Mode";
            renderDashboard(uploaded);
        }
    }
});

function loadUploadedAnalysis() {
    try {
        const raw = localStorage.getItem(UPLOAD_ANALYSIS_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (_) {
        return null;
    }
}

async function loadSidebar() {
    const res = await apiFetch("/api/companies");
    if (!res) return;

    universeCompanies = await res.json();
    const container = document.getElementById("sidebar-companies");
    container.innerHTML = "";

    universeCompanies.forEach((c) => {
        const btn = document.createElement("button");
        btn.className = "sidebar-btn";
        btn.id = `sb-${c.id}`;
        btn.innerHTML = `<span class="sb-logo">${c.logo}</span><span class="sb-name">${c.name}</span><span class="sb-model">${c.model}</span>`;
        btn.onclick = () => handleSidebarClick(c.id, btn);
        container.appendChild(btn);
    });
}

function handleSidebarClick(id, btn) {
    if (compareMode) {
        toggleCompanyInComparison(id, btn);
        return;
    }

    document.querySelectorAll(".sidebar-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    analyzeCompany(id);
}

function toggleCompareMode() {
    compareMode = !compareMode;
    compareIds = [];

    document.querySelectorAll(".sidebar-btn").forEach((b) => {
        b.classList.remove("selected-compare");
    });

    const hint = document.getElementById("compare-hint");
    const modeLabel = document.getElementById("mode-label");
    const toggleBtn = document.getElementById("toggle-compare-btn");
    const dashContent = document.getElementById("dash-content");
    const compareContent = document.getElementById("compare-content");
    const emptyState = document.getElementById("empty-state");
    const loading = document.getElementById("loading-state");

    if (compareMode) {
        hint.style.display = "flex";
        modeLabel.textContent = "Compare Intelligence";
        toggleBtn.textContent = "Exit Compare";
        dashContent.style.display = "none";
        compareContent.style.display = "flex";
        emptyState.style.display = "none";
        loading.style.display = "none";
        document.getElementById("compare-grid").innerHTML = "";
    } else {
        hint.style.display = "none";
        modeLabel.textContent = "Intelligence Mode";
        toggleBtn.textContent = "Compare Mode";
        compareContent.style.display = "none";
        emptyState.style.display = currentData ? "none" : "flex";
        dashContent.style.display = currentData ? "flex" : "none";
    }
}

async function toggleCompanyInComparison(id, btn) {
    const idx = compareIds.indexOf(id);
    if (idx > -1) {
        compareIds.splice(idx, 1);
        btn.classList.remove("selected-compare");
    } else {
        if (compareIds.length >= 4) {
            alert("Maximum 4 companies can be compared.");
            return;
        }
        compareIds.push(id);
        btn.classList.add("selected-compare");
    }

    if (compareIds.length > 0) {
        await renderComparison();
    } else {
        document.getElementById("compare-grid").innerHTML = "";
        destroyCompareCharts();
    }
}

async function analyzeCompany(id, model = null) {
    showLoading(true);
    const query = model ? `?model=${encodeURIComponent(model)}` : "";
    const res = await apiFetch(`/api/analyze/${id}${query}`);
    if (!res) {
        showLoading(false);
        return;
    }

    const data = await res.json();
    currentData = data;
    allClaims = data.claims || [];

    renderDashboard(data);
    showLoading(false);
}

function showLoading(on) {
    document.getElementById("loading-state").style.display = on ? "flex" : "none";
    document.getElementById("empty-state").style.display = "none";
    document.getElementById("dash-content").style.display = on ? "none" : "flex";
}

async function renderDashboard(d) {
    renderHero(d);
    renderZoneA(d);
    renderZoneB(d);
    renderZoneC(d);
    renderClaims(allClaims);
}

function renderHero(d) {
    const percentile = scoreToPercentile(d.lts);
    const momentum = calculateMomentum(d.temporal_drift);

    document.getElementById("company-title").textContent = d.company || "Issuer";
    document.getElementById("company-model").textContent = d.model || "Model";
    document.getElementById("report-year").textContent = `Report ${d.report_year}`;
    document.getElementById("esg-badge").textContent = `ESG ${d.esg_investor_index?.rating || "--"}`;

    animateNumber("hero-transparency", d.lts, 1, "");
    document.getElementById("hero-change").textContent = `${momentum.sign} ${Math.abs(momentum.avgDelta).toFixed(1)}% this quarter`;
    document.getElementById("hero-change").className = `hero-kpi-delta ${momentum.avgDelta >= 0 ? "up" : "down"}`;

    document.getElementById("hero-percentile").textContent = `${percentile}th`;
    document.getElementById("hero-rank-badge").textContent = percentile >= 70 ? "Top 30% EV Transparency" : "Watchlist Cohort";
}

function renderZoneA(d) {
    const riskProbability = computeRiskProbability(d);
    const percentile = scoreToPercentile(d.lts);
    const confidenceRange = scoreConfidenceBand(d.claims || []);
    const momentum = calculateMomentum(d.temporal_drift);

    drawGauge(d.lts);
    animateNumber("gauge-score", d.lts, 1, "");

    document.getElementById("confidence-interval").textContent = `Confidence Interval: ${Math.max(0, d.lts - confidenceRange).toFixed(1)} - ${Math.min(100, d.lts + confidenceRange).toFixed(1)}`;
    document.getElementById("risk-desc").textContent = d.risk?.description || "";

    animateNumber("risk-prob-value", riskProbability, 1, "%");
    const riskBar = document.getElementById("risk-prob-bar");
    riskBar.style.width = `${riskProbability}%`;
    riskBar.style.background = riskProbability > 70
        ? "linear-gradient(90deg,#f97316,#ef4444)"
        : riskProbability > 45
            ? "linear-gradient(90deg,#facc15,#f97316)"
            : "linear-gradient(90deg,#00e676,#00d4ff)";

    const momentumEl = document.getElementById("momentum-indicator");
    momentumEl.textContent = `${momentum.avgDelta >= 0 ? "Improving" : "Declining"} (${momentum.sign} ${Math.abs(momentum.avgDelta).toFixed(1)})`;
    momentumEl.className = `momentum-indicator ${momentum.avgDelta >= 0 ? "up" : "down"}`;

    document.getElementById("percentile-rank").textContent = `${percentile}th percentile`;

    const regRow = document.getElementById("regulatory-row");
    const regulations = [
        ["EU CSRD", !!d.regulatory_alignment?.CSRD],
        ["SEC Climate", !!d.regulatory_alignment?.SEC_Climate],
        ["GHG Protocol", (d.claim_ratio?.numeric || 0) > 0.35],
        ["GRI", !!d.regulatory_alignment?.GRI],
        ["TCFD", !!d.regulatory_alignment?.TCFD],
    ];
    regRow.innerHTML = regulations.map(([name, met]) => `<span class="reg-chip ${met ? "met" : "not-met"}">${name}</span>`).join("");

    const esgBadges = document.getElementById("esg-badges");
    esgBadges.innerHTML = `<span class="reg-chip met">${d.esg_investor_index?.rating || "--"}</span><span class="reg-chip ${riskProbability > 60 ? "not-met" : "met"}">${d.risk?.label || "Risk"}</span>`;
}

function renderZoneB(d) {
    drawRadar(d.pillar_scores || {});
    drawOffsetRing(d.offset_analysis || {});
    drawClaimSparkline(d.claims || []);
    drawVolatilityChart(d);
    drawDriftChart(d.temporal_drift || {});

    document.getElementById("drift-years").textContent = `${(d.report_year || "--") - 1} -> ${d.report_year || "--"}`;
    document.getElementById("offset-pct").textContent = `${d.offset_analysis?.offset_dependency_pct ?? "--"}%`;

    const qualityBadge = document.getElementById("offset-quality-badge");
    const quality = d.offset_analysis?.offset_quality || "Unverified";
    qualityBadge.textContent = `Offset Quality: ${quality}`;
    qualityBadge.className = `offset-quality-badge ${quality.toLowerCase().replace(/\s+/g, "-")}`;

    document.getElementById("offset-quality-desc").textContent = d.offset_analysis?.quality_description || "";

    renderHeatmapAndDepth(d.pillar_scores || {});
}

function renderZoneC(d) {
    const bd = d.breakdown || {};
    const tieBreakdown = document.getElementById("tie-breakdown");
    tieBreakdown.innerHTML = `
        <div class="breakdown-item"><span>Base Weighted Score</span><strong>${formatSigned(bd.pillar_weighted_base, false)}</strong></div>
        <div class="breakdown-item"><span>Claim Quality Adjustment</span><strong>${formatSigned(bd.claim_quality_adjustment)}</strong></div>
        <div class="breakdown-item"><span>Offset Penalty</span><strong>${formatSigned(bd.offset_penalty)}</strong></div>
        <div class="breakdown-item"><span>Regulatory Bonus</span><strong>${formatSigned(bd.regulatory_bonus)}</strong></div>
        <div class="breakdown-item"><span>Grid Carbon Adjustment</span><strong>${formatSigned(bd.grid_penalty)}</strong></div>
        <div class="breakdown-item total"><span>Final TIE Score</span><strong>${d.lts}</strong></div>
    `;

    document.getElementById("impact-calc").textContent = `TIE = ${bd.pillar_weighted_base ?? 0} ${signedToken(bd.claim_quality_adjustment)} ${signedToken(bd.offset_penalty)} ${signedToken(bd.regulatory_bonus)} ${signedToken(bd.grid_penalty)} = ${d.lts}`;

    const insights = buildInsights(d);
    document.getElementById("ai-summary").innerHTML = insights.map((s) => `<p>${s}</p>`).join("");

    const drivers = detectRiskDrivers(d);
    const driverContainer = document.getElementById("risk-drivers");
    driverContainer.innerHTML = drivers.map((x) => `<span class="driver-pill">${x}</span>`).join("");

    renderClaimReasoning(d.claims || []);
}

function renderHeatmapAndDepth(scores) {
    const matrix = document.getElementById("heatmap-matrix");
    const depthList = document.getElementById("depth-list");

    matrix.innerHTML = PILLAR_KEYS.map((k, idx) => {
        const score = scores[k] || 0;
        const level = Math.min(4, Math.max(0, Math.floor(score / 20)));
        const cells = [0, 1, 2, 3, 4].map((cellIdx) => {
            const active = cellIdx <= level;
            return `<span class="heat-cell ${active ? "active" : ""}" style="--heat-color:${PILLAR_COLORS[idx]}"></span>`;
        }).join("");

        return `
            <div class="heat-row">
                <span class="heat-label">${PILLAR_LABELS[k]}</span>
                <div class="heat-cells">${cells}</div>
                <span class="heat-score">${score}</span>
            </div>
        `;
    }).join("");

    depthList.innerHTML = PILLAR_KEYS.map((k) => {
        const score = scores[k] || 0;
        const level = Math.min(4, Math.max(0, Math.floor(score / 20)));
        return `<div class="depth-item"><span>${PILLAR_LABELS[k]}</span><strong>Level ${level}</strong></div>`;
    }).join("");
}

function renderClaimReasoning(claims) {
    const container = document.getElementById("claim-reasoning");
    const topClaims = [...claims]
        .sort((a, b) => Math.abs((b.impact_score || 0)) - Math.abs((a.impact_score || 0)))
        .slice(0, 5);

    container.innerHTML = topClaims.map((c, idx) => {
        return `
            <details class="reason-item" ${idx === 0 ? "open" : ""}>
                <summary>${c.type} | Impact ${formatSigned(c.impact_score, false)}</summary>
                <p>${c.text}</p>
                <p><strong>Reasoning:</strong> ${c.type === "VAGUE" ? "Claim lacks measurable disclosure depth." : "Claim contributes measurable disclosure evidence."}</p>
                <p><strong>Suggested rewrite:</strong> ${c.rewrite_suggestion || "No rewrite required."}</p>
            </details>
        `;
    }).join("");
}

function renderClaims(claims, filter = "all") {
    const tbody = document.getElementById("claims-tbody");
    const filtered = filter === "all" ? claims : claims.filter((c) => c.type === filter);

    tbody.innerHTML = filtered.map((c) => {
        const impactVal = c.impact_score > 0 ? `+${c.impact_score}` : c.impact_score;
        const impactClass = c.impact_score > 0 ? "impact-pos" : c.impact_score < 0 ? "impact-neg" : "impact-neu";
        const confPct = Math.round((c.confidence || 0) * 100);
        const pillarLabel = PILLAR_LABELS[c.pillar] || c.pillar;

        return `
        <tr>
            <td class="claim-text">${c.text}</td>
            <td><span class="claim-type-tag ${c.type}">${c.type.replace("_", " ")}</span></td>
            <td>${pillarLabel}</td>
            <td class="${impactClass}">${impactVal}</td>
            <td>
                <div>${confPct}%</div>
                <div class="confidence-bar"><div class="confidence-fill" style="width:${confPct}%"></div></div>
            </td>
            <td>${c.rewrite_suggestion || "-"}</td>
        </tr>
        `;
    }).join("");
}

function filterClaims(type, btn) {
    document.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    renderClaims(allClaims, type);
}

async function renderComparison() {
    const idsStr = compareIds.join(",");
    const res = await apiFetch(`/api/compare?ids=${idsStr}`);
    if (!res) return;

    const results = await res.json();
    if (!results.length) return;

    const sorted = [...results].sort((a, b) => b.lts - a.lts);
    const baseline = sorted[0].pillar_scores || {};

    const grid = document.getElementById("compare-grid");
    grid.innerHTML = sorted.map((r, idx) => {
        const rank = idx === 0 ? "Leader" : idx === sorted.length - 1 ? "Risk" : "Watchlist";
        const rankClass = idx === 0 ? "leader" : idx === sorted.length - 1 ? "risk" : "watch";
        const riskProb = computeRiskProbability(r);

        const pillarDeltas = PILLAR_KEYS.map((k) => {
            const delta = (r.pillar_scores?.[k] || 0) - (baseline[k] || 0);
            return `<div class="delta-row"><span>${PILLAR_LABELS[k]}</span><span class="${delta >= 0 ? "pos" : "neg"}">${formatSigned(delta, false)}</span></div>`;
        }).join("");

        return `
            <article class="glass-card platform-card compare-company-card">
                <div class="compare-company-header">
                    <span class="compare-logo">${r.logo || "EV"}</span>
                    <div>
                        <div class="compare-name">${r.company}</div>
                        <div class="compare-model">${r.model}</div>
                    </div>
                    <span class="rank-badge ${rankClass}">${rank}</span>
                </div>
                <div class="compare-lts">${r.lts}</div>
                <div class="metric-inline"><span>Greenwashing Risk</span><strong>${riskProb.toFixed(1)}%</strong></div>
                <div class="risk-track"><div class="risk-fill" style="width:${riskProb}%;"></div></div>
                <div class="metric-inline"><span>Offset Dependency</span><strong>${r.offset_analysis?.offset_dependency_pct || 0}%</strong></div>
                <div class="offset-gradient"><span style="width:${r.offset_analysis?.offset_dependency_pct || 0}%"></span></div>
                <div class="delta-block">${pillarDeltas}</div>
            </article>
        `;
    }).join("");

    drawCompareRadar(sorted);
    drawCompareDelta(sorted);
}

function drawGauge(score) {
    const ctx = document.getElementById("gauge-canvas").getContext("2d");
    if (gaugeChart) gaugeChart.destroy();

    gaugeChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            datasets: [{
                data: [score, 100 - score],
                backgroundColor: ["#00e676", "rgba(255,255,255,0.08)"],
                borderColor: ["rgba(0,230,118,0.35)", "transparent"],
                borderWidth: 1,
                circumference: 270,
                rotation: 225,
            }],
        },
        options: {
            cutout: "82%",
            animation: { duration: 750 },
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
        },
    });
}

function drawRadar(scores) {
    const ctx = document.getElementById("radar-canvas").getContext("2d");
    if (radarChart) radarChart.destroy();

    const gradient = ctx.createRadialGradient(220, 180, 40, 220, 180, 220);
    gradient.addColorStop(0, "rgba(0,230,118,0.26)");
    gradient.addColorStop(1, "rgba(0,212,255,0.04)");

    radarChart = new Chart(ctx, {
        type: "radar",
        data: {
            labels: PILLAR_KEYS.map((k) => PILLAR_LABELS[k]),
            datasets: [{
                label: "Pillar Score",
                data: PILLAR_KEYS.map((k) => scores[k] || 0),
                backgroundColor: gradient,
                borderColor: "#00d4ff",
                pointBackgroundColor: "#00e676",
                pointHoverBackgroundColor: "#ffffff",
                borderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
            }],
        },
        options: {
            maintainAspectRatio: false,
            animation: { duration: 650 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx2) => `${ctx2.label}: ${ctx2.raw}`,
                    },
                },
            },
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    ticks: { display: false },
                    angleLines: { color: "rgba(148,163,184,0.2)" },
                    grid: { color: "rgba(148,163,184,0.16)" },
                    pointLabels: { color: chartTextColor, font: { size: 11 } },
                },
            },
        },
    });
}

function drawOffsetRing(oa) {
    const ctx = document.getElementById("offset-ring-canvas").getContext("2d");
    if (offsetRingChart) offsetRingChart.destroy();

    const pct = Math.max(0, Math.min(100, oa.offset_dependency_pct || 0));
    const qualityScore = oa.offset_quality === "Gold Standard" ? 90 : oa.offset_quality === "VCS" ? 70 : oa.offset_quality === "None" ? 100 : 35;

    offsetRingChart = new Chart(ctx, {
        type: "doughnut",
        data: {
            datasets: [
                {
                    data: [pct, 100 - pct],
                    backgroundColor: ["#f97316", "rgba(255,255,255,0.07)"],
                    borderWidth: 0,
                    weight: 1,
                },
                {
                    data: [qualityScore, 100 - qualityScore],
                    backgroundColor: ["#00d4ff", "rgba(255,255,255,0.03)"],
                    borderWidth: 0,
                    weight: 0.7,
                },
            ],
        },
        options: {
            cutout: "55%",
            plugins: { legend: { display: false }, tooltip: { enabled: true } },
            animation: { duration: 700 },
        },
    });
}

function drawClaimSparkline(claims) {
    const ctx = document.getElementById("claim-sparkline-canvas").getContext("2d");
    if (claimSparklineChart) claimSparklineChart.destroy();

    const labels = claims.map((_, i) => `C${i + 1}`);
    const series = claims.map((c) => {
        const conf = (c.confidence || 0) * 100;
        return Math.max(0, conf + (c.impact_score || 0) * 2);
    });

    claimSparklineChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                data: series,
                borderColor: "#00d4ff",
                backgroundColor: "rgba(0,212,255,0.15)",
                fill: true,
                tension: 0.35,
                pointRadius: 0,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { display: false, min: 0, max: 100 },
            },
        },
    });
}

function drawVolatilityChart(d) {
    const ctx = document.getElementById("volatility-canvas").getContext("2d");
    if (volatilityChart) volatilityChart.destroy();

    const current = PILLAR_KEYS.map((k) => d.pillar_scores?.[k] || 0);
    const prev = PILLAR_KEYS.map((k) => d.prior_year_scores?.[k] || 0);
    const base = prev.reduce((a, b) => a + b, 0) / Math.max(prev.length, 1);
    const now = current.reduce((a, b) => a + b, 0) / Math.max(current.length, 1);

    const points = [
        Math.max(0, base - 4 + seededNoise(d.company, 1)),
        Math.max(0, base + seededNoise(d.company, 2)),
        Math.max(0, now - 2 + seededNoise(d.company, 3)),
        Math.max(0, now + seededNoise(d.company, 4)),
    ];

    volatilityChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: ["Q1", "Q2", "Q3", "Q4"],
            datasets: [{
                data: points,
                borderColor: "#00e676",
                backgroundColor: "rgba(0,230,118,0.14)",
                fill: true,
                tension: 0.35,
                pointRadius: 2,
            }],
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: chartTextColor } },
                y: { ticks: { color: chartTextColor }, min: 0, max: 100, grid: { color: "rgba(148,163,184,0.12)" } },
            },
        },
    });
}

function drawDriftChart(drift) {
    const ctx = document.getElementById("drift-canvas").getContext("2d");
    if (driftChart) driftChart.destroy();

    const deltas = PILLAR_KEYS.map((k) => drift[k]?.delta || 0);
    driftChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: PILLAR_KEYS.map((k) => PILLAR_LABELS[k]),
            datasets: [{
                data: deltas,
                backgroundColor: deltas.map((v) => (v >= 0 ? "rgba(0,230,118,0.55)" : "rgba(249,115,22,0.6)")),
                borderRadius: 6,
            }],
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: chartTextColor, font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: chartTextColor }, grid: { color: "rgba(148,163,184,0.12)" } },
            },
        },
    });
}

function drawCompareRadar(results) {
    const ctx = document.getElementById("compare-radar-canvas").getContext("2d");
    if (compareRadarChart) compareRadarChart.destroy();

    compareRadarChart = new Chart(ctx, {
        type: "radar",
        data: {
            labels: PILLAR_KEYS.map((k) => PILLAR_LABELS[k]),
            datasets: results.map((r, i) => ({
                label: r.company,
                data: PILLAR_KEYS.map((k) => r.pillar_scores?.[k] || 0),
                borderColor: PILLAR_COLORS[i % PILLAR_COLORS.length],
                backgroundColor: `${PILLAR_COLORS[i % PILLAR_COLORS.length]}22`,
                borderWidth: 2,
                pointRadius: 2,
            })),
        },
        options: {
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: chartTextColor } },
            },
            scales: {
                r: {
                    min: 0,
                    max: 100,
                    ticks: { display: false },
                    pointLabels: { color: chartTextColor, font: { size: 11 } },
                    grid: { color: "rgba(148,163,184,0.16)" },
                    angleLines: { color: "rgba(148,163,184,0.2)" },
                },
            },
        },
    });
}

function drawCompareDelta(results) {
    const ctx = document.getElementById("compare-delta-canvas").getContext("2d");
    if (compareDeltaChart) compareDeltaChart.destroy();

    const leader = [...results].sort((a, b) => b.lts - a.lts)[0];

    compareDeltaChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: PILLAR_KEYS.map((k) => PILLAR_LABELS[k]),
            datasets: results.map((r, i) => ({
                label: r.company,
                data: PILLAR_KEYS.map((k) => (r.pillar_scores?.[k] || 0) - (leader.pillar_scores?.[k] || 0)),
                backgroundColor: `${PILLAR_COLORS[i % PILLAR_COLORS.length]}88`,
                borderRadius: 4,
            })),
        },
        options: {
            plugins: { legend: { labels: { color: chartTextColor } } },
            scales: {
                x: { ticks: { color: chartTextColor, font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: chartTextColor }, grid: { color: "rgba(148,163,184,0.12)" } },
            },
        },
    });
}

function destroyCompareCharts() {
    if (compareRadarChart) compareRadarChart.destroy();
    if (compareDeltaChart) compareDeltaChart.destroy();
    compareRadarChart = null;
    compareDeltaChart = null;
}

async function apiFetch(path) {
    for (const base of API_BASE_CANDIDATES) {
        try {
            const res = await fetch(`${base}${path}`);
            if (!res.ok) throw new Error(`API ${res.status}`);
            return res;
        } catch (err) {
            // continue fallback
        }
    }

    showApiError();
    return null;
}

function showApiError() {
    const empty = document.getElementById("empty-state");
    const loading = document.getElementById("loading-state");
    const dash = document.getElementById("dash-content");

    loading.style.display = "none";
    dash.style.display = "none";
    empty.style.display = "flex";
    empty.innerHTML = `
        <div class="empty-icon">API</div>
        <h2>Dashboard API not reachable</h2>
        <p>Start Flask and open <strong>http://localhost:5001/dashboard</strong>.</p>
    `;
}

function showRuntimeError(message) {
    const empty = document.getElementById("empty-state");
    const loading = document.getElementById("loading-state");
    const dash = document.getElementById("dash-content");

    loading.style.display = "none";
    dash.style.display = "none";
    empty.style.display = "flex";
    empty.innerHTML = `
        <div class="empty-icon">ERR</div>
        <h2>Dashboard failed to load</h2>
        <p>${message}</p>
    `;
}

function buildInsights(d) {
    const insights = [];
    const riskProb = computeRiskProbability(d);

    insights.push(`TIE score ${d.lts} with ${scoreToPercentile(d.lts)}th percentile market position.`);

    if ((d.claim_ratio?.vague || 0) > 0.3) {
        insights.push("Vague claim density is elevated; quantitative evidence quality is below institutional baseline.");
    } else {
        insights.push("Numeric disclosure density supports stronger auditability across lifecycle assertions.");
    }

    if ((d.offset_analysis?.offset_dependency_pct || 0) > 35) {
        insights.push("Offset dependency is high and increases transition-risk scrutiny from investor committees.");
    }

    insights.push(`Modeled greenwashing probability is ${riskProb.toFixed(1)}%, driven by claim quality and offset structure.`);
    return insights;
}

function detectRiskDrivers(d) {
    const out = [];

    if ((d.pillar_scores?.supply_chain || 0) < 45) out.push("Scope 3 missing depth");
    if ((d.offset_analysis?.offset_dependency_pct || 0) > 35) out.push("Offset overreliance");
    if ((d.claim_ratio?.vague || 0) > 0.3) out.push("Vague claim load");
    if (!d.regulatory_alignment?.CSRD) out.push("CSRD misalignment");
    if (!out.length) out.push("No critical drivers");

    return out;
}

function calculateMomentum(drift = {}) {
    const values = Object.values(drift).map((x) => x.delta || 0);
    if (!values.length) return { avgDelta: 0, sign: "+0.0" };

    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const sign = avg >= 0 ? `+${avg.toFixed(1)}` : avg.toFixed(1);
    return { avgDelta: avg, sign };
}

function computeRiskProbability(d) {
    const ltsPenalty = 100 - (d.lts || 0);
    const offsetPenalty = (d.offset_analysis?.offset_dependency_pct || 0) * 0.35;
    const vaguePenalty = (d.claim_ratio?.vague || 0) * 28;
    const supplyPenalty = Math.max(0, 50 - (d.pillar_scores?.supply_chain || 0)) * 0.3;

    const raw = ltsPenalty * 0.62 + offsetPenalty + vaguePenalty + supplyPenalty;
    return Math.max(5, Math.min(95, raw));
}

function scoreConfidenceBand(claims) {
    if (!claims.length) return 6;
    const avgConfidence = claims.reduce((sum, c) => sum + (c.confidence || 0.6), 0) / claims.length;
    return Math.max(2.5, (1 - avgConfidence) * 20);
}

function scoreToPercentile(score) {
    return Math.max(1, Math.min(99, Math.round(score)));
}

function animateNumber(id, to, decimals = 0, suffix = "") {
    const el = document.getElementById(id);
    if (!el) return;

    const from = parseFloat((el.textContent || "0").replace(/[^\d.-]/g, "")) || 0;
    const duration = 460;
    const start = performance.now();

    function tick(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        const value = from + (to - from) * eased;
        el.textContent = `${value.toFixed(decimals)}${suffix}`;
        if (t < 1) requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
}

function formatSigned(value, alwaysSign = true) {
    const v = Number(value || 0);
    if (alwaysSign) return v >= 0 ? `+${v}` : `${v}`;
    return `${v}`;
}

function signedToken(value) {
    const v = Number(value || 0);
    return v >= 0 ? `+ ${v}` : `- ${Math.abs(v)}`;
}

function seededNoise(seed, step) {
    const text = `${seed || "AUTO"}-${step}`;
    let h = 0;
    for (let i = 0; i < text.length; i += 1) {
        h = (h << 5) - h + text.charCodeAt(i);
        h |= 0;
    }
    return ((h % 100) / 100) * 6;
}

function bindHeroParallax() {
    const hero = document.getElementById("intel-hero");
    if (!hero) return;

    window.addEventListener("scroll", () => {
        const y = window.scrollY || 0;
        hero.style.transform = `translateY(${Math.min(16, y * 0.06)}px)`;
    }, { passive: true });
}
