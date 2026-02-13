/**
 * 🚑 Driver Module
 * Handles both login (driver_login.html) and dashboard (driver.html).
 * Firebase auth + fallback quick login. Socket.IO for real-time dispatch.
 * Location streaming via watchPosition.
 */

const IS_DASHBOARD = !!document.getElementById('driver-info-bar');
let currentAmbulance = null;
let currentSOS = null;
let watchId = null;
let locationInterval = null;

// ─── Login Page Logic ────────────────────────────
if (!IS_DASHBOARD) {
    document.addEventListener('DOMContentLoaded', () => {
        loadAmbulanceList();
    });
}

async function loadAmbulanceList() {
    try {
        const res = await fetch('/api/ambulances');
        const data = await res.json();
        const select = document.getElementById('ambulance-select');
        if (!select) return;
        (data.ambulances || []).forEach(a => {
            const opt = document.createElement('option');
            opt.value = a.id;
            opt.textContent = `${a.driver_name} — ${a.vehicle_number}`;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load ambulances:', e);
    }
}

async function loginDriver() {
    const email = document.getElementById('login-email').value.trim();
    const pass = document.getElementById('login-password').value;
    const fb = document.getElementById('login-feedback');

    if (!email || !pass) {
        showFeedback(fb, 'Please enter email and password', 'error');
        return;
    }

    try {
        if (typeof firebase !== 'undefined' && firebase.auth) {
            const cred = await firebase.auth().signInWithEmailAndPassword(email, pass);
            const token = await cred.user.getIdToken();
            // Login with token
            const res = await fetch('/api/driver/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({})
            });
            const data = await res.json();
            if (data.success && data.ambulance) {
                sessionStorage.setItem('ambulance', JSON.stringify(data.ambulance));
                sessionStorage.setItem('auth_token', token);
                window.location.href = '/driver/dashboard';
            } else if (data.uid) {
                // Need to select ambulance
                showFeedback(fb, 'Select an ambulance below and use Quick Login', 'error');
            } else {
                showFeedback(fb, data.error || 'Login failed', 'error');
            }
        } else {
            showFeedback(fb, 'Firebase not configured. Use Quick Login.', 'error');
        }
    } catch (e) {
        showFeedback(fb, e.message || 'Login failed', 'error');
    }
}

async function quickLogin() {
    const select = document.getElementById('ambulance-select');
    const ambId = select?.value;
    if (!ambId) {
        alert('Please select an ambulance');
        return;
    }

    try {
        const res = await fetch('/api/driver/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ambulance_id: parseInt(ambId) })
        });
        const data = await res.json();
        if (data.success && data.ambulance) {
            sessionStorage.setItem('ambulance', JSON.stringify(data.ambulance));
            window.location.href = '/driver/dashboard';
        } else {
            alert(data.error || 'Login failed');
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}

function showFeedback(el, msg, type) {
    el.textContent = msg;
    el.className = `feedback ${type}`;
    el.classList.remove('hidden');
}

// ─── Dashboard Logic ─────────────────────────────
if (IS_DASHBOARD) {
    document.addEventListener('DOMContentLoaded', initDashboard);
}

function initDashboard() {
    // Retrieve ambulance from session
    const stored = sessionStorage.getItem('ambulance');
    if (!stored) {
        window.location.href = '/driver';
        return;
    }

    currentAmbulance = JSON.parse(stored);
    document.getElementById('d-driver-name').textContent = currentAmbulance.driver_name;
    document.getElementById('d-vehicle-info').textContent =
        `${currentAmbulance.vehicle_number} · ${currentAmbulance.driver_phone || ''}`;

    // Connect socket
    const socket = io();
    window._socket = socket;

    socket.on('connect', () => console.log('Driver socket connected'));

    // Listen for assignment
    socket.on('driver_assignment', (data) => {
        if (data.ambulance_id === currentAmbulance.id) {
            showActiveRequest(data);
        }
    });

    socket.on('driver_reassigned', (data) => {
        // If we were reassigned away, go back to waiting
        if (data.sos_id === currentSOS?.sos_id && data.ambulance_id !== currentAmbulance.id) {
            currentSOS = null;
            showWaitingState();
        }
        // If reassigned TO us
        if (data.ambulance_id === currentAmbulance.id) {
            checkActiveRequest();
        }
    });

    // Start GPS streaming
    startLocationStreaming();

    // Check for existing active request
    checkActiveRequest();
}

async function checkActiveRequest() {
    if (!currentAmbulance) return;
    try {
        const res = await fetch(`/api/driver/${currentAmbulance.id}/active`);
        const data = await res.json();
        if (data.active && data.sos) {
            showActiveRequest({
                sos_id: data.sos.id,
                emergency_type: data.sos.emergency_type,
                severity: data.sos.severity,
                patient_notes: data.sos.patient_notes,
                patient_lat: data.sos.latitude || data.patient_location?.latitude,
                patient_lng: data.sos.longitude || data.patient_location?.longitude,
                hospital_name: data.hospital?.name || '—',
                hospital_lat: data.hospital?.latitude,
                hospital_lng: data.hospital?.longitude,
                distance_km: data.sos.distance_km,
                status: data.sos.status
            });
        } else {
            showWaitingState();
        }
    } catch (e) {
        console.error('Check active failed:', e);
        showWaitingState();
    }
}

function showActiveRequest(data) {
    currentSOS = data;
    document.getElementById('waiting-state').classList.add('hidden');
    document.getElementById('active-request').classList.remove('hidden');

    // Update badge
    const badge = document.getElementById('driver-badge');
    badge.textContent = 'On Duty';
    badge.className = 'driver-status-badge busy';

    // Fill in info
    document.getElementById('req-type').textContent = (data.emergency_type || 'general').toUpperCase();
    document.getElementById('req-severity').textContent = (data.severity || 'medium').toUpperCase();
    document.getElementById('req-location').textContent =
        data.patient_lat && data.patient_lng
            ? `${parseFloat(data.patient_lat).toFixed(4)}, ${parseFloat(data.patient_lng).toFixed(4)}`
            : '—';
    document.getElementById('req-distance').textContent =
        data.distance_km ? `${data.distance_km} km` : '—';
    document.getElementById('req-notes').textContent = data.patient_notes || 'No notes';
    document.getElementById('alert-detail').textContent =
        `${(data.emergency_type || 'General').toUpperCase()} · ${data.severity || 'Medium'}`;

    // Hospital
    document.getElementById('req-hospital').textContent = data.hospital_name || '—';
    document.getElementById('req-hospital-loc').textContent =
        data.hospital_lat && data.hospital_lng
            ? `${parseFloat(data.hospital_lat).toFixed(4)}, ${parseFloat(data.hospital_lng).toFixed(4)}`
            : '—';

    // Render action buttons based on status
    renderDriverActions(data.status || 'assigned');
}

function renderDriverActions(status) {
    const container = document.getElementById('driver-actions');
    const sosId = currentSOS?.sos_id;
    const ambId = currentAmbulance?.id;
    const patLat = currentSOS?.patient_lat;
    const patLng = currentSOS?.patient_lng;
    const hospLat = currentSOS?.hospital_lat;
    const hospLng = currentSOS?.hospital_lng;

    let html = '';

    if (status === 'assigned') {
        html = `
            <button class="driver-action-btn accept" onclick="driverAction('accept')">
                <span>✅</span> <strong>Accept Request</strong>
            </button>`;
    }

    if (status === 'accepted' || status === 'assigned') {
        if (status === 'accepted') {
            html += `
                <button class="driver-action-btn enroute" onclick="driverAction('enroute')">
                    <span>🏃</span> <strong>Start Trip — En Route</strong>
                </button>`;
        }
    }

    if (status === 'enroute' || status === 'accepted') {
        if (patLat && patLng) {
            html += `
                <a class="driver-action-btn nav-patient" href="https://www.google.com/maps/dir/?api=1&destination=${patLat},${patLng}" target="_blank">
                    <span>📍</span> <strong>Navigate to Patient</strong>
                </a>`;
        }
        if (status === 'enroute') {
            html += `
                <button class="driver-action-btn arrived-btn" onclick="driverAction('arrived')">
                    <span>📍</span> <strong>Mark Arrived</strong>
                </button>`;
        }
    }

    if (status === 'arrived') {
        if (hospLat && hospLng) {
            html += `
                <a class="driver-action-btn nav-hospital" href="https://www.google.com/maps/dir/?api=1&destination=${hospLat},${hospLng}" target="_blank">
                    <span>🏥</span> <strong>Navigate to Hospital</strong>
                </a>`;
        }
        html += `
            <button class="driver-action-btn complete" onclick="driverAction('complete')">
                <span>🏁</span> <strong>Complete Trip</strong>
            </button>`;
    }

    if (status === 'completed') {
        html = `
            <div class="glass-card" style="text-align:center;padding:24px;">
                <div style="font-size:48px;margin-bottom:12px;">🏁</div>
                <h3>Trip Completed!</h3>
                <p class="text-dim">Great job. You'll receive the next request automatically.</p>
                <button class="btn btn-primary mt-4" onclick="resetToWaiting()">Back to Waiting</button>
            </div>`;
    }

    container.innerHTML = html;
}

async function driverAction(action) {
    if (!currentAmbulance || !currentSOS) return;
    const ambId = currentAmbulance.id;
    const sosId = currentSOS.sos_id;

    const endpoints = {
        accept: `/api/driver/${ambId}/accept`,
        enroute: `/api/driver/${ambId}/enroute`,
        arrived: `/api/driver/${ambId}/arrived`,
        complete: `/api/driver/${ambId}/complete`
    };

    try {
        const res = await fetch(endpoints[action], {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sos_id: sosId })
        });
        const data = await res.json();
        if (data.success) {
            const nextStatus = { accept: 'accepted', enroute: 'enroute', arrived: 'arrived', complete: 'completed' };
            currentSOS.status = nextStatus[action];
            renderDriverActions(nextStatus[action]);

            if (action === 'complete') {
                setTimeout(() => resetToWaiting(), 3000);
            }
        } else {
            alert('Error: ' + (data.error || 'Failed'));
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}

function showWaitingState() {
    document.getElementById('waiting-state').classList.remove('hidden');
    document.getElementById('active-request').classList.add('hidden');
    const badge = document.getElementById('driver-badge');
    badge.textContent = 'Available';
    badge.className = 'driver-status-badge available';
}

function resetToWaiting() {
    currentSOS = null;
    showWaitingState();
    checkActiveRequest();
}

// ─── Location Streaming ──────────────────────────
function startLocationStreaming() {
    if (!navigator.geolocation || !currentAmbulance) return;

    watchId = navigator.geolocation.watchPosition(
        pos => {
            sendLocation(pos.coords.latitude, pos.coords.longitude);
        },
        err => console.warn('GPS watch error:', err.message),
        { enableHighAccuracy: true, maximumAge: 3000 }
    );

    // Also send periodically
    locationInterval = setInterval(() => {
        navigator.geolocation.getCurrentPosition(
            pos => sendLocation(pos.coords.latitude, pos.coords.longitude),
            () => {},
            { enableHighAccuracy: true, maximumAge: 5000 }
        );
    }, 5000);
}

async function sendLocation(lat, lng) {
    if (!currentAmbulance) return;
    try {
        await fetch(`/api/driver/${currentAmbulance.id}/location`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latitude: lat, longitude: lng })
        });
    } catch (e) { /* ignore */ }
}

function logout() {
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    if (locationInterval) clearInterval(locationInterval);
    sessionStorage.removeItem('ambulance');
    sessionStorage.removeItem('auth_token');
    if (typeof firebase !== 'undefined' && firebase.auth) {
        firebase.auth().signOut().catch(() => {});
    }
    window.location.href = '/driver';
}
