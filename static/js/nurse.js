/**
 * Nurse Station: Vitals Triage, Bed Matrix & IPMO Medication Schedule
 */

let currentSelectedPatient = null;
let vitalsAuditLogs = [];

document.addEventListener("DOMContentLoaded", () => {
  loadBedMatrix();
  loadIpmoQueue();
  loadNurseAnalytics();
  loadRecentVitalsLogs();
  setupPatientAutocomplete();

  const vitalsForm = document.getElementById("vitalsForm");
  if (vitalsForm) {
    vitalsForm.addEventListener("submit", handleSaveVitals);
    setupRealtimeVitalsFeedback();
  }
});

function setupRealtimeVitalsFeedback() {
  const sysInput = document.getElementById("bpSystolic");
  const diaInput = document.getElementById("bpDiastolic");
  const spo2Input = document.getElementById("spo2Input");
  const tempInput = document.getElementById("tempInput");
  const feedbackBox = document.getElementById("vitalsFeedbackBox");

  function evaluate() {
    const sys = parseInt(sysInput?.value || 0, 10);
    const dia = parseInt(diaInput?.value || 0, 10);
    const spo2 = parseInt(spo2Input?.value || 100, 10);
    const temp = parseFloat(tempInput?.value || 98.6);

    const alerts = [];
    if (sys >= 140 || dia >= 90) alerts.push("High Blood Pressure (Hypertension)");
    if (sys > 0 && sys <= 90) alerts.push("Low Blood Pressure (Hypotension)");
    if (spo2 > 0 && spo2 < 94) alerts.push("Critical: Hypoxemia! Low Oxygen Saturation (<94%)");
    if (temp >= 99.5) alerts.push("Pyrexia (Fever detected)");

    if (alerts.length > 0) {
      feedbackBox.style.display = "block";
      feedbackBox.className = "card badge-danger";
      feedbackBox.innerHTML = `<strong>Clinical Alert:</strong><ul style="margin-left:1.5rem; margin-top:0.25rem;">${alerts.map(a => `<li>${a}</li>`).join("")}</ul>`;
    } else {
      feedbackBox.style.display = "none";
    }
  }

  [sysInput, diaInput, spo2Input, tempInput].forEach(el => el?.addEventListener("input", evaluate));
}

async function handleSaveVitals(e) {
  e.preventDefault();
  const form = e.target;
  const patientIdVal = document.getElementById("patientIdInput")?.value;
  const patientId = parseInt(patientIdVal, 10);
  
  if (!patientId || isNaN(patientId)) {
    showToast("Please search and select a patient from the dropdown list before saving.", "warning");
    const searchInput = document.getElementById("patientSearchInput");
    if (searchInput) searchInput.focus();
    return;
  }

  const saveBtn = document.getElementById("saveVitalsBtn");
  const origBtnContent = saveBtn ? saveBtn.innerHTML : "Save Vitals";
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span>Saving to Medical Record...</span>`;
  }

  const payload = {
    patient_id: patientId,
    temperature_f: parseFloat(form.tempInput.value) || null,
    blood_pressure_systolic: parseInt(form.bpSystolic.value, 10) || null,
    blood_pressure_diastolic: parseInt(form.bpDiastolic.value, 10) || null,
    heart_rate_bpm: parseInt(form.pulseInput.value, 10) || null,
    spo2_percent: parseInt(form.spo2Input.value, 10) || null,
    respiratory_rate: parseInt(form.respInput.value, 10) || null,
    weight_kg: parseFloat(form.weightInput.value) || null,
    height_cm: parseFloat(form.heightInput.value) || null,
    triage_notes: form.triageNotes.value ? form.triageNotes.value.trim() : null
  };

  try {
    const vitals = await apiFetch("/api/clinical/vitals", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    const patientName = currentSelectedPatient ? currentSelectedPatient.full_name : `Patient #${patientId}`;
    showToast(`Vitals successfully logged for ${patientName}! Calculated BMI: ${vitals.bmi || 'N/A'}${vitals.is_abnormal ? ' (Abnormal Flags Recorded)' : ''}`, "success");
    
    // Reset form & patient picker
    form.reset();
    clearPatientSelection();
    const feedbackBox = document.getElementById("vitalsFeedbackBox");
    if (feedbackBox) feedbackBox.style.display = "none";

    // Refresh audit logs and analytics
    loadRecentVitalsLogs();
    loadNurseAnalytics();
  } catch (err) {
    showToast(err.message || "Failed to record vitals. Please check values.", "error");
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = origBtnContent;
    }
  }
}

