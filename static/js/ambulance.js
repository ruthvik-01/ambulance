/**
 * 🚑 Ambulance Tracking Module
 * Real-time driver tracking via Socket.IO, status timeline,
 * driver info card, ETA, event log.
 * SOS_ID & HOSPITAL_ID injected from template.
 */

const socket = io();
let ambulanceId = null;
let driverData = null;
let pollInterval = null;
let sosStatus = 'pending';

const STEPS = ['requested', 'assigned', 'accepted', 'enroute', 'arrived', 'completed'];

// ─── Init ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    socket.on('connect', () => console.log('Socket connected'));
    socket.emit('join_sos', { sos_id: SOS_ID });

    // Listen for real-time events
    socket.on('driver_assignment', onDriverAssigned);
    socket.on('driver_accepted', onDriverAccepted);
    socket.on('status_changed', onStatusChanged);
    socket.on('location_update', onLocationUpdate);
    socket.on('trip_completed', onTripCompleted);
    socket.on('driver_reassigned', onDriverReassigned);
    socket.on('no_driver_available', onNoDriver);

    // Load initial state
    loadSOSState();
    loadEvents();

    // Auto-trigger ambulance assignment if not yet done
    assignAmbulance();
});

// ─── Load Current State ──────────────────────────
async function loadSOSState() {
    try {
        const res = await fetch(`/api/sos/${SOS_ID}`);
        const sos = await res.json();
        if (!res.ok) return;

        sosStatus = sos.status || 'pending';
        updateTimeline(sosStatus);

        // If driver is assigned, show driver card
        if (sos.driver) {
            ambulanceId = sos.driver.id;
            showDriverCard(sos.driver);
            startLocationPoll();
        }

        // Show hospital info
        if (sos.hospital) {
            showHospitalCard(sos.hospital);
        } else if (HOSPITAL_ID) {
            loadHospitalInfo(HOSPITAL_ID);
        }

        updateStatusText(sosStatus);
    } catch (e) {
        console.error('Failed to load SOS state:', e);
    }
}

async function loadHospitalInfo(hid) {
    try {
        const res = await fetch(`/api/hospitals/${hid}`);
        const h = await res.json();
        if (res.ok) showHospitalCard(h);
    } catch (e) { /* ignore */ }
}

// ─── Assign Ambulance ────────────────────────────
async function assignAmbulance() {
    try {
        const checkRes = await fetch(`/api/sos/${SOS_ID}`);
        const checkData = await checkRes.json();
        if (checkData.assigned_ambulance_id) {
            // Already assigned
            return;
        }
    } catch (e) { /* continue to assign */ }

    try {
        const res = await fetch('/api/ambulance/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sos_id: SOS_ID, hospital_id: HOSPITAL_ID })
        });
        const data = await res.json();
        if (res.ok && data.success && data.ambulance) {
            ambulanceId = data.ambulance.id;
            onDriverAssigned({
                sos_id: SOS_ID,
                ambulance_id: data.ambulance.id,
                driver_name: data.ambulance.driver_name,
                driver_phone: data.ambulance.phone,
                vehicle_number: data.ambulance.vehicle_number,
                driver_lat: data.ambulance.latitude,
                driver_lng: data.ambulance.longitude,
                distance_km: data.ambulance.distance_km
            });
        } else if (!res.ok) {
            showWaiting('No Drivers Available', data.error || 'Please wait — a driver will be assigned shortly.');
        }
    } catch (e) {
        console.error('Assign failed:', e);
    }
}

// ─── Socket Event Handlers ───────────────────────
function onDriverAssigned(data) {
    if (data.sos_id !== SOS_ID) return;
    ambulanceId = data.ambulance_id;
    sosStatus = 'assigned';
    updateTimeline('assigned');
    updateStatusText('assigned');

    showDriverCard({
        id: data.ambulance_id,
        driver_name: data.driver_name,
        driver_phone: data.driver_phone,
        vehicle_number: data.vehicle_number,
        latitude: data.driver_lat,
        longitude: data.driver_lng,
        distance_km: data.distance_km
    });

    startLocationPoll();
    loadEvents();
}

function onDriverAccepted(data) {
    if (data.sos_id !== SOS_ID) return;
    sosStatus = 'accepted';
    updateTimeline('accepted');
    updateStatusText('accepted');

    const card = document.getElementById('waiting-card');
    if (card) {
        card.classList.add('accepted');
        card.querySelector('.waiting-pulse').textContent = '✅';
        card.querySelector('h3').textContent = 'Driver Accepted!';
        card.querySelector('p').textContent = 'The driver is preparing to come to you.';
    }
    loadEvents();
}

function onStatusChanged(data) {
    if (data.sos_id !== SOS_ID) return;
    sosStatus = data.status;
    updateTimeline(data.status);
    updateStatusText(data.status);
    loadEvents();
}

function onLocationUpdate(data) {
    if (data.ambulance_id !== ambulanceId) return;
    updateDriverLocation(data.latitude, data.longitude);
}

function onTripCompleted(data) {
    if (data.sos_id !== SOS_ID) return;
    sosStatus = 'completed';
    updateTimeline('completed');
    updateStatusText('completed');
    stopLocationPoll();
    loadEvents();
}

function onDriverReassigned(data) {
    if (data.sos_id !== SOS_ID) return;
    ambulanceId = data.ambulance_id;
    sosStatus = 'assigned';
    updateTimeline('assigned');
    updateStatusText('assigned');

    showDriverCard({
        id: data.ambulance_id,
        driver_name: data.driver_name,
        driver_phone: data.driver_phone,
        vehicle_number: data.vehicle_number,
        latitude: data.latitude,
        longitude: data.longitude
    });
    loadEvents();
}

