/**
 * Doctor EHR Consultation Module
 * SOAP notes, 1-Click Treatment Templates, Rx line items, and Lab Orders
 */

let activeAppointment = null;
let activePatient = null;
let treatmentTemplates = [];
let availableLabTemplates = [];

document.addEventListener("DOMContentLoaded", async () => {
  await loadMetadata();
  
  const doctorSelect = document.getElementById("doctorQueueSelect");
  if (doctorSelect) {
    doctorSelect.addEventListener("change", () => {
      loadDoctorQueue();
      loadDoctorAnalytics();
      loadDoctorReviewQueue();
    });
  }
  loadDoctorQueue();
  loadDoctorAnalytics();
  loadDoctorReviewQueue();


  const templateSelect = document.getElementById("treatmentTemplateSelect");
  if (templateSelect) {
    templateSelect.addEventListener("change", applyTreatmentTemplate);
  }

  const encounterForm = document.getElementById("encounterForm");
  if (encounterForm) {
    encounterForm.addEventListener("submit", handleFinalizeEncounter);
  }
});

async function loadMetadata() {
  const [templatesResult, labsResult] = await Promise.allSettled([
    apiFetch("/api/clinical/templates"),
    apiFetch("/api/lab/templates")
  ]);

  treatmentTemplates = templatesResult.status === "fulfilled" ? templatesResult.value || [] : [];
  availableLabTemplates = labsResult.status === "fulfilled" ? labsResult.value || [] : [];

  const tSelect = document.getElementById("treatmentTemplateSelect");
  if (tSelect) {
    tSelect.innerHTML = `<option value="">-- Choose 1-Click Treatment Protocol --</option>` +
      treatmentTemplates.map(t => `<option value="${t.id}">${t.name} (${t.diagnosis})</option>`).join("");
    if (templatesResult.status === "rejected") {
      tSelect.innerHTML += `<option value="" disabled>Protocols could not be loaded</option>`;
    }
  }

  const labContainer = document.getElementById("labCheckboxesContainer");
  if (labContainer) {
    labContainer.innerHTML = availableLabTemplates.length ? availableLabTemplates.map(t => `
      <label style="display:flex; align-items:center; gap:0.5rem; font-size:var(--font-sm); margin-bottom:0.4rem; cursor:pointer;">
        <input type="checkbox" name="lab_order" value="${t.id}">
        <span><strong>${t.test_code}</strong>: ${t.test_name} (Rs. ${t.standard_rate})</span>
      </label>
    `).join("") : `<p class="kpi-sub">${labsResult.status === "rejected" ? "Lab tests could not be loaded." : "No lab tests are configured."}</p>`;
  }
}

async function loadDoctorQueue() {
  const doctorSelect = document.getElementById("doctorQueueSelect");
  const docId = doctorSelect?.value || window.HMS_DOCTOR_ID;
  if (!docId) return;
  try {
    const queue = await apiFetch(`/api/appointments/doctor-queue?doctor_id=${docId}`);
    renderQueue(queue);
  } catch (err) {}
}

function renderQueue(queue) {
  const container = document.getElementById("queueContainer");
  if (!container) return;

  if (!queue || queue.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); font-size:var(--font-sm); padding:1rem; text-align:center;">No patients waiting in queue today.</p>`;
    return;
  }

  container.innerHTML = queue.map(item => `
    <div class="card" style="padding:0.75rem 1rem; margin-bottom:0.75rem; border-left:4px solid ${item.status === 'COMPLETED' ? '#10b981' : '#2563eb'}; cursor:pointer;" onclick="selectPatientForConsultation(${JSON.stringify(item).replace(/"/g, '&quot;')})">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
          <span class="badge ${item.status === 'COMPLETED' ? 'badge-success' : 'badge-warning'}">Token #${item.token_number}</span>
          <strong style="margin-left:0.5rem;">${item.patient_name}</strong> (${item.age}/${item.gender})
        </div>
        <span style="font-size:var(--font-xs); color:var(--text-muted);">${item.time_slot}</span>
      </div>
      <div style="font-size:var(--font-xs); color:var(--text-muted); margin-top:0.25rem;">
        MRN: ${item.patient_mrn} | Reason: ${item.reason_for_visit}
      </div>
    </div>
  `).join("");
}

