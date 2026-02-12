/**
 * 🏥 Hospital Dashboard — Manage availability, receive alerts.
 */

// ─── State ──────────────────────────────────────
let currentHospital = null;
let doctorsList = [];

// ─── Init ───────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    await loadHospitalList();
    initWebSocket();
});

// ─── Load Hospital List ─────────────────────────
async function loadHospitalList() {
    try {
        const resp = await fetch("/api/hospitals");
        const data = await resp.json();

        const select = document.getElementById("hospital-select");
        data.hospitals.forEach(h => {
            const opt = document.createElement("option");
            opt.value = h.id;
            opt.textContent = h.name;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error("Failed to load hospitals:", err);
    }
}

// ─── Load Selected Hospital ─────────────────────
async function loadHospital() {
    const id = document.getElementById("hospital-select").value;
    if (!id) {
        document.getElementById("status-panel").classList.add("hidden");
        return;
    }

    try {
        const resp = await fetch(`/api/hospitals/${id}`);
        currentHospital = await resp.json();

        document.getElementById("hospital-name").textContent = currentHospital.name;
        document.getElementById("icu-beds").value = currentHospital.available_icu_beds || 0;
        document.getElementById("gen-beds").value = currentHospital.available_general_beds || 0;
        document.getElementById("load-pct").value = currentHospital.load_percentage || 50;
        updateLoadLabel();

        // Load doctors
        doctorsList = currentHospital.doctors_on_duty || [];
        renderDoctors();

        document.getElementById("status-panel").classList.remove("hidden");
        hideFeedback();
    } catch (err) {
        console.error("Failed to load hospital:", err);
    }
}

// ─── Adjust +/- Controls ────────────────────────
function adjustValue(inputId, delta) {
    const input = document.getElementById(inputId);
    let val = parseInt(input.value) || 0;
    val = Math.max(0, val + delta);
    input.value = val;
}

function updateLoadLabel() {
    const val = document.getElementById("load-pct").value;
    const label = document.getElementById("load-label");
    label.textContent = `${val}%`;

    if (val >= 80) label.style.color = "var(--danger)";
    else if (val >= 60) label.style.color = "var(--warning)";
    else label.style.color = "var(--success)";
}

// ─── Doctors Management ─────────────────────────
function renderDoctors() {
    const container = document.getElementById("doctors-list");
    container.innerHTML = doctorsList.map((doc, i) => `
        <span class="doctor-chip">
            ${doc}
            <span class="remove" onclick="removeDoctor(${i})">✕</span>
        </span>
    `).join("");
}

function addDoctor() {
    const input = document.getElementById("new-doctor");
    const name = input.value.trim();
    if (!name) return;

    doctorsList.push(name);
    renderDoctors();
    input.value = "";
}

function removeDoctor(index) {
    doctorsList.splice(index, 1);
    renderDoctors();
}

// ─── Save Status ────────────────────────────────
async function saveStatus() {
    if (!currentHospital) return;

    const updates = {
        available_icu_beds: parseInt(document.getElementById("icu-beds").value) || 0,
        available_general_beds: parseInt(document.getElementById("gen-beds").value) || 0,
        load_percentage: parseInt(document.getElementById("load-pct").value) || 50,
        doctors_on_duty: doctorsList
    };

    try {
        const resp = await fetch(`/api/hospitals/${currentHospital.id}/status`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updates)
        });

        const data = await resp.json();
        if (resp.ok) {
            showFeedback("✅ Status updated successfully!", "success");
        } else {
            showFeedback(`❌ ${data.error || "Update failed"}`, "error");
        }
    } catch (err) {
        showFeedback("❌ Network error. Please try again.", "error");
    }
}

function showFeedback(msg, type) {
    const el = document.getElementById("save-feedback");
    el.textContent = msg;
    el.className = `feedback ${type}`;
    el.classList.remove("hidden");
    setTimeout(() => el.classList.add("hidden"), 4000);
}

function hideFeedback() {
    document.getElementById("save-feedback").classList.add("hidden");
}

// ─── WebSocket ──────────────────────────────────
function initWebSocket() {
    const socket = io();

    socket.on("connect", () => {
        console.log("🔌 Connected to server");
    });

    socket.on("new_sos", (data) => {
        showSOSAlert(data);
        addFeedItem(data);
    });

    socket.on("hospital_updated", (data) => {
        addFeedItem({
            emergency_type: "update",
            best_hospital: data.hospital_name,
            eta_minutes: null,
            timestamp: data.timestamp,
            severity: "info"
        });
    });
}

// ─── SOS Alert Banner ───────────────────────────
function showSOSAlert(data) {
    const banner = document.getElementById("sos-alert-banner");
    document.getElementById("alert-title").textContent = 
        `🚨 ${data.emergency_type.toUpperCase()} Emergency — ${data.severity}`;
    document.getElementById("alert-detail").textContent = 
        `Best match: ${data.best_hospital} | ETA: ${data.eta_minutes} min`;

    banner.classList.remove("hidden");

    // Play alert sound (browser API)
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 800;
        gain.gain.value = 0.3;
        osc.start();
        setTimeout(() => { osc.frequency.value = 600; }, 200);
        setTimeout(() => { osc.stop(); ctx.close(); }, 500);
    } catch(e) { /* Audio not supported */ }

    // Auto-dismiss after 15 seconds
    setTimeout(dismissAlert, 15000);
}

function dismissAlert() {
    document.getElementById("sos-alert-banner").classList.add("hidden");
}

// ─── SOS Feed ───────────────────────────────────
function addFeedItem(data) {
    const feed = document.getElementById("sos-feed");
    const empty = feed.querySelector(".feed-empty");
    if (empty) empty.remove();

    const typeEmojis = {
        accident: "🚗", cardiac: "❤️", trauma: "🩹",
        maternity: "🤰", burns: "🔥", neuro: "🧠",
        general: "🏥", update: "📝"
    };

    const emoji = typeEmojis[data.emergency_type] || "🚨";
    const time = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : "now";

    const item = document.createElement("div");
    item.className = "feed-item";
    item.innerHTML = `
        <span class="feed-icon">${emoji}</span>
        <div class="feed-info">
            <div class="title">${data.emergency_type.toUpperCase()} ${data.severity ? `(${data.severity})` : ""}</div>
            <div class="detail">${data.best_hospital}${data.eta_minutes ? ` • ETA: ${data.eta_minutes} min` : ""}</div>
        </div>
        <span class="feed-time">${time}</span>
    `;

    feed.insertBefore(item, feed.firstChild);
}