function onNoDriver(data) {
    if (data.sos_id !== SOS_ID) return;
    showWaiting('No Drivers Available', 'All drivers are busy. We\'ll keep looking…');
}

// ─── Timeline ────────────────────────────────────
function updateTimeline(status) {
    const idx = STEPS.indexOf(status);
    if (idx === -1) return;

    STEPS.forEach((step, i) => {
        const el = document.getElementById(`step-${step}`);
        const line = document.getElementById(`line-${i}`);
        if (el) el.classList.toggle('active', i <= idx);
        if (line) line.classList.toggle('active', i <= idx);
    });

    // Progress bar
    const fill = document.getElementById('progress-fill');
    if (fill) {
        const pct = Math.min(100, ((idx) / (STEPS.length - 1)) * 100);
        fill.style.width = pct + '%';
    }
}

function updateStatusText(status) {
    const texts = {
        pending: '⏳ Waiting for ambulance assignment…',
        assigned: '🚑 Driver assigned — waiting for acceptance',
        accepted: '✅ Driver accepted — preparing to depart',
        enroute: '🏃 Ambulance is en route to you!',
        arrived: '📍 Ambulance has arrived!',
        completed: '🏁 Trip completed. Stay safe!'
    };
    document.getElementById('status-text').textContent = texts[status] || 'Processing…';
}

// ─── Driver Card ─────────────────────────────────
function showDriverCard(driver) {
    driverData = driver;
    document.getElementById('waiting-section').classList.add('hidden');
    const card = document.getElementById('driver-card');
    card.classList.remove('hidden');

    document.getElementById('driver-name').textContent = driver.driver_name || 'Driver';
    document.getElementById('driver-vehicle').textContent = driver.vehicle_number || '—';

    const callBtn = document.getElementById('driver-call');
    if (driver.driver_phone) {
        callBtn.href = `tel:${driver.driver_phone}`;
        callBtn.classList.remove('hidden');
    }

    // ETA estimation (rough: 30km/h average speed)
    if (driver.distance_km) {
        const etaMin = Math.max(1, Math.round(driver.distance_km / 0.5));
        document.getElementById('driver-eta').textContent = `~${etaMin} min`;
    }

    // Show actions
    document.getElementById('amb-actions').classList.remove('hidden');

    // Update navigation links
    if (driver.latitude && driver.longitude) {
        document.getElementById('nav-driver-btn').href =
            `https://www.google.com/maps?q=${driver.latitude},${driver.longitude}`;
    }
}

function showWaiting(title, msg) {
    const section = document.getElementById('waiting-section');
    section.classList.remove('hidden');
    document.getElementById('driver-card').classList.add('hidden');
    const card = document.getElementById('waiting-card');
    card.querySelector('h3').textContent = title;
    card.querySelector('p').textContent = msg;
}

function showHospitalCard(h) {
    const card = document.getElementById('hospital-card');
    card.classList.remove('hidden');

    document.getElementById('hosp-name').textContent = h.name || '—';
    document.getElementById('hosp-address').textContent = h.address || '—';
    document.getElementById('hosp-beds').textContent = h.available_icu_beds || '—';

    if (h.phone) {
        const link = document.getElementById('hosp-phone-link');
        link.href = `tel:${h.phone}`;
        link.textContent = h.phone;
    }

    // Navigation link
    const navBtn = document.getElementById('nav-hospital-btn');
    navBtn.href = `https://www.google.com/maps/dir/?api=1&destination=${h.latitude},${h.longitude}`;
}

// ─── Location Polling ────────────────────────────
function startLocationPoll() {
    if (pollInterval) return;
    pollInterval = setInterval(async () => {
        if (!ambulanceId) return;
        try {
            const res = await fetch(`/api/ambulance/${ambulanceId}/location`);
            const data = await res.json();
            if (res.ok) {
                updateDriverLocation(data.latitude, data.longitude);
            }
        } catch (e) { /* ignore */ }
    }, 5000);
}

function stopLocationPoll() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function updateDriverLocation(lat, lng) {
    const navBtn = document.getElementById('nav-driver-btn');
    if (navBtn) {
        navBtn.href = `https://www.google.com/maps?q=${lat},${lng}`;
    }
    // Update ETA if we have patient location from SOS
    if (driverData) {
        driverData.latitude = lat;
        driverData.longitude = lng;
    }
}

// ─── Event Log ───────────────────────────────────
async function loadEvents() {
    try {
        const res = await fetch(`/api/sos/${SOS_ID}/events`);
        const data = await res.json();
        if (!res.ok) return;

        const log = document.getElementById('event-log');
        if (!data.events || data.events.length === 0) {
            log.innerHTML = '<div class="feed-empty">No events yet</div>';
            return;
        }

        const icons = {
            request_created: '📝',
            ambulance_assigned: '🚑',
            driver_accepted: '✅',
            status_enroute: '🏃',
            status_arrived: '📍',
            trip_completed: '🏁',
            driver_reassigned: '🔄',
            admin_reassigned: '🔧'
        };

        log.innerHTML = data.events.map(e => {
            const t = new Date(e.created_at).toLocaleTimeString();
            const icon = icons[e.event_type] || '📋';
            return `
            <div class="feed-item">
                <span class="feed-icon">${icon}</span>
                <div class="feed-info">
                    <div class="title">${e.event_type.replace(/_/g, ' ').toUpperCase()}</div>
                    ${e.details ? `<div class="detail">${e.details}</div>` : ''}
                </div>
                <span class="feed-time">${t}</span>
            </div>`;
        }).join('');
    } catch (e) { /* ignore */ }
}