function clearPatientSelection() {
  currentSelectedPatient = null;
  const idInput = document.getElementById("patientIdInput");
  const searchInput = document.getElementById("patientSearchInput");
  const badge = document.getElementById("selectedPatientBadge");
  const clearBtn = document.getElementById("clearPatientBtn");
  const list = document.getElementById("patientDropdownList");

  if (idInput) idInput.value = "";
  if (searchInput) searchInput.value = "";
  if (badge) {
    badge.style.display = "none";
    badge.innerHTML = "";
  }
  if (clearBtn) clearBtn.style.display = "none";
  if (list) list.style.display = "none";
}

let patientSearchDebounce = null;

function setupPatientAutocomplete() {
  const searchInput = document.getElementById("patientSearchInput");
  const list = document.getElementById("patientDropdownList");
  const clearBtn = document.getElementById("clearPatientBtn");

  if (!searchInput || !list) return;

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      clearPatientSelection();
      searchInput.focus();
    });
  }

  // Focus or click shows patients
  searchInput.addEventListener("focus", () => {
    fetchAndDisplayPatients(searchInput.value.trim());
  });

  searchInput.addEventListener("click", () => {
    fetchAndDisplayPatients(searchInput.value.trim());
  });

  // Typing filters patients
  searchInput.addEventListener("input", (e) => {
    clearTimeout(patientSearchDebounce);
    const query = e.target.value.trim();
    patientSearchDebounce = setTimeout(() => {
      fetchAndDisplayPatients(query);
    }, 150);
  });

  // Close dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!searchInput.contains(e.target) && !list.contains(e.target) && clearBtn && !clearBtn.contains(e.target)) {
      list.style.display = "none";
    }
  });
}

async function fetchAndDisplayPatients(query = "") {
  const list = document.getElementById("patientDropdownList");
  if (!list) return;

  try {
    const url = `/api/patients/search?q=${encodeURIComponent(query)}&limit=25`;
    const patients = await apiFetch(url);

    if (!patients || patients.length === 0) {
      list.innerHTML = `<div style="padding:0.85rem; font-size:var(--font-xs); color:var(--text-muted); text-align:center;">No matching registered patients found.</div>`;
      list.style.display = "block";
      return;
    }

    list.innerHTML = patients.map(p => `
      <div class="patient-select-item" onclick="selectPatientForVitals(${JSON.stringify(p).replace(/"/g, '&quot;')})">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="font-size:0.85rem; font-weight:600; color:var(--text-main);">
            ${p.full_name} 
            <span class="badge badge-neutral" style="font-size:0.675rem; margin-left:0.35rem;">${p.mrn}</span>
          </div>
          <span style="font-size:0.75rem; font-weight:600; color:var(--primary-600); background:rgba(37,99,235,0.08); padding:0.1rem 0.4rem; border-radius:4px;">ID: #${p.id}</span>
        </div>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; display:flex; gap:0.5rem; align-items:center;">
          <span>${p.age} yrs • ${p.gender}</span>
          <span>&bull;</span>
          <span>Blood: <strong>${p.blood_group || 'N/A'}</strong></span>
          <span>&bull;</span>
          <span>📞 ${p.phone_number || '-'}</span>
          ${p.allergies && !p.allergies.toLowerCase().includes('none') ? `<span class="badge badge-danger" style="font-size:0.65rem; padding:0.05rem 0.35rem;">⚠️ ${p.allergies}</span>` : ''}
        </div>
      </div>
    `).join("");

    list.style.display = "block";
  } catch (err) {
    console.error("Failed to fetch patients for autocomplete:", err);
  }
}