async function selectPatientForConsultation(item) {
  activeAppointment = item;
  
  // Fetch full patient details & latest vitals
  try {
    activePatient = await apiFetch(`/api/patients/${item.patient_id}`);
    const vitals = await apiFetch(`/api/clinical/vitals/latest/${item.patient_id}`);

    // Update Banner
    const emptyState = document.getElementById("consultationEmptyState");
    if (emptyState) emptyState.style.display = "none";
    document.getElementById("consultationBanner").style.display = "block";
    document.getElementById("activePatientName").innerText = `${activePatient.full_name} (${activePatient.mrn})`;
    document.getElementById("activePatientMeta").innerText = `Age: ${activePatient.age} | Gender: ${activePatient.gender} | Blood Group: ${activePatient.blood_group || 'N/A'}`;
    
    // Allergies alert
    const allergyBox = document.getElementById("activePatientAllergies");
    if (activePatient.allergies) {
      allergyBox.style.display = "block";
      allergyBox.innerHTML = `<strong>Known Allergies:</strong> ${activePatient.allergies}`;
    } else {
      allergyBox.style.display = "none";
    }

    // Vitals Display
    const vitalsBox = document.getElementById("activePatientVitals");
    if (vitals && vitals.bp) {
      vitalsBox.innerHTML = `
        <div style="display:flex; gap:1rem; flex-wrap:wrap; font-size:var(--font-sm);">
          <span><strong>BP:</strong> ${vitals.bp} mmHg</span>
          <span><strong>Pulse:</strong> ${vitals.heart_rate_bpm || '-'} bpm</span>
          <span><strong>Temp:</strong> ${vitals.temperature_f || '-'} °F</span>
          <span><strong>SpO2:</strong> ${vitals.spo2_percent || '-'}%</span>
          <span><strong>BMI:</strong> ${vitals.bmi || '-'}</span>
          ${vitals.is_abnormal ? `<span class="badge badge-danger">Alert: ${vitals.clinical_flags}</span>` : `<span class="badge badge-success">Vitals Normal</span>`}
        </div>
      `;
    } else {
      vitalsBox.innerHTML = `<span style="font-size:var(--font-xs); color:var(--text-muted);">No vitals logged for this visit yet.</span>`;
    }

    // Pre-fill reason into chief complaint
    document.getElementById("chiefComplaint").value = item.reason_for_visit || "";

    // Fetch and display Read-Only Invoice State
    const invoiceBox = document.getElementById("activePatientInvoiceState");
    if (invoiceBox) {
      try {
        const invoices = await apiFetch(`/api/billing/invoices?patient_id=${item.patient_id}`);
        if (invoices && invoices.length > 0) {
          const latestInv = invoices[0];
          const isPaid = latestInv.payment_status === "PAID";
          const statusBadge = isPaid
            ? `<span class="badge badge-success">PAID (Settled)</span>`
            : `<span class="badge badge-warning">PENDING PAYMENT (₹${(latestInv.net_payable - latestInv.paid_amount).toFixed(2)} Due)</span>`;

          invoiceBox.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem; background:rgba(0,0,0,0.02); padding:0.5rem 0.75rem; border-radius:var(--radius-sm); border:1px solid rgba(0,0,0,0.05);">
              <div style="display:flex; align-items:center; gap:0.5rem; font-size:var(--font-sm);">
                <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
                <span><strong>Invoice State:</strong> ${latestInv.invoice_number}</span>
                ${statusBadge}
                <span style="font-size:var(--font-xs); color:var(--text-muted);">(Total: ₹${latestInv.net_payable.toFixed(2)})</span>
              </div>
              <div style="font-size:var(--font-xs); color:var(--text-muted); display:inline-flex; align-items:center; gap:0.3rem;">
                <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <span>Read-only: Doctor cannot alter fees, apply discounts, or settle balances.</span>
              </div>
            </div>
          `;
        } else {
          invoiceBox.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:var(--font-xs); color:var(--text-muted); background:rgba(0,0,0,0.02); padding:0.4rem 0.75rem; border-radius:var(--radius-sm);">
              <span><strong>Billing State:</strong> No prior invoices. Consultation charge will be generated upon SOAP finalization.</span>
              <span style="display:inline-flex; align-items:center; gap:0.25rem;">
                <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                Read-only: Fee edits locked
              </span>
            </div>
          `;
        }
      } catch (e) {
        invoiceBox.innerHTML = "";
      }
    }
    
    // Enable form
    document.getElementById("consultationFormCard").style.display = "block";
    document.getElementById("consultationFormCard").scrollIntoView({ behavior: "smooth" });

  } catch (err) {}
}

