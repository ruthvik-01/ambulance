/**
 * 🚑 SOS Module — GPS + Emergency Type + SOS Submission
 * Public (no auth). Sends SOS request with GPS coords & emergency type.
 */

let userLat = null;
let userLng = null;
let selectedType = 'cardiac';
let selectedSeverity = 'medium';
let gpsReady = false;

// ─── GPS ─────────────────────────────────────────
function initGPS() {
    if (!navigator.geolocation) {
        setGPSStatus('error', 'Geolocation not supported');
        showManualModal();
        return;
    }
    navigator.geolocation.getCurrentPosition(
        pos => {
            userLat = pos.coords.latitude;
            userLng = pos.coords.longitude;
            gpsReady = true;
            setGPSStatus('active', `📍 ${userLat.toFixed(5)}, ${userLng.toFixed(5)}`);
            document.getElementById('sos-btn').disabled = false;
            document.getElementById('sos-hint').textContent = 'Tap SOS to send emergency request';
        },
        err => {
            console.warn('GPS Error:', err.message);
            setGPSStatus('error', 'Location access denied');
            document.getElementById('sos-hint').textContent = 'Enable location or enter manually';
            showManualModal();
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
}

function setGPSStatus(state, text) {
    const dot = document.getElementById('gps-dot');
    const txt = document.getElementById('gps-text');
    dot.className = 'gps-dot ' + state;
    txt.textContent = text;
}

function retryGPS() {
    document.getElementById('manual-modal').classList.add('hidden');
    setGPSStatus('', 'Retrying GPS…');
    initGPS();
}

function showManualModal() {
    document.getElementById('manual-modal').classList.remove('hidden');
}

function useManualCoords() {
    const lat = parseFloat(document.getElementById('manual-lat').value);
    const lng = parseFloat(document.getElementById('manual-lng').value);
    if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
        alert('Please enter valid coordinates (lat: -90 to 90, lng: -180 to 180)');
        return;
    }
    userLat = lat;
    userLng = lng;
    gpsReady = true;
    document.getElementById('manual-modal').classList.add('hidden');
    setGPSStatus('active', `📍 ${lat.toFixed(5)}, ${lng.toFixed(5)} (manual)`);
    document.getElementById('sos-btn').disabled = false;
    document.getElementById('sos-hint').textContent = 'Tap SOS to send emergency request';
}

// ─── Emergency Type ──────────────────────────────
function selectType(el) {
    document.querySelectorAll('.type-card').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    selectedType = el.dataset.type;
}

// ─── Severity ────────────────────────────────────
function selectSeverity(el) {
    document.querySelectorAll('.severity-btn').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    selectedSeverity = el.dataset.severity;
}

// ─── Send SOS ────────────────────────────────────
async function sendSOS() {
    if (!gpsReady || userLat === null) {
        alert('GPS not ready. Please wait or enter coordinates manually.');
        return;
    }

    const btn = document.getElementById('sos-btn');
    btn.disabled = true;

    // Show loading
    document.getElementById('loading').classList.remove('hidden');

    const notes = document.getElementById('patient-notes')?.value || '';

    try {
        const res = await fetch('/api/sos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                latitude: userLat,
                longitude: userLng,
                emergency_type: selectedType,
                severity: selectedSeverity,
                patient_notes: notes
            })
        });

        const data = await res.json();

        if (res.ok && data.success) {
            // Redirect to results page
            window.location.href = `/results/${data.sos_id}`;
        } else {
            document.getElementById('loading').classList.add('hidden');
            btn.disabled = false;
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        document.getElementById('loading').classList.add('hidden');
        btn.disabled = false;
        alert('Network error: ' + e.message);
    }
}

// ─── Init ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', initGPS);