async function selectPatientForVitals(p) {
  currentSelectedPatient = p;
  const idInput = document.getElementById("patientIdInput");
  const searchInput = document.getElementById("patientSearchInput");
  const badge = document.getElementById("selectedPatientBadge");
  const clearBtn = document.getElementById("clearPatientBtn");
  const list = document.getElementById("patientDropdownList");

  if (idInput) idInput.value = p.id;
  if (searchInput) searchInput.value = `${p.full_name} (${p.mrn}) - ID: #${p.id}`;
  if (clearBtn) clearBtn.style.display = "block";
  if (list) list.style.display = "none";

  if (badge) {
    badge.style.display = "block";
    badge.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <strong>Active Patient:</strong> <strong>${p.full_name}</strong> (MRN: <strong>${p.mrn}</strong>) &bull; ${p.age}y/${p.gender} &bull; Blood: <strong>${p.blood_group || 'N/A'}</strong>
          ${p.allergies && !p.allergies.toLowerCase().includes('none') ? `<span style="color:#dc2626; font-weight:600; margin-left:0.5rem;">[Allergies: ${p.allergies}]</span>` : ''}
        </div>
        <button type="button" class="btn btn-outline btn-sm" style="font-size:0.7rem; padding:0.15rem 0.5rem; border-color:#93c5fd; color:#1e40af;" onclick="clearPatientSelection()">Change</button>
      </div>
    `;
  }

  // Check and pre-fill baseline height/weight if available
  try {
    const latest = await apiFetch(`/api/clinical/vitals/latest/${p.id}`);
    if (latest && latest.id) {
      if (!document.getElementById("heightInput").value && latest.height_cm) {
        document.getElementById("heightInput").value = latest.height_cm;
      }
      if (!document.getElementById("weightInput").value && latest.weight_kg) {
        document.getElementById("weightInput").value = latest.weight_kg;
      }
      showToast(`Baseline found for ${p.full_name}: Previous BP ${latest.bp || 'N/A'}, BMI ${latest.bmi || 'N/A'}`, "info");
    }
  } catch (err) {}
}

async function loadBedMatrix() {
  const container = document.getElementById("bedMatrixContainer");
  if (!container) return;

  try {
    const matrix = await apiFetch("/api/inpatient/bed-matrix");
    let html = "";

    for (const [ward, beds] of Object.entries(matrix)) {
      html += `
        <div style="margin-bottom:1.5rem;">
          <h4 style="font-size:var(--font-sm); text-transform:uppercase; color:var(--text-muted); margin-bottom:0.75rem;">
            ${ward} (${beds.filter(b => b.status === 'OCCUPIED').length}/${beds.length} Occupied)
          </h4>
          <div class="grid-4">
            ${beds.map(b => `
              <div class="bed-card ${b.status.toLowerCase()}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  <strong>${b.bed_number}</strong>
                  <span class="badge ${b.status === 'VACANT' ? 'badge-success' : b.status === 'OCCUPIED' ? 'badge-danger' : 'badge-warning'}">
                    ${b.status}
                  </span>
                </div>
                <div style="font-size:var(--font-xs); color:var(--text-muted); margin-top:0.5rem;">
                  Type: ${b.bed_type} | ₹${b.daily_rate}/day
                </div>
                <div style="font-size:var(--font-xs); margin-top:0.25rem;">
                  ${b.patient_name ? `Patient: <strong>${b.patient_name}</strong>` : `<span style="color:var(--text-faint);">Available</span>`}
                </div>
                <div style="margin-top:0.75rem; display:flex; gap:0.35rem;">
                  ${b.status === 'OCCUPIED' ? `
                    <button class="btn btn-secondary btn-sm" onclick="openDischargeModal(${b.id}, '${b.bed_number}')">Discharge</button>
                  ` : b.status === 'CLEANING' ? `
                    <button class="btn btn-success btn-sm" onclick="toggleBedStatus(${b.id}, 'VACANT')">Mark Ready</button>
                  ` : `
                    <button class="btn btn-outline btn-sm" onclick="toggleBedStatus(${b.id}, 'CLEANING')">Sanitize</button>
                  `}
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      `;
    }

    container.innerHTML = html;
  } catch (err) {}
}

async function toggleBedStatus(bedId, newStatus) {
  try {
    await apiFetch(`/api/inpatient/beds/${bedId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus })
    });
    showToast(`Bed status updated to ${newStatus}`, "info");
    loadBedMatrix();
    loadNurseAnalytics();
  } catch (err) {}
}

async function loadIpmoQueue() {
  const container = document.getElementById("ipmoTableBody");
  if (!container) return;

  try {
    const queue = await apiFetch("/api/inpatient/ipmo-queue");
    if (!queue || queue.length === 0) {
      container.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:1.5rem;">All inpatient medications have been administered for this shift.</td></tr>`;
      return;
    }

    container.innerHTML = queue.map(q => `
      <tr>
        <td><strong>${q.bed_number}</strong> (${q.ward_name})</td>
        <td>${q.patient_name} (${q.mrn})</td>
        <td><strong>${q.medicine_name}</strong> (${q.dosage})</td>
        <td>${q.frequency} - ${q.route}</td>
        <td><span class="badge badge-warning">${q.scheduled_slot}</span></td>
        <td>
          <button class="btn btn-success btn-sm" onclick="administerMedication(${q.id}, '${q.medicine_name}')">
            Mark Administered
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {}
}

async function administerMedication(orderId, medName) {
  try {
    await apiFetch("/api/inpatient/administer-ipmo", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, notes: "Administered on time" })
    });
    showToast(`Administered ${medName}! Recorded in medication chart.`, "success");
    loadIpmoQueue();
    loadNurseAnalytics();
  } catch (err) {}
}

let currentClearance = null;

async function openDischargeModal(bedId, bedNumber) {
  try {
    const admission = await apiFetch(`/api/inpatient/active-admission/${bedId}`);
    if (!admission || !admission.id) {
      showToast("No active admission found for this bed.", "warning");
      return;
    }

    document.getElementById("dischargeRecordId").value = admission.id;
    document.getElementById("dischargePatientMeta").innerHTML = `
      <strong>Bed ${bedNumber}</strong> &bull; Patient: <strong>${admission.patient_name}</strong> (${admission.patient_mrn})<br>
      <span style="color:var(--text-muted); font-size:var(--font-xs);">IP Number: <strong>${admission.ip_number}</strong> &bull; Admitted: ${admission.admission_date}</span>
    `;

    // Reset override fields
    const overrideSection = document.getElementById("overrideSection");
    const allowOverrideCheck = document.getElementById("allowOverrideCheck");
    const overrideReasonBox = document.getElementById("overrideReasonBox");
    const overrideReasonInput = document.getElementById("overrideReasonInput");
    if (allowOverrideCheck) allowOverrideCheck.checked = false;
    if (overrideReasonBox) overrideReasonBox.style.display = "none";
    if (overrideReasonInput) overrideReasonInput.value = "";

    // Check Invariant Clearance
    const alertBox = document.getElementById("dischargeClearanceAlert");
    alertBox.innerHTML = `<div style="color:var(--text-muted); font-size:var(--font-sm);">Evaluating Discharge Billing Block Invariant...</div>`;

    const clearance = await apiFetch(`/api/inpatient/clearance/${admission.id}`);
    currentClearance = clearance;

    if (clearance.can_discharge) {
      alertBox.innerHTML = `
        <div class="card" style="border:1px solid var(--success-border); background:rgba(5, 150, 105, 0.05); padding:0.75rem 1rem; border-radius:var(--radius-md);">
          <div style="color:var(--success-border); font-weight:600; display:flex; align-items:center; gap:0.5rem;">
            <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Discharge Clearance Approved</span>
          </div>
          <div style="font-size:var(--font-xs); color:var(--text-muted); margin-top:0.25rem;">
            All scheduled medication doses administered, all lab investigations completed, and no outstanding clinical blocks.
          </div>
        </div>
      `;
      if (overrideSection) overrideSection.style.display = "none";
    } else {
      alertBox.innerHTML = `
        <div class="card" style="border:1px solid var(--danger-border); background:rgba(225, 29, 72, 0.05); padding:0.75rem 1rem; border-radius:var(--radius-md);">
          <div style="color:var(--danger-border); font-weight:600; display:flex; align-items:center; gap:0.5rem;">
            <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>Discharge Blocked by Invariant</span>
          </div>
          <ul style="margin-left:1.5rem; margin-top:0.35rem; font-size:var(--font-xs); color:var(--text-main);">
            ${clearance.blocking_reasons.map(r => `<li>${r}</li>`).join("")}
          </ul>
        </div>
      `;
      if (overrideSection) overrideSection.style.display = "block";
    }

    openModal("dischargeModal");
  } catch (err) {
    showToast(err.message || "Failed to fetch admission details.", "error");
  }
}

function toggleOverrideReason(isChecked) {
  const box = document.getElementById("overrideReasonBox");
  if (box) box.style.display = isChecked ? "block" : "none";
}

async function handleConfirmDischarge(e) {
  e.preventDefault();
  const form = e.target;
  const recordId = parseInt(form.inpatient_record_id.value, 10);
  const condition = form.discharge_condition.value;
  const summary = form.discharge_summary.value;
  const allowOverride = document.getElementById("allowOverrideCheck")?.checked || false;
  const overrideReason = document.getElementById("overrideReasonInput")?.value || "";

  if (currentClearance && !currentClearance.can_discharge && !allowOverride) {
    showToast("Discharge blocked by invariant! Resolve pending items or authorize an Emergency Clinical Override.", "warning");
    return;
  }

  if (allowOverride && !overrideReason.trim()) {
    showToast("Mandatory clinical justification is required for Emergency Override Bypass.", "warning");
    return;
  }

  const payload = {
    inpatient_record_id: recordId,
    discharge_condition: condition,
    discharge_summary: summary,
    allow_override: allowOverride,
    override_reason: overrideReason.trim() || null
  };

  try {
    const res = await apiFetch("/api/inpatient/discharge", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast(`Patient successfully discharged! Bed marked for sanitization. Bill generated: ${res.invoice_number}`, "success");
    closeModal("dischargeModal");
    form.reset();
    loadBedMatrix();
    loadIpmoQueue();
    loadNurseAnalytics();
  } catch (err) {
    showToast(err.message || "Failed to discharge patient.", "error");
  }
}

let nurseAlertsData = [];

async function loadNurseAnalytics() {
  try {
    const data = await apiFetch("/api/inpatient/analytics");
    if (!data) return;

    // Update 4 KPIs
    const kpiOccupancy = document.getElementById("kpiBedOccupancy");
    const kpiOccupancySub = document.getElementById("kpiBedOccupancySub");
    const kpiVacant = document.getElementById("kpiVacantBeds");
    const kpiCleaning = document.getElementById("kpiCleaningBeds");
    const kpiPendingIpmo = document.getElementById("kpiPendingIpmo");
    const kpiIpmoSub = document.getElementById("kpiIpmoSub");

    if (kpiOccupancy) kpiOccupancy.textContent = `${data.kpis.occupancy_rate_pct}%`;
    if (kpiOccupancySub) kpiOccupancySub.textContent = `${data.kpis.occupied_beds} of ${data.kpis.total_beds} beds occupied`;
    if (kpiVacant) kpiVacant.textContent = data.kpis.vacant_beds;
    if (kpiCleaning) kpiCleaning.textContent = data.kpis.cleaning_beds;
    if (kpiPendingIpmo) kpiPendingIpmo.textContent = data.kpis.pending_ipmo_doses;
    if (kpiIpmoSub) kpiIpmoSub.textContent = `${data.kpis.administered_ipmo_doses} administered today • ${data.kpis.admitted_inpatients} admitted`;

    // Render alerts
    nurseAlertsData = data.alerts || [];
    renderNurseAlerts(nurseAlertsData);
  } catch (err) {
    console.error("Failed to load nurse analytics:", err);
  }
}

function renderNurseAlerts(alerts) {
  const container = document.getElementById("nurseAlertsContainer");
  if (!container) return;

  if (!alerts || alerts.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  container.style.display = "block";
  const count = alerts.length;

  container.innerHTML = `
    <div class="card" style="border-left:4px solid #f59e0b; background:#fffbeb; padding:0; overflow:hidden;">
      <div style="display:flex; justify-content:space-between; align-items:center; padding:0.75rem 1rem; border-bottom:1px solid #fde68a; cursor:pointer;" onclick="toggleNurseAlerts()">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <svg class="icon" style="color:#d97706;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <strong style="color:#92400e;">Inpatient Care & Bed Turnaround Alerts (${count} Action${count > 1 ? 's' : ''})</strong>
          <span style="font-size:var(--font-xs); color:#78350f; background:#fef3c7; padding:0.15rem 0.5rem; border-radius:999px; border:1px solid #fde68a;">Ward Action Required</span>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <button type="button" class="btn btn-outline btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem; border-color:#fcd34d; color:#92400e;" id="toggleNurseAlertsBtn">
            Hide Alerts &#9652;
          </button>
        </div>
      </div>
      <div id="nurseAlertsBody" style="padding:0.75rem 1rem;">
        <div style="margin-bottom:0.6rem;">
          <input type="text" id="nurseAlertSearch" class="form-control" placeholder="Filter alerts by patient, bed number, or medication..." style="font-size:0.8rem; padding:0.35rem 0.6rem; height:auto; background:#fff; border-color:#fde68a;" oninput="filterNurseAlerts(this.value)">
        </div>
        <div id="nurseAlertsList" style="max-height:260px; overflow-y:auto; display:flex; flex-direction:column; gap:0.5rem; padding-right:0.25rem;">
          ${buildNurseAlertItemsHTML(alerts)}
        </div>
      </div>
    </div>
  `;
}

function buildNurseAlertItemsHTML(alerts) {
  if (alerts.length === 0) {
    return `<div style="font-size:0.8rem; color:#78716c; text-align:center; padding:0.5rem;">No alerts match filter.</div>`;
  }
  return alerts.map(a => `
    <div style="display:flex; justify-content:space-between; align-items:center; background:#ffffff; border:1px solid ${a.severity === 'danger' ? '#fecaca' : '#fde68a'}; border-radius:var(--radius-md); padding:0.5rem 0.75rem;">
      <div style="display:flex; align-items:center; gap:0.5rem;">
        <span class="badge ${a.severity === 'danger' ? 'badge-danger' : 'badge-warning'}" style="font-size:0.7rem;">${a.type}</span>
        <span style="font-size:0.825rem; color:var(--text-main);">${a.message}</span>
      </div>
      ${a.type === 'BED_CLEANING_REQUIRED' ? `
        <button class="btn btn-success btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem; white-space:nowrap; margin-left:0.5rem;" onclick="toggleBedStatus(${a.bed_id}, 'VACANT')">
          Mark Ready
        </button>
      ` : a.type === 'IPMO_DOSE_DUE' ? `
        <button class="btn btn-primary btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem; white-space:nowrap; margin-left:0.5rem;" onclick="administerMedication(${a.order_id}, 'Prescribed Medication')">
          Administer
        </button>
      ` : `
        <span class="badge badge-secondary" style="font-size:0.7rem; white-space:nowrap; margin-left:0.5rem;">${a.action}</span>
      `}
    </div>
  `).join("");
}

function filterNurseAlerts(query) {
  const q = (query || "").toLowerCase().trim();
  const filtered = nurseAlertsData.filter(a => 
    (a.message || "").toLowerCase().includes(q) ||
    (a.type || "").toLowerCase().includes(q)
  );
  const list = document.getElementById("nurseAlertsList");
  if (list) list.innerHTML = buildNurseAlertItemsHTML(filtered);
}

function toggleNurseAlerts() {
  const body = document.getElementById("nurseAlertsBody");
  const btn = document.getElementById("toggleNurseAlertsBtn");
  if (!body) return;
  if (body.style.display === "none") {
    body.style.display = "block";
    if (btn) btn.innerHTML = "Hide Alerts &#9652;";
  } else {
    body.style.display = "none";
    if (btn) btn.innerHTML = "Show Alerts &#9662;";
  }
}

async function loadRecentVitalsLogs() {
  const tbody = document.getElementById("recentVitalsTableBody");
  const countBadge = document.getElementById("vitalsLogCountBadge");
  if (!tbody) return;

  try {
    const records = await apiFetch("/api/clinical/vitals/recent?limit=30");
    vitalsAuditLogs = records || [];

    if (countBadge) {
      countBadge.textContent = `${vitalsAuditLogs.length} Record${vitalsAuditLogs.length === 1 ? '' : 's'}`;
    }

    renderVitalsLogs(vitalsAuditLogs);
  } catch (err) {
    console.error("Failed to load recent vitals logs:", err);
  }
}

function renderVitalsLogs(records) {
  const tbody = document.getElementById("recentVitalsTableBody");
  if (!tbody) return;

  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; color:var(--text-muted); padding:2rem;">No clinical vitals logged yet today. Use the form above to record patient triage vitals.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(v => `
    <tr style="${v.is_abnormal ? 'background:rgba(239, 68, 68, 0.03);' : ''}">
      <td>
        <div style="font-weight:600; font-size:0.8rem; color:var(--text-main);">${v.recorded_at_display}</div>
        <small style="color:var(--text-muted); font-size:0.7rem;">${v.relative_time} by ${v.recorded_by_name || 'Nurse'}</small>
      </td>
      <td>
        <strong style="color:var(--text-main); font-size:0.85rem;">${v.patient_name}</strong>
        <div style="display:flex; align-items:center; gap:0.35rem; margin-top:0.15rem;">
          <span class="badge badge-neutral" style="font-size:0.65rem;">${v.patient_mrn}</span>
          <span style="font-size:0.7rem; color:var(--text-muted);">#ID:${v.patient_id}</span>
        </div>
        ${v.patient_meta ? `<div style="font-size:0.7rem; color:var(--text-muted); margin-top:0.15rem;">${v.patient_meta}</div>` : ''}
      </td>
      <td>
        <strong style="font-size:0.85rem; color:${v.is_abnormal && v.clinical_flags && v.clinical_flags.includes('Hypertension') ? '#dc2626' : 'var(--text-main)'};">
          ${v.bp_display}
        </strong>
      </td>
      <td>
        <span style="font-size:0.85rem; ${v.is_abnormal && v.clinical_flags && (v.clinical_flags.includes('Tachycardia') || v.clinical_flags.includes('Bradycardia')) ? 'color:#dc2626; font-weight:600;' : ''}">
          ${v.heart_rate_bpm ? `${v.heart_rate_bpm} bpm` : '-'}
        </span>
      </td>
      <td>
        <span style="font-size:0.85rem; ${v.is_abnormal && v.clinical_flags && v.clinical_flags.includes('Pyrexia') ? 'color:#dc2626; font-weight:600;' : ''}">
          ${v.temperature_f ? `${v.temperature_f} °F` : '-'}
        </span>
      </td>
      <td>
        <span style="font-size:0.85rem; ${v.is_abnormal && v.clinical_flags && v.clinical_flags.includes('Hypoxemia') ? 'color:#dc2626; font-weight:bold;' : ''}">
          ${v.spo2_percent ? `${v.spo2_percent} %` : '-'}
        </span>
      </td>
      <td>
        <span style="font-size:0.85rem;">${v.respiratory_rate ? `${v.respiratory_rate} /min` : '-'}</span>
      </td>
      <td>
        <span style="font-size:0.8rem; color:var(--text-muted);">
          ${v.weight_kg ? `${v.weight_kg} kg` : '-'} / ${v.height_cm ? `${v.height_cm} cm` : '-'}
        </span>
      </td>
      <td>
        ${v.bmi ? `
          <span class="badge ${v.bmi >= 30 ? 'badge-danger' : v.bmi >= 25 ? 'badge-warning' : 'badge-success'}" style="font-size:0.7rem;">
            BMI ${v.bmi}
          </span>
        ` : '<span style="color:var(--text-faint);">-</span>'}
      </td>
      <td>
        ${v.is_abnormal && v.clinical_flags ? `
          <span class="badge badge-danger" style="font-size:0.7rem; white-space:normal; line-height:1.2;">
            ⚠️ ${v.clinical_flags}
          </span>
        ` : `
          <span class="badge badge-success" style="font-size:0.7rem;">Normal Range</span>
        `}
      </td>
      <td>
        <span style="font-size:0.8rem; color:var(--text-main); font-style:${v.triage_notes ? 'normal' : 'italic'};">
          ${v.triage_notes || '-'}
        </span>
      </td>
    </tr>
  `).join("");
}

function filterVitalsLogs(query) {
  const q = (query || "").toLowerCase().trim();
  if (!q) {
    renderVitalsLogs(vitalsAuditLogs);
    return;
  }

  const filtered = vitalsAuditLogs.filter(v => 
    (v.patient_name || "").toLowerCase().includes(q) ||
    (v.patient_mrn || "").toLowerCase().includes(q) ||
    String(v.patient_id).includes(q) ||
    (v.clinical_flags || "").toLowerCase().includes(q) ||
    (v.triage_notes || "").toLowerCase().includes(q) ||
    (v.bp_display || "").toLowerCase().includes(q)
  );

  renderVitalsLogs(filtered);
}



