/**
 * 📊 Results Page — Display hospital matches and enable navigation.
 */

// ─── Load Results ───────────────────────────────
document.addEventListener("DOMContentLoaded", loadResults);

async function loadResults() {
    // Try sessionStorage first (faster), then API fallback
    let data = null;
    const cached = sessionStorage.getItem("sos_result");

    if (cached) {
        data = JSON.parse(cached);
        sessionStorage.removeItem("sos_result");
    }

    if (!data) {
        // Fetch from API
        try {
            const resp = await fetch(`/api/sos/${SOS_ID}`);
            if (!resp.ok) throw new Error("SOS not found");
            // For API fallback, re-trigger scoring (simplified view)
            data = await resp.json();
        } catch (err) {
            document.getElementById("best-hospital").innerHTML = `
                <div style="text-align:center;padding:30px;">
                    <p style="font-size:48px;margin-bottom:12px;">😔</p>
                    <h3>SOS request not found</h3>
                    <p style="color:var(--text-dim);margin:12px 0;">This emergency request may have expired.</p>
                    <a href="/" class="btn btn-primary">Start New Emergency</a>
                </div>
            `;
            return;
        }
    }

    renderResults(data);
}

function renderResults(data) {
    // Set emergency badge
    const badge = document.getElementById("emergency-badge");
    const typeEmojis = {
        accident: "🚗", cardiac: "❤️", trauma: "🩹",
        maternity: "🤰", burns: "🔥", neuro: "🧠", general: "🏥"
    };
    const emoji = typeEmojis[data.emergency_type] || "🏥";
    badge.textContent = `${emoji} ${data.emergency_type.toUpperCase()} Emergency`;

    // Render best hospital
    if (data.best_hospital) {
        renderHospitalCard("best-hospital", data.best_hospital, "best");

        // Show navigate button
        const navSection = document.getElementById("nav-section");
        const navBtn = document.getElementById("navigate-btn");
        navBtn.href = data.best_hospital.navigation_url;
        navSection.classList.remove("hidden");

        // Show score breakdown
        renderScoreBreakdown(data.best_hospital.score_breakdown);
    }

    // Render backup hospital
    if (data.backup_hospital) {
        const backupSection = document.getElementById("backup-section");
        backupSection.classList.remove("hidden");
        renderHospitalCard("backup-hospital", data.backup_hospital, "backup");
        document.getElementById("backup-nav-btn").href = data.backup_hospital.navigation_url;
    }

    // Render all hospitals
    if (data.all_hospitals && data.all_hospitals.length > 0) {
        renderAllHospitals(data.all_hospitals);
    }
}

function renderHospitalCard(containerId, hospital, type) {
    const container = document.getElementById(containerId);
    const badgeClass = type === "best" ? "badge-best" : "badge-backup";
    const badgeText = type === "best" ? "✅ BEST MATCH" : "🔄 BACKUP OPTION";

    const score = Math.round(hospital.readiness_score * 100);
    const scoreColor = score >= 80 ? "var(--success)" : score >= 60 ? "var(--warning)" : "var(--danger)";

    // Determine which facilities match (for highlighting)
    const facilitiesTags = (hospital.facilities || []).map(f =>
        `<span class="tag">${f}</span>`
    ).join("");

    container.innerHTML = `
        <span class="card-badge ${badgeClass}">${badgeText}</span>
        <h2 class="card-hospital-name">${hospital.name}</h2>
        <p class="card-address">📍 ${hospital.address || "Address not available"}</p>

        <div class="card-stats">
            <div class="stat-item">
                <div class="stat-value score" style="color:${scoreColor}">${score}%</div>
                <div class="stat-label">Readiness</div>
            </div>
            <div class="stat-item">
                <div class="stat-value distance">${hospital.distance_km} km</div>
                <div class="stat-label">Distance</div>
            </div>
            <div class="stat-item">
                <div class="stat-value eta">${Math.round(hospital.eta_minutes)} min</div>
                <div class="stat-label">ETA</div>
            </div>
        </div>

        <div style="display:flex;gap:16px;margin-bottom:12px;">
            <div>
                <span style="font-size:12px;color:var(--text-dim);">ICU Beds:</span>
                <strong style="color:${hospital.available_icu_beds > 3 ? 'var(--success)' : 'var(--danger)'}">
                    ${hospital.available_icu_beds} available
                </strong>
            </div>
        </div>

        <div class="card-tags">${facilitiesTags}</div>

        ${hospital.phone ? `<p class="card-phone">📞 <a href="tel:${hospital.phone}">${hospital.phone}</a></p>` : ""}
    `;
}

function renderScoreBreakdown(scores) {
    if (!scores) return;

    const section = document.getElementById("score-section");
    section.classList.remove("hidden");

    const bars = document.getElementById("score-bars");
    const scoreItems = [
        { key: "facility", label: "Facility Match", css: "facility" },
        { key: "distance", label: "Proximity", css: "distance" },
        { key: "bed", label: "Bed Availability", css: "bed" },
        { key: "specialist", label: "Specialist", css: "specialist" },
        { key: "prediction", label: "Prediction", css: "prediction" },
        { key: "history", label: "History", css: "history" }
    ];

    bars.innerHTML = scoreItems.map(item => {
        const val = scores[item.key] || 0;
        const pct = Math.round(val * 100);
        return `
            <div class="score-row">
                <span class="score-label">${item.label}</span>
                <div class="score-bar-bg">
                    <div class="score-bar-fill ${item.css}" style="width:${pct}%"></div>
                </div>
                <span class="score-value">${pct}%</span>
            </div>
        `;
    }).join("");
}

function renderAllHospitals(hospitals) {
    const section = document.getElementById("all-section");
    section.classList.remove("hidden");

    const list = document.getElementById("all-hospitals");
    list.innerHTML = hospitals.map((h, i) => {
        const score = Math.round(h.readiness_score * 100);
        return `
            <div class="all-hospital-item">
                <div class="all-hospital-info">
                    <div class="name">${i + 1}. ${h.name}</div>
                    <div class="meta">${h.distance_km} km • ${Math.round(h.eta_minutes)} min ETA • ICU: ${h.available_icu_beds}</div>
                </div>
                <span class="all-hospital-score">${score}%</span>
                <a href="${h.navigation_url}" target="_blank" class="all-hospital-nav">Navigate →</a>
            </div>
        `;
    }).join("");
}