function applyTreatmentTemplate() {
  const select = document.getElementById("treatmentTemplateSelect");
  const templateId = parseInt(select.value, 10);
  if (!templateId) return;

  const t = treatmentTemplates.find(x => x.id === templateId);
  if (!t) return;

  document.getElementById("diagnosis").value = t.diagnosis;
  document.getElementById("icd10Code").value = t.icd10_code || "";
  if (!document.getElementById("chiefComplaint").value) {
    document.getElementById("chiefComplaint").value = t.default_complaint || "";
  }

  // Pre-fill Rx
  try {
    const rxList = JSON.parse(t.default_rx);
    const tbody = document.getElementById("rxTableBody");
    tbody.innerHTML = "";
    rxList.forEach(rx => addPrescriptionRow(rx));
  } catch (e) {}

  // Pre-check Labs
  try {
    const labIds = JSON.parse(t.default_labs || "[]");
    document.querySelectorAll("input[name='lab_order']").forEach(cb => {
      cb.checked = labIds.includes(parseInt(cb.value, 10));
    });
  } catch (e) {}

  showToast(`Applied protocol: ${t.name}`, "info");
}

function addPrescriptionRow(data = {}) {
  const tbody = document.getElementById("rxTableBody");
  const rowId = "rx_" + Math.random().toString(36).substring(7);
  
  const tr = document.createElement("tr");
  tr.id = rowId;
  tr.innerHTML = `
    <td>
      <input type="text" class="form-control rx-med" value="${data.medicine_name || ''}" placeholder="Medicine name" required>
    </td>
    <td>
      <input type="text" class="form-control rx-dose" value="${data.dosage || '650 mg'}" style="width:90px;" placeholder="Dose">
    </td>
    <td>
      <select class="form-select rx-freq" style="width:100px;">
        <option value="1-0-1" ${data.frequency === '1-0-1' ? 'selected' : ''}>1-0-1</option>
        <option value="1-0-0" ${data.frequency === '1-0-0' ? 'selected' : ''}>1-0-0</option>
        <option value="0-0-1" ${data.frequency === '0-0-1' ? 'selected' : ''}>0-0-1</option>
        <option value="1-1-1" ${data.frequency === '1-1-1' ? 'selected' : ''}>1-1-1</option>
        <option value="SOS" ${data.frequency === 'SOS' ? 'selected' : ''}>SOS</option>
      </select>
    </td>
    <td>
      <input type="number" class="form-control rx-days" value="${data.duration_days || 3}" style="width:70px;" min="1">
    </td>
    <td>
      <input type="text" class="form-control rx-inst" value="${data.instructions || 'After Food'}" placeholder="Instructions">
    </td>
    <td>
      <button type="button" class="btn btn-danger btn-sm" onclick="document.getElementById('${rowId}').remove()">&times;</button>
    </td>
  `;
  tbody.appendChild(tr);
}

