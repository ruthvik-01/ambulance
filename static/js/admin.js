/**
 * 🔧 Admin Dashboard Module
 * Firebase auth, live requests, driver fleet, event feed,
 * hospital management, manual reassignment. Socket.IO for real-time.
 */

let socket = null;
let adminReady = false;
let currentFilter = 'active';

// ─── Init ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Check if Firebase is configured
    const hasFirebase = typeof firebase !== 'undefined' && firebase.auth &&
        FIREBASE_CONFIG.apiKey && FIREBASE_CONFIG.apiKey !== 'None' && FIREBASE_CONFIG.apiKey !== '';

    if (hasFirebase) {
        firebase.auth().onAuthStateChanged(user => {
            if (user) {
                showDashboard();
            } else {
                showLoginSection();
            }
        });
    } else {
        // No Firebase — go straight to dashboard (demo mode)
        showDashboard();
    }
});

function showLoginSection() {
    document.getElementById('admin-login-section').classList.remove('hidden');
    document.getElementById('admin-dashboard').classList.add('hidden');
}

function showDashboard() {
    document.getElementById('admin-login-section').classList.add('hidden');
    document.getElementById('admin-dashboard').classList.remove('hidden');
    if (!adminReady) {
        adminReady = true;
        initSocket();
        loadAll();
    }
}

async function adminLogin() {
    const email = document.getElementById('admin-email').value.trim();
    const pass = document.getElementById('admin-password').value;
    const fb = document.getElementById('admin-feedback');

    if (!email || !pass) {
        showAdminFeedback('Please enter email and password', 'error');
        return;
    }

    try {
        if (typeof firebase !== 'undefined' && firebase.auth) {
            await firebase.auth().signInWithEmailAndPassword(email, pass);
            showDashboard();
        } else {
            showAdminFeedback('Firebase not configured. Use Demo mode.', 'error');
        }
    } catch (e) {
        showAdminFeedback(e.message || 'Login failed', 'error');
    }
}

function skipAdminAuth() {
    showDashboard();
}

function adminLogout() {
    if (typeof firebase !== 'undefined' && firebase.auth) {
        firebase.auth().signOut().catch(() => {});
    }
    adminReady = false;
    showLoginSection();
}

function showAdminFeedback(msg, type) {
    const el = document.getElementById('admin-feedback');
    el.textContent = msg;
    el.className = `feedback ${type}`;
    el.classList.remove('hidden');
}

// ─── Socket.IO ───────────────────────────────────
function initSocket() {
    socket = io();
    socket.on('connect', () => {
        document.getElementById('connection-badge').textContent = '● Live';
        document.getElementById('connection-badge').className = 'driver-status-badge available';
    });
    socket.on('disconnect', () => {
        document.getElementById('connection-badge').textContent = '● Offline';
        document.getElementById('connection-badge').className = 'driver-status-badge busy';
    });

    // Real-time events
    socket.on('new_sos', onNewSOS);
    socket.on('driver_assignment', () => refreshAfterDelay());
    socket.on('driver_accepted', () => refreshAfterDelay());
    socket.on('status_changed', () => refreshAfterDelay());
    socket.on('trip_completed', () => refreshAfterDelay());
    socket.on('driver_reassigned', () => refreshAfterDelay());
    socket.on('location_update', onLiveLocationUpdate);
}

function refreshAfterDelay() {
    setTimeout(() => {
        loadRequests();
        loadStats();
        loadEvents();
    }, 500);
}

function onNewSOS(data) {
    // Show alert banner
    const banner = document.getElementById('sos-alert-banner');
    document.getElementById('alert-sos-detail').textContent =
        `${(data.emergency_type || 'General').toUpperCase()} · ${data.best_hospital || ''} · #${data.sos_id}`;
    banner.classList.remove('hidden');

    // Auto-dismiss after 10s
    setTimeout(() => banner.classList.add('hidden'), 10000);

    // Play sound (if available)
    try {
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1');
        audio.volume = 0.3;
        audio.play().catch(() => {});
    } catch (e) { /* ignore */ }

    refreshAfterDelay();
}

function onLiveLocationUpdate(data) {
    // Could update driver markers on a map — for now refresh drivers tab if active
    // We'll update the driver status indicator
}

function dismissAlert() {
    document.getElementById('sos-alert-banner').classList.add('hidden');
}

// ─── Data Loading ────────────────────────────────
function loadAll() {
    loadStats();
    loadRequests();
    loadDrivers();
    loadEvents();
    loadHospitals();
}

