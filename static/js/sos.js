/**
 * 🚨 SOS Page — Main emergency trigger logic
 * Handles GPS acquisition, emergency type selection, and SOS submission.
 */

// ─── State ──────────────────────────────────────
let userLat = null;
let userLng = null;
let gpsReady = false;
let selectedType = "accident";
let selectedSeverity = "medium";

// ─── GPS ────────────────────────────────────────
function initGPS() {
    const statusDot = document.querySelector(".gps-dot");
    const statusText = document.getElementById("gps-text");

    if (!navigator.geolocation) {
        statusDot.classList.add("error");
        statusText.textContent = "GPS not supported. Enter location manually.";
        showGPSModal();
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            userLat = pos.coords.latitude;
            userLng = pos.coords.longitude;
            gpsReady = true;
            statusDot.classList.add("active");
            statusText.textContent = `📍 ${userLat.toFixed(4)}, ${userLng.toFixed(4)}`;
            document.getElementById("sos-btn").disabled = false;
        },
        (err) => {
            console.warn("GPS error:", err.message);
            statusDot.classList.add("error");
            statusText.textContent = "GPS unavailable. Tap to enter manually.";
            document.querySelector(".gps-status").style.cursor = "pointer";
            document.querySelector(".gps-status").onclick = showGPSModal;
            // Enable SOS with default location for demo
            enableDemoMode();
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
}

function enableDemoMode() {
    // Default to Coimbatore center for demo purposes
    userLat = 11.0168;
    userLng = 76.9558;
    gpsReady = true;
    document.getElementById("sos-btn").disabled = false;
    const statusText = document.getElementById("gps-text");
    statusText.textContent = `📍 Demo: ${userLat}, ${userLng} (tap to change)`;
    document.querySelector(".gps-dot").classList.add("active");
}

function showGPSModal() {
    document.getElementById("gps-modal").classList.remove("hidden");
}

function retryGPS() {
    document.getElementById("gps-modal").classList.add("hidden");
    initGPS();
}

function useManualCoords() {
    const lat = parseFloat(document.getElementById("manual-lat").value);
    const lng = parseFloat(document.getElementById("manual-lng").value);

    if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
        alert("Please enter valid coordinates.\nLatitude: -90 to 90\nLongitude: -180 to 180");
        return;
    }

    userLat = lat;
    userLng = lng;
    gpsReady = true;

    document.getElementById("gps-modal").classList.add("hidden");
    document.querySelector(".gps-dot").classList.add("active");
    document.getElementById("gps-text").textContent = `📍 ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    document.getElementById("sos-btn").disabled = false;
}

// ─── Emergency Type Selection ───────────────────
function selectType(el) {
    document.querySelectorAll(".type-card").forEach(c => c.classList.remove("active"));
    el.classList.add("active");
    selectedType = el.dataset.type;
}

// ─── Severity Selection ─────────────────────────
function selectSeverity(el) {
    document.querySelectorAll(".severity-btn").forEach(b => b.classList.remove("active"));
    el.classList.add("active");
    selectedSeverity = el.dataset.severity;
}

// ─── SOS Trigger ────────────────────────────────
async function triggerSOS() {
    if (!gpsReady) {
        showGPSModal();
        return;
    }

    // Show loading
    const overlay = document.getElementById("loading-overlay");
    overlay.classList.remove("hidden");

    const loadingText = document.getElementById("loading-text");
    const messages = [
        "Scanning nearby hospitals...",
        "Checking ICU bed availability...",
        "Matching specialists to emergency type...",
        "Calculating readiness scores...",
        "Selecting the best hospital..."
    ];

    let msgIndex = 0;
    const msgInterval = setInterval(() => {
        loadingText.textContent = messages[msgIndex % messages.length];
        msgIndex++;
    }, 800);

    const notes = document.getElementById("patient-notes")?.value || "";

    try {
        const response = await fetch("/api/sos", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                latitude: userLat,
                longitude: userLng,
                emergency_type: selectedType,
                severity: selectedSeverity,
                patient_notes: notes
            })
        });

        const data = await response.json();
        clearInterval(msgInterval);

        if (response.ok && data.success) {
            // Store results and redirect
            sessionStorage.setItem("sos_result", JSON.stringify(data));
            window.location.href = `/results/${data.sos_id}`;
        } else {
            overlay.classList.add("hidden");
            alert(`Error: ${data.error || "Something went wrong"}`);
        }
    } catch (err) {
        clearInterval(msgInterval);
        overlay.classList.add("hidden");
        console.error("SOS error:", err);
        alert("Network error. Please check your connection and try again.");
    }
}

// ─── Init ───────────────────────────────────────
document.addEventListener("DOMContentLoaded", initGPS);