async function handleFinalizeEncounter(e) {
  e.preventDefault();
  if (!activeAppointment || !activePatient) {
    showToast("Please select a patient from the waiting queue first.", "warning");
    return;
  }

  const chiefComplaint = (document.getElementById("chiefComplaint").value || "").trim();
  const diagnosis = (document.getElementById("diagnosis").value || "").trim();

  if (!chiefComplaint) {
    showToast("Please enter the patient's Chief Complaints.", "warning");
    document.getElementById("chiefComplaint").focus();
    return;
  }

  if (!diagnosis) {
    showToast("Please enter the Assessment / Diagnosis.", "warning");
    document.getElementById("diagnosis").focus();
    return;
  }

  // Gather Prescriptions
  const rxRows = document.querySelectorAll("#rxTableBody tr");
  const prescriptions = [];
  rxRows.forEach(row => {
    const medInput = row.querySelector(".rx-med");
    const medName = medInput ? medInput.value.trim() : "";
    if (medName) {
      prescriptions.push({
        medicine_name: medName,
        dosage: row.querySelector(".rx-dose") ? row.querySelector(".rx-dose").value : "650 mg",
        frequency: row.querySelector(".rx-freq") ? row.querySelector(".rx-freq").value : "1-0-1",
        duration_days: parseInt(row.querySelector(".rx-days") ? row.querySelector(".rx-days").value : 3, 10) || 3,
        instructions: (row.querySelector(".rx-inst") ? row.querySelector(".rx-inst").value : "After Food") || "After Food",
        quantity: (parseInt(row.querySelector(".rx-days") ? row.querySelector(".rx-days").value : 3, 10) || 3) * 2
      });
    }
  });

  // Gather Labs
  const labIds = [];
  document.querySelectorAll("input[name='lab_order']:checked").forEach(cb => {
    labIds.push(parseInt(cb.value, 10));
  });

  const admissionRec = document.getElementById("admissionCheckbox").checked;
  const doctorSelect = document.getElementById("doctorQueueSelect");
  const docId = window.HMS_IS_DOCTOR ? window.HMS_DOCTOR_ID : (activeAppointment && activeAppointment.doctor_id)
    ? activeAppointment.doctor_id
    : (doctorSelect && doctorSelect.value ? parseInt(doctorSelect.value, 10) : null);

  const payload = {
    patient_id: activePatient.id,
    doctor_id: docId,
    appointment_id: activeAppointment.id,
    chief_complaint: chiefComplaint,
    clinical_notes: (document.getElementById("clinicalNotes").value || "").trim(),
    diagnosis: diagnosis,
    icd10_code: (document.getElementById("icd10Code").value || "").trim(),
    prescriptions: prescriptions,
    lab_test_template_ids: labIds,
    admission_recommended: admissionRec,
    admission_ward_preference: admissionRec ? document.getElementById("admissionWard").value : null
  };

  try {
    const result = await apiFetch("/api/clinical/encounter", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast(`Consultation Finalized! Invoice #${result.invoice_number} created for cashier.`, "success");
    
    // Open printable prescription in new tab
    window.open(`/rx/${result.encounter_id}`, "_blank");

    // Reset and reload queue
    document.getElementById("consultationFormCard").style.display = "none";
    document.getElementById("consultationBanner").style.display = "none";
    const emptyState = document.getElementById("consultationEmptyState");
    if (emptyState) emptyState.style.display = "block";
    activeAppointment = null;
    activePatient = null;
    loadDoctorQueue();
    loadDoctorAnalytics();
  } catch (err) {}
}

let doctorAlertsData = [];

async function loadDoctorAnalytics() {
  const doctorSelect = document.getElementById("doctorQueueSelect");
  const docId = doctorSelect?.value || window.HMS_DOCTOR_ID || "";
  
  try {
    const data = await apiFetch(`/api/clinical/analytics?doctor_id=${docId}`);
    if (!data) return;

    // Update 4 KPIs
    const kpiQueue = document.getElementById("kpiDocQueue");
    const kpiWaiting = document.getElementById("kpiDocWaiting");
    const kpiCompleted = document.getElementById("kpiDocCompleted");
    const kpiRisks = document.getElementById("kpiDocRisks");
    const kpiRiskSub = document.getElementById("kpiDocRiskSub");

    if (kpiQueue) kpiQueue.textContent = data.kpis.queue_total ?? 0;
    if (kpiWaiting) kpiWaiting.textContent = data.kpis.waiting ?? 0;
    if (kpiCompleted) kpiCompleted.textContent = data.kpis.completed ?? 0;
    
    const riskTotal = (data.kpis.abnormal_vitals_count ?? 0) + (data.kpis.allergy_count ?? 0);
    if (kpiRisks) kpiRisks.textContent = riskTotal;
    if (kpiRiskSub) {
      kpiRiskSub.textContent = `${data.kpis.abnormal_vitals_count ?? 0} abnormal vitals • ${data.kpis.allergy_count ?? 0} critical allergies`;
    }

    // Render alerts
    doctorAlertsData = data.alerts || [];
    renderDoctorAlerts(doctorAlertsData);
  } catch (err) {
    console.error("Failed to load doctor analytics:", err);
  }
}

function renderDoctorAlerts(alerts) {
  const container = document.getElementById("doctorAlertsContainer");
  if (!container) return;

  if (!alerts || alerts.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  container.style.display = "block";
  const count = alerts.length;

  container.innerHTML = `
    <div class="card" style="border-left:4px solid #ef4444; background:#fff7ed; padding:0; overflow:hidden;">
      <div style="display:flex; justify-content:space-between; align-items:center; padding:0.75rem 1rem; border-bottom:1px solid #fed7aa; cursor:pointer;" onclick="toggleDoctorAlerts()">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <svg class="icon" style="color:#c2410c;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <strong style="color:#9a3412;">Clinical Alerts & Anomaly Warnings (${count} Flag${count > 1 ? 's' : ''})</strong>
          <span style="font-size:var(--font-xs); color:#7c2d12; background:#ffedd5; padding:0.15rem 0.5rem; border-radius:999px; border:1px solid #fdba74;">Action Required Before Prescribing</span>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <button type="button" class="btn btn-outline btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem; border-color:#fdba74; color:#9a3412;" id="toggleDoctorAlertsBtn">
            Hide Alerts &#9652;
          </button>
        </div>
      </div>
      <div id="doctorAlertsBody" style="padding:0.75rem 1rem;">
        <div style="margin-bottom:0.6rem;">
          <input type="text" id="doctorAlertSearch" class="form-control" placeholder="Filter alerts by patient, flag or condition..." style="font-size:0.8rem; padding:0.35rem 0.6rem; height:auto; background:#fff; border-color:#fed7aa;" oninput="filterDoctorAlerts(this.value)">
        </div>
        <div id="doctorAlertsList" style="max-height:260px; overflow-y:auto; display:flex; flex-direction:column; gap:0.5rem; padding-right:0.25rem;">
          ${buildDoctorAlertItemsHTML(alerts)}
        </div>
      </div>
    </div>
  `;
}

function buildDoctorAlertItemsHTML(alerts) {
  if (alerts.length === 0) {
    return `<div style="font-size:0.8rem; color:#78716c; text-align:center; padding:0.5rem;">No alerts match filter.</div>`;
  }
  return alerts.map(a => `
    <div style="display:flex; justify-content:space-between; align-items:center; background:#ffffff; border:1px solid ${a.severity === 'danger' ? '#fecaca' : '#fed7aa'}; border-radius:var(--radius-md); padding:0.5rem 0.75rem;">
      <div style="display:flex; align-items:center; gap:0.5rem;">
        <span class="badge ${a.severity === 'danger' ? 'badge-danger' : 'badge-warning'}" style="font-size:0.7rem;">${a.type}</span>
        <span style="font-size:0.825rem; font-weight:600; color:var(--text-main);">${a.patient_name || 'Patient'}:</span>
        <span style="font-size:0.825rem; color:var(--text-main);">${a.message}</span>
      </div>
      <span class="badge badge-secondary" style="font-size:0.7rem; white-space:nowrap; margin-left:0.5rem;">${a.action}</span>
    </div>
  `).join("");
}

function filterDoctorAlerts(query) {
  const q = (query || "").toLowerCase().trim();
  const filtered = doctorAlertsData.filter(a => 
    (a.patient_name || "").toLowerCase().includes(q) ||
    (a.message || "").toLowerCase().includes(q) ||
    (a.type || "").toLowerCase().includes(q)
  );
  const list = document.getElementById("doctorAlertsList");
  if (list) list.innerHTML = buildDoctorAlertItemsHTML(filtered);
}

function toggleDoctorAlerts() {
  const body = document.getElementById("doctorAlertsBody");
  const btn = document.getElementById("toggleDoctorAlertsBtn");
  if (!body) return;
  if (body.style.display === "none") {
    body.style.display = "block";
    if (btn) btn.innerHTML = "Hide Alerts &#9652;";
  } else {
  }
}

// ----------------------------------------------------
// Diagnostic Reports Review & Clinical Authentication
// ----------------------------------------------------
window._doctorReviewQueueCache = [];

async function loadDoctorReviewQueue() {
  const tbody = document.getElementById("doctorReviewQueueBody");
  if (!tbody) return;

  try {
    const data = await apiFetch("/api/lab/doctor-review-queue");
    window._doctorReviewQueueCache = data || [];
    renderDoctorReviewQueue(window._doctorReviewQueueCache);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:1.5rem; color:#ef4444;">Failed to load diagnostic review queue.</td></tr>`;
  }
}

function renderDoctorReviewQueue(items) {
  const tbody = document.getElementById("doctorReviewQueueBody");
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:var(--text-muted);">No diagnostic reports awaiting review.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(item => {
    const res = item.result || {};
    
    // Status Badge
    let statusBadge = `<span class="badge badge-info">⏳ AWAITING REVIEW</span>`;
    if (res.doctor_approval_status === "APPROVED") {
      statusBadge = `<span class="badge badge-success">✓ APPROVED</span><div style="font-size:0.7rem; color:#059669; margin-top:2px;">Signed by Doctor</div>`;
    } else if (res.doctor_approval_status === "REVISION_REQUESTED") {
      statusBadge = `<span class="badge badge-warning">⚠️ REVISION SENT</span><div style="font-size:0.7rem; color:#d97706; margin-top:2px;" title="${escapeDoctorJs(res.doctor_notes)}">In Lab Tech Queue</div>`;
    }

    // Abnormal / Panic Badge
    let panicTag = "";
    if (res.is_abnormal || (res.panic_flag && res.panic_flag !== "NORMAL")) {
      panicTag = `<span class="badge badge-danger" style="font-size:0.68rem; margin-left:4px;">${res.panic_flag || 'ABNORMAL'}</span>`;
    }

    // Findings Preview
    let findingsPreview = "";
    if (res.parameter_results) {
      try {
        const params = JSON.parse(res.parameter_results);
        findingsPreview = `<div style="font-size:0.78rem; color:var(--text-muted);">${params.map(p => `<strong>${p.name}:</strong> ${p.value} ${p.unit}`).slice(0, 3).join(", ")}${params.length > 3 ? '...' : ''}</div>`;
      } catch (e) {
        findingsPreview = `<div style="font-size:0.78rem; color:var(--text-muted);">${res.result_value || '-'}</div>`;
      }
    } else if (res.impression || res.findings) {
      findingsPreview = `<div style="font-size:0.78rem; color:var(--text-muted); line-height:1.3;"><strong>Impression:</strong> ${res.impression || res.findings.substring(0, 70)}...</div>`;
    } else {
      findingsPreview = `<div style="font-size:0.78rem; color:var(--text-muted);">${res.result_value || '-'}</div>`;
    }

    // Image preview if radiology
    let imageThumbnail = "";
    if (res.annotated_image_url || res.image_url) {
      const imgUrl = res.annotated_image_url || res.image_url;
      imageThumbnail = `
        <div style="margin-top:4px;">
          <a href="${imgUrl}" target="_blank" style="font-size:0.72rem; color:#2563eb; text-decoration:none; display:inline-flex; align-items:center; gap:3px;">
            🖼️ View Scan (${item.modality || 'Imaging'})
          </a>
        </div>
      `;
    }

    // Revision notes if any
    let doctorNotesHtml = "";
    if (res.doctor_notes) {
      doctorNotesHtml = `
        <div style="font-size:0.72rem; color:#b45309; background:#fffbeb; padding:0.25rem 0.5rem; border-radius:4px; margin-top:4px; border:1px solid #fef3c7;">
          <strong>Revision Note:</strong> ${res.doctor_notes}
        </div>
      `;
    }

    // Action buttons
    const isApproved = (res.doctor_approval_status === "APPROVED");
    const actionsHtml = `
      <div style="display:flex; flex-direction:column; gap:0.35rem; align-items:flex-start;">
        ${!isApproved ? `
          <button class="btn btn-success btn-sm" style="font-size:0.75rem; padding:0.3rem 0.65rem;" onclick="approveLabResult(${item.order_id})">
            ✓ Sign &amp; Authorize
          </button>
          <button class="btn btn-outline btn-sm" style="font-size:0.72rem; padding:0.25rem 0.5rem; color:#b45309; border-color:#fde68a;" 
                  onclick="openDoctorRevisionModal(${item.order_id}, '${escapeDoctorJs(item.patient?.name)}', '${escapeDoctorJs(item.test_name)}')">
            ↩️ Request Changes
          </button>
        ` : `
          <span class="badge badge-success" style="font-size:0.72rem;">✓ Signed Off</span>
        `}
        <a href="/api/lab/reports/${item.order_id}/pdf" target="_blank" class="btn btn-outline btn-sm" style="font-size:0.7rem; padding:0.2rem 0.45rem; text-decoration:none;">
          📄 View Full PDF
        </a>
      </div>
    `;

    return `
      <tr>
        <td>
          <strong>#${item.order_id}</strong>
          <div style="font-size:0.72rem; color:var(--text-muted); font-family:monospace;">${item.sample_barcode || '-'}</div>
          <div style="font-size:0.7rem; color:#94a3b8;">${item.created_at}</div>
        </td>
        <td>
          <strong>${item.patient?.name || 'Patient'}</strong>
          <div style="font-size:0.75rem; color:var(--text-muted);">MRN: ${item.patient?.mrn || '-'}</div>
          <div style="font-size:0.72rem; color:#64748b;">${item.patient?.age_gender || ''}</div>
        </td>
        <td>
          <div style="display:flex; align-items:center;">
            <strong>${item.test_name}</strong>
            ${panicTag}
          </div>
          <div><span class="badge badge-neutral" style="font-size:0.7rem;">${item.modality || item.department}</span></div>
        </td>
        <td>
          ${findingsPreview}
          ${imageThumbnail}
          ${doctorNotesHtml}
        </td>
        <td>
          ${statusBadge}
        </td>
        <td>
          ${actionsHtml}
        </td>
      </tr>
    `;
  }).join("");
}