async function loadStats() {
    try {
        const [reqRes, ambRes, hospRes] = await Promise.all([
            fetch('/api/admin/requests'),
            fetch('/api/ambulances'),
            fetch('/api/hospitals')
        ]);
        const reqData = await reqRes.json();
        const ambData = await ambRes.json();
        const hospData = await hospRes.json();

        const reqs = reqData.requests || [];
        const active = reqs.filter(r => !['completed', 'cancelled'].includes(r.status));
        const completed = reqs.filter(r => r.status === 'completed');

        document.getElementById('stat-active').textContent = active.length;
        document.getElementById('stat-completed').textContent = completed.length;
        document.getElementById('stat-drivers').textContent = (ambData.ambulances || []).length;
        document.getElementById('stat-hospitals').textContent = (hospData.hospitals || []).length;
    } catch (e) {
        console.error('Stats load failed:', e);
    }
}

async function loadRequests() {
    try {
        const res = await fetch(`/api/admin/requests?tab=${currentFilter}`);
        const data = await res.json();
        const list = document.getElementById('requests-list');

        if (!data.requests || data.requests.length === 0) {
            list.innerHTML = '<div class="loading-text">No requests found</div>';
            return;
        }

        list.innerHTML = data.requests.map(r => {
            const statusClass = r.status || 'pending';
            const driverInfo = r.driver
                ? `${r.driver.driver_name} (${r.driver.vehicle_number})`
                : 'Unassigned';
            const time = r.created_at ? new Date(r.created_at).toLocaleString() : '—';

            return `
            <div class="request-card">
                <div class="request-card-header">
                    <div>
                        <span class="request-id">SOS #${r.id}</span>
                        <span class="admin-card-meta" style="margin-left:8px;">${time}</span>
                    </div>
                    <span class="status-pill ${statusClass}">${statusClass}</span>
                </div>
                <div class="request-details">
                    <div class="req-detail-item">
                        <span class="req-detail-label">Type</span>
                        <span class="req-detail-value">${(r.emergency_type || 'general').toUpperCase()}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Severity</span>
                        <span class="req-detail-value">${(r.severity || 'medium').toUpperCase()}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Driver</span>
                        <span class="req-detail-value">${driverInfo}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Hospital</span>
                        <span class="req-detail-value">${r.hospital_name || '—'}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Location</span>
                        <span class="req-detail-value">${r.latitude ? `${parseFloat(r.latitude).toFixed(4)}, ${parseFloat(r.longitude).toFixed(4)}` : '—'}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Actions</span>
                        <span class="req-detail-value">
                            ${['assigned', 'accepted', 'enroute', 'pending'].includes(r.status) ?
                                `<button class="btn btn-sm btn-secondary" onclick="showReassignFor(${r.id})">🔄 Reassign</button>` : '—'}
                        </span>
                    </div>
                </div>
            </div>`;
        }).join('');

        // Populate reassign dropdown
        populateReassignDropdown(data.requests);
    } catch (e) {
        console.error('Requests load failed:', e);
    }
}

function filterRequests(tab) {
    currentFilter = tab;
    document.getElementById('filter-all').className = `btn btn-sm ${tab === 'all' ? 'btn-primary' : 'btn-secondary'}`;
    document.getElementById('filter-active').className = `btn btn-sm ${tab === 'active' ? 'btn-primary' : 'btn-secondary'}`;
    loadRequests();
}

