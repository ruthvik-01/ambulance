/**
 * 🏥 Results Module — Display scored hospitals & dispatch ambulance
 * SOS_ID is injected from template.
 */

let sosData = null;

async function loadResults() {
    try {
        const res = await fetch(`/api/sos/${SOS_ID}`);
        const sos = await res.json();
        if (!res.ok) {
            document.getElementById('best-card').innerHTML =
                `<div class="glass-card" style="text-align:center;padding:30px;"><p style="color:var(--danger);">Error: ${sos.error || 'Failed to load'}</p></div>`;
            return;
        }
        sosData = sos;

        // Emergency badge
        const badge = document.getElementById('emergency-badge');
        badge.textContent = (sos.emergency_type || 'general').toUpperCase();

        // Load scored results from the original SOS submission stored in session/localStorage
        // or fetch fresh from the hospital scoring
        loadHospitalScores();
    } catch (e) {
        document.getElementById('best-card').innerHTML =
            `<div class="glass-card" style="text-align:center;padding:30px;"><p style="color:var(--danger);">Network error</p></div>`;
    }
}

async function loadHospitalScores() {
    // Check sessionStorage for cached results from SOS submission
    let cached = sessionStorage.getItem(`sos_results_${SOS_ID}`);
    if (cached) {
        try {
            renderResults(JSON.parse(cached));
            return;
        } catch (e) { /* ignore, fetch fresh */ }
    }

    // Re-score by re-fetching (the SOS data has selected_hospital etc.)
    // We need to trigger a fresh scoring call
    try {
        const sos = sosData;
        const lat = sos.latitude;
        const lng = sos.longitude;
        const etype = sos.emergency_type || 'general';

        // Get hospital results via a mini SOS call (GET won't work — use scoring endpoint)
        // Actually, the SOS already has hospital info stored. Let's build from SOS data.
        // Fetch all hospitals and the selected one
        const [hospRes, allRes] = await Promise.all([
            sos.selected_hospital_id ? fetch(`/api/hospitals/${sos.selected_hospital_id}`) : null,
            fetch('/api/hospitals')
        ]);

        const allData = await allRes.json();
        const hospitals = allData.hospitals || [];

        // Build a simple display — the best hospital is the selected one
        if (sos.selected_hospital_id) {
            const bestHosp = hospitals.find(h => h.id === sos.selected_hospital_id);
            const backupHosp = sos.backup_hospital_id ? hospitals.find(h => h.id === sos.backup_hospital_id) : null;

            // Sort remaining by distance (we don't have scores cached, so show what we can)
            const others = hospitals.filter(h => h.id !== sos.selected_hospital_id && (!backupHosp || h.id !== backupHosp.id));

            renderResults({
                best_hospital: bestHosp ? formatHospitalForDisplay(bestHosp, lat, lng) : null,
                backup_hospital: backupHosp ? formatHospitalForDisplay(backupHosp, lat, lng) : null,
                all_hospitals: others.map(h => formatHospitalForDisplay(h, lat, lng)).slice(0, 5)
            });
        } else {
            document.getElementById('best-card').innerHTML =
                `<div class="glass-card" style="text-align:center;padding:30px;"><p class="text-dim">No hospital selected yet.</p></div>`;
        }
    } catch (e) {
        console.error('Failed to load hospital scores:', e);
    }
}

function formatHospitalForDisplay(h, userLat, userLng) {
    const dist = haversine(userLat, userLng, h.latitude, h.longitude);
    const eta = Math.round(dist / 0.5); // rough ETA: 30km/h average
    return {
        id: h.id,
        name: h.name,
        address: h.address || '',
        phone: h.phone || '',
        latitude: h.latitude,
        longitude: h.longitude,
        distance_km: Math.round(dist * 10) / 10,
        eta_minutes: eta,
        readiness_score: h.readiness_score || 0,
        facilities: h.facilities || [],
        specializations: h.specializations || [],
        available_icu_beds: h.available_icu_beds || 0,
        navigation_url: `https://www.google.com/maps/dir/?api=1&destination=${h.latitude},${h.longitude}`
    };
}

function haversine(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const toRad = x => x * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.asin(Math.sqrt(a));
}