function escapeDoctorJs(str) {
  if (!str) return "";
  return String(str).replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

async function approveLabResult(orderId) {
  try {
    const res = await apiFetch(`/api/lab/orders/${orderId}/doctor-review`, {
      method: "POST",
      body: JSON.stringify({
        action: "APPROVE",
        doctor_notes: "Clinically authenticated and approved by consulting physician."
      })
    });
    showToast(res.message || "Report signed off and authenticated successfully!", "success");
    loadDoctorReviewQueue();
  } catch (err) {}
}

function openDoctorRevisionModal(orderId, patientName, testName) {
  document.getElementById("revOrderId").value = orderId;
  const pName = document.getElementById("revPatientName");
  if (pName) pName.innerText = patientName || "Patient";
  const tName = document.getElementById("revTestName");
  if (tName) tName.innerText = testName || "Investigation";
  const notes = document.getElementById("revDoctorNotes");
  if (notes) notes.value = "";
  openModal("doctorRevisionModal");
}

async function submitDoctorRevision() {
  const orderId = document.getElementById("revOrderId").value;
  const notes = (document.getElementById("revDoctorNotes")?.value || "").trim();

  if (!notes) {
    showToast("Please enter the clinical changes or revision instructions for the technician", "warning");
    document.getElementById("revDoctorNotes")?.focus();
    return;
  }

  const btn = document.getElementById("btnSubmitRevision");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Returning to Lab...";
  }

  try {
    const res = await apiFetch(`/api/lab/orders/${orderId}/doctor-review`, {
      method: "POST",
      body: JSON.stringify({
        action: "REQUEST_REVISION",
        doctor_notes: notes
      })
    });

    closeModal("doctorRevisionModal");
    showToast(res.message || "Report returned to technician queue with revision notes", "info");
    loadDoctorReviewQueue();
  } catch (err) {
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "↩️ Return to Technician with Notes";
    }
  }
}