async function loadDrivers() {
    try {
        const res = await fetch('/api/ambulances');
        const data = await res.json();
        const list = document.getElementById('drivers-list');

        if (!data.ambulances || data.ambulances.length === 0) {
            list.innerHTML = '<div class="loading-text">No drivers registered</div>';
            return;
        }

        list.innerHTML = data.ambulances.map(a => {
            const statusBadge = a.status === 'available'
                ? '<span class="status-pill completed">Available</span>'
                : '<span class="status-pill assigned">Busy</span>';
            return `
            <div class="admin-card">
                <div class="admin-card-header">
                    <div>
                        <div class="admin-card-title">🚑 ${a.driver_name}</div>
                        <div class="admin-card-meta">${a.vehicle_number} · ${a.driver_phone || ''}</div>
                    </div>
                    ${statusBadge}
                </div>
                <div class="request-details" style="grid-template-columns:1fr 1fr;">
                    <div class="req-detail-item">
                        <span class="req-detail-label">Location</span>
                        <span class="req-detail-value">${a.latitude ? `${parseFloat(a.latitude).toFixed(4)}, ${parseFloat(a.longitude).toFixed(4)}` : '—'}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Firebase</span>
                        <span class="req-detail-value">${a.firebase_uid ? '✅ Linked' : '—'}</span>
                    </div>
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('Drivers load failed:', e);
    }
}

async function loadEvents() {
    try {
        const res = await fetch('/api/admin/events?limit=30');
        const data = await res.json();
        const feed = document.getElementById('events-feed');

        if (!data.events || data.events.length === 0) {
            feed.innerHTML = '<div class="feed-empty">No events yet</div>';
            return;
        }

        const icons = {
            request_created: '📝', ambulance_assigned: '🚑', driver_accepted: '✅',
            status_enroute: '🏃', status_arrived: '📍', trip_completed: '🏁',
            driver_reassigned: '🔄', admin_reassigned: '🔧'
        };

        feed.innerHTML = data.events.map(e => {
            const t = new Date(e.created_at).toLocaleString();
            const icon = icons[e.event_type] || '📋';
            return `
            <div class="feed-item">
                <span class="feed-icon">${icon}</span>
                <div class="feed-info">
                    <div class="title">${e.event_type.replace(/_/g, ' ').toUpperCase()}</div>
                    <div class="detail">SOS #${e.sos_id}${e.ambulance_id ? ` · Amb #${e.ambulance_id}` : ''}${e.details ? ` · ${e.details}` : ''}</div>
                </div>
                <span class="feed-time">${t}</span>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('Events load failed:', e);
    }
}

async function loadHospitals() {
    try {
        const res = await fetch('/api/hospitals');
        const data = await res.json();
        const list = document.getElementById('hospitals-list');

        if (!data.hospitals || data.hospitals.length === 0) {
            list.innerHTML = '<div class="loading-text">No hospitals</div>';
            return;
        }

        list.innerHTML = data.hospitals.map(h => `
            <div class="admin-card">
                <div class="admin-card-header">
                    <div>
                        <div class="admin-card-title">🏥 ${h.name}</div>
                        <div class="admin-card-meta">${h.address || ''} · ${h.phone || ''}</div>
                    </div>
                    <span class="status-pill completed">${h.status || 'active'}</span>
                </div>
                <div class="request-details">
                    <div class="req-detail-item">
                        <span class="req-detail-label">ICU Beds</span>
                        <span class="req-detail-value">${h.available_icu_beds || 0}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Total Beds</span>
                        <span class="req-detail-value">${h.total_beds || 0}</span>
                    </div>
                    <div class="req-detail-item">
                        <span class="req-detail-label">Specializations</span>
                        <span class="req-detail-value">${(h.specializations || []).join(', ') || '—'}</span>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Hospitals load failed:', e);
    }
}

// ─── Tabs ────────────────────────────────────────
function switchTab(tabName, btn) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Refresh data for the tab
    const refreshMap = { requests: loadRequests, drivers: loadDrivers, events: loadEvents, hospitals: loadHospitals };
    if (refreshMap[tabName]) refreshMap[tabName]();
}

// ─── Reassignment ────────────────────────────────
function populateReassignDropdown(requests) {
    const select = document.getElementById('reassign-sos');
    select.innerHTML = requests
        .filter(r => ['assigned', 'accepted', 'enroute', 'pending'].includes(r.status))
        .map(r => `<option value="${r.id}">SOS #${r.id} — ${(r.emergency_type || 'General').toUpperCase()}</option>`)
        .join('');

    // Load available ambulances
    fetch('/api/ambulances').then(r => r.json()).then(data => {
        const ambSelect = document.getElementById('reassign-amb');
        ambSelect.innerHTML = '<option value="">Auto (nearest available)</option>';
        (data.ambulances || []).forEach(a => {
            ambSelect.innerHTML += `<option value="${a.id}">${a.driver_name} — ${a.vehicle_number} (${a.status})</option>`;
        });
    });
}

function showReassignFor(sosId) {
    const form = document.getElementById('reassign-form');
    form.style.display = 'block';
    const select = document.getElementById('reassign-sos');
    select.value = sosId;
    form.scrollIntoView({ behavior: 'smooth' });
}

function hideReassign() {
    document.getElementById('reassign-form').style.display = 'none';
}

async function submitReassign() {
    const sosId = parseInt(document.getElementById('reassign-sos').value);
    const ambId = document.getElementById('reassign-amb').value;

    if (!sosId) {
        alert('Select a SOS request');
        return;
    }

    try {
        const body = { sos_id: sosId };
        if (ambId) body.ambulance_id = parseInt(ambId);

        const res = await fetch('/api/admin/reassign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        if (data.success) {
            hideReassign();
            loadRequests();
            loadEvents();
            alert(`✅ Reassigned to ${data.ambulance?.driver_name || 'nearest driver'}`);
        } else {
            alert('Error: ' + (data.error || 'Failed'));
        }
    } catch (e) {
        alert('Network error: ' + e.message);
    }
}