function renderResults(data) {
    // Best Hospital Card
    if (data.best_hospital) {
        const b = data.best_hospital;
        document.getElementById('best-card').innerHTML = buildHospitalCard(b, 'best');
        
        // Navigation
        const navSection = document.getElementById('best-nav-section');
        navSection.classList.remove('hidden');
        document.getElementById('select-best-btn').href = '#';
        document.getElementById('select-best-btn').onclick = (e) => {
            e.preventDefault();
            dispatchAmbulance(b.id);
        };

        // Score bars (use available data)
        renderScoreBars(b);
    }

    // Backup
    if (data.backup_hospital) {
        const bk = data.backup_hospital;
        const backupDiv = document.getElementById('backup-card');
        backupDiv.classList.remove('hidden');
        backupDiv.innerHTML = `
            <div style="margin-top:20px;">
                <h3 style="font-size:14px;color:var(--text-secondary);margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px;">Backup Hospital</h3>
                ${buildHospitalCard(bk, 'backup')}
                <div class="nav-section" style="margin-top:12px;">
                    <a href="#" class="navigate-button" style="background:linear-gradient(135deg, var(--warning), var(--warning-dark));font-size:14px;padding:14px;box-shadow:none;" onclick="event.preventDefault(); dispatchAmbulance(${bk.id})">
                        🚑 Dispatch to Backup
                    </a>
                </div>
            </div>`;
    }

    // All hospitals
    if (data.all_hospitals && data.all_hospitals.length > 0) {
        const allSection = document.getElementById('all-section');
        allSection.classList.remove('hidden');
        const listDiv = document.getElementById('all-hospitals-list');
        listDiv.innerHTML = data.all_hospitals.map(h => `
            <div class="all-hospital-item">
                <div class="all-hospital-info">
                    <div class="name">${h.name}</div>
                    <div class="meta">${h.distance_km} km · ETA ${h.eta_minutes} min · ${h.available_icu_beds} ICU beds</div>
                </div>
                <span class="all-hospital-score">${h.readiness_score || '—'}</span>
                <a href="#" class="all-hospital-nav" onclick="event.preventDefault(); dispatchAmbulance(${h.id})">Dispatch</a>
            </div>
        `).join('');
    }
}

function buildHospitalCard(h, type) {
    const badgeClass = type === 'best' ? 'badge-best' : 'badge-backup';
    const badgeText = type === 'best' ? '⭐ BEST MATCH' : '🔄 BACKUP';
    const cardClass = type === 'best' ? 'best' : 'backup';

    const facilitiesTags = (h.facilities || []).map(f =>
        `<span class="tag">${f}</span>`
    ).join('');

    const specTags = (h.specializations || []).map(s =>
        `<span class="tag match">${s}</span>`
    ).join('');

    return `
    <div class="hospital-card ${cardClass}">
        <span class="card-badge ${badgeClass}">${badgeText}</span>
        <h2 class="card-hospital-name">${h.name}</h2>
        <p class="card-address">${h.address || 'Address not available'}</p>
        <div class="card-stats">
            <div class="stat-item">
                <div class="stat-value score">${h.readiness_score || '—'}</div>
                <div class="stat-label">Score</div>
            </div>
            <div class="stat-item">
                <div class="stat-value distance">${h.distance_km}</div>
                <div class="stat-label">km</div>
            </div>
            <div class="stat-item">
                <div class="stat-value eta">${h.eta_minutes}</div>
                <div class="stat-label">min ETA</div>
            </div>
        </div>
        ${facilitiesTags || specTags ? `<div class="card-tags">${facilitiesTags}${specTags}</div>` : ''}
        ${h.phone ? `<div class="card-phone">📞 <a href="tel:${h.phone}">${h.phone}</a></div>` : ''}
    </div>`;
}

function renderScoreBars(h) {
    const section = document.getElementById('score-section');
    const bars = document.getElementById('score-bars');
    if (!h.score_breakdown) {
        section.classList.add('hidden');
        return;
    }
    section.classList.remove('hidden');
    const bd = h.score_breakdown;
    const items = [
        { label: 'Facility', value: bd.facility_score || 0, max: 30, cls: 'facility' },
        { label: 'Distance', value: bd.distance_score || 0, max: 25, cls: 'distance' },
        { label: 'Bed Avail.', value: bd.bed_score || 0, max: 20, cls: 'bed' },
        { label: 'Specialist', value: bd.specialist_score || 0, max: 15, cls: 'specialist' },
        { label: 'Prediction', value: bd.prediction_score || 0, max: 5, cls: 'prediction' },
        { label: 'History', value: bd.history_score || 0, max: 5, cls: 'history' }
    ];

    bars.innerHTML = items.map(i => {
        const pct = Math.min(100, (i.value / i.max) * 100);
        return `
        <div class="score-row">
            <span class="score-label">${i.label}</span>
            <div class="score-bar-bg">
                <div class="score-bar-fill ${i.cls}" style="width: ${pct}%"></div>
            </div>
            <span class="score-value">${i.value.toFixed(1)}</span>
        </div>`;
    }).join('');
}

// ─── Dispatch Ambulance ──────────────────────────
async function dispatchAmbulance(hospitalId) {
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = 'Dispatching…';
    btn.style.pointerEvents = 'none';

    try {
        const res = await fetch('/api/ambulance/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sos_id: SOS_ID, hospital_id: hospitalId })
        });
        const data = await res.json();
        if (res.ok && data.success) {
            // Navigate to ambulance tracking page
            window.location.href = `/ambulance/${SOS_ID}/${hospitalId}`;
        } else {
            alert('Error: ' + (data.error || 'Failed to dispatch'));
            btn.textContent = originalText;
            btn.style.pointerEvents = '';
        }
    } catch (e) {
        alert('Network error: ' + e.message);
        btn.textContent = originalText;
        btn.style.pointerEvents = '';
    }
}

// Cache SOS results from initial POST for re-display
window.addEventListener('beforeunload', () => {
    // Noop — caching handled in SOS response redirect
});

// ─── Init ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadResults);

// Store SOS results on page load if passed via query params
(function cacheFromSOS() {
    // This runs on the SOS submission page before redirect — we intercept in sos.js
})();
