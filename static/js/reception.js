/**
 * Reception Desk & Patient Registration Module
 */

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

let selectedPatient = null;
let allReceptionCorporateClients = [];

document.addEventListener("DOMContentLoaded", () => {
  loadRecentPatients();
  loadReceptionAnalytics();
  loadDispatchQueue();
  loadReceptionCorporatePartners();
  
  const searchInput = document.getElementById("patientSearchInput");

  if (searchInput) {
    let timeout = null;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => searchPatients(e.target.value), 250);
    });
  }

  const regForm = document.getElementById("quickRegisterForm");
  if (regForm) {
    regForm.addEventListener("submit", handleQuickRegister);
  }

  const bookForm = document.getElementById("bookingForm");
  if (bookForm) {
    bookForm.addEventListener("submit", handleBookAppointment);
  }
});

async function searchPatients(query) {
  try {
    const patients = await apiFetch(`/api/patients/search?q=${encodeURIComponent(query)}`);
    renderPatientList(patients);
  } catch (err) {
    // Error handled by core
  }
}

async function loadRecentPatients() {
  try {
    const patients = await apiFetch("/api/patients/search?limit=10");
    renderPatientList(patients);
  } catch (err) {}
}

function renderPatientList(patients) {
  const tbody = document.getElementById("patientTableBody");
  if (!tbody) return;

  if (!patients || patients.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:2rem;">No patients found. Use the quick registration form above.</td></tr>`;
    return;
  }

  tbody.innerHTML = patients.map(p => `
    <tr>
      <td>
        <strong>${p.mrn}</strong>
        ${p.billing_category === 'CORPORATE_TIEUP' ? `<div style="font-size:0.68rem; color:#2563eb; font-weight:600;">🏢 Corporate Tie-up</div>` : `<div style="font-size:0.68rem; color:var(--text-muted);">🚶 Walk-in</div>`}
      </td>
      <td><strong>${p.full_name}</strong></td>
      <td>${p.phone_number}</td>
      <td>${p.age} / ${p.gender}</td>
      <td>${p.blood_group || '-'}</td>
      <td style="display:flex; gap:0.35rem;">
        <button class="btn btn-outline btn-sm" onclick="inspectPatientDemographics(${JSON.stringify(p).replace(/"/g, '&quot;')})" title="View Demographics & Guard">
          Demographics
        </button>
        <button class="btn btn-primary btn-sm" onclick="selectPatientForBooking(${JSON.stringify(p).replace(/"/g, '&quot;')})">
          Select &amp; Book
        </button>
      </td>
    </tr>
  `).join("");
}

function inspectPatientDemographics(patient) {
  const container = document.getElementById("demographicsContent");
  if (container) {
    container.innerHTML = `
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; font-size:var(--font-sm);">
        <div><strong>MRN:</strong> ${patient.mrn}</div>
        <div><strong>Full Name:</strong> ${patient.full_name}</div>
        <div><strong>Phone:</strong> ${patient.phone_number}</div>
        <div><strong>Age / Gender:</strong> ${patient.age} / ${patient.gender}</div>
        <div><strong>Blood Group:</strong> ${patient.blood_group || 'Unknown'}</div>
        <div><strong>Aadhaar / ID:</strong> ${patient.aadhar_card_no || 'Not recorded'}</div>
        <div style="grid-column: span 2;"><strong>Emergency Contact:</strong> ${patient.emergency_contact_name || 'None listed'} (${patient.emergency_contact_phone || '-'})</div>
      </div>
    `;
  }
  const selectBtn = document.getElementById("btnSelectFromModal");
  if (selectBtn) {
    selectBtn.onclick = () => {
      closeModal("patientDemographicsModal");
      selectPatientForBooking(patient);
    };
  }
  openModal("patientDemographicsModal");
}

function selectPatientForBooking(patient) {
  selectedPatient = patient;
  document.getElementById("selectedPatientId").value = patient.id;
  document.getElementById("selectedPatientBanner").style.display = "block";
  
  let corpTag = "";
  if (patient.billing_category === "CORPORATE_TIEUP") {
    corpTag = ` <span class="badge badge-primary" style="margin-left:6px;">🏢 Corporate Tie-up: Policy #${escapeHtml(patient.corporate_policy_id || 'Cashless')}</span>`;
  } else {
    corpTag = ` <span class="badge badge-neutral" style="margin-left:6px;">🚶 Walk-in</span>`;
  }
  
  document.getElementById("selectedPatientName").innerHTML = `<strong>${escapeHtml(patient.full_name)}</strong> (${patient.mrn}) • Age: ${patient.age} • Phone: ${patient.phone_number}${corpTag}`;
  
  // Scroll to booking section
  document.getElementById("bookingCard").scrollIntoView({ behavior: "smooth" });
}


async function handleQuickRegister(e) {
  e.preventDefault();
  const form = e.target;
  const bCategory = form.regBillingCategory?.value || "WALK_IN";
  const corpClientId = bCategory === "CORPORATE_TIEUP" && form.regCorporateClientSelect?.value ? parseInt(form.regCorporateClientSelect.value, 10) : null;
  const policyId = bCategory === "CORPORATE_TIEUP" ? (document.getElementById("regCorporatePolicyId")?.value.trim() || null) : null;

  if (bCategory === "CORPORATE_TIEUP" && !corpClientId) {
    showToast("Please choose an Insurance / Corporate Partner", "warning");
    return;
  }

  const payload = {
    full_name: form.fullName.value,
    phone_number: form.phoneNumber.value,
    age: parseInt(form.age.value, 10),
    gender: form.gender.value,
    blood_group: form.bloodGroup.value || null,
    allergies: form.allergies.value || null,
    referred_by_doctor_id: form.referred_by_doctor_id && form.referred_by_doctor_id.value ? parseInt(form.referred_by_doctor_id.value, 10) : null,
    billing_category: bCategory,
    corporate_client_id: corpClientId,
    corporate_policy_id: policyId
  };

  try {
    const newPatient = await apiFetch("/api/patients/", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    showToast(`Patient registered! Assigned MRN: ${newPatient.mrn}`, "success");
    form.reset();
    onRegCategoryToggle("WALK_IN");
    loadRecentPatients();
    selectPatientForBooking(newPatient);
  } catch (err) {}
}

// ---------------------------------------------------------------------------
// Corporate Tie-up & Credit Limit Tracking for Receptionist
// ---------------------------------------------------------------------------
async function loadReceptionCorporatePartners() {
  try {
    const clients = await apiFetch("/api/corporate/clients?active_only=true");
    allReceptionCorporateClients = clients || [];
    
    // 1. Populate dropdown in registration form
    const select = document.getElementById("regCorporateClientSelect");
    if (select) {
      select.innerHTML = `<option value="">-- Choose Corporate Partner / TPA --</option>` +
        allReceptionCorporateClients.map(c => `
          <option value="${c.id}">
            ${escapeHtml(c.name)} (${c.category.replace(/_/g, ' ')}) - ₹${c.available_credit.toLocaleString('en-IN', {minimumFractionDigits: 0})} Avail
          </option>
        `).join("");
    }

    // 2. Populate quick cards grid
    renderReceptionCorporateCards();
  } catch (err) {
    console.warn("Could not load corporate partners for reception:", err);
  }
}

function renderReceptionCorporateCards() {
  const grid = document.getElementById("receptionCorpCardsGrid");
  if (!grid) return;

  if (!allReceptionCorporateClients || allReceptionCorporateClients.length === 0) {
    grid.innerHTML = `<div style="grid-column: 1 / -1; font-size:0.75rem; color:var(--text-muted); padding:0.5rem;">No corporate tie-up partners configured.</div>`;
    return;
  }

  grid.innerHTML = allReceptionCorporateClients.map(c => {
    const pct = c.utilization_percentage || 0;
    const progressColor = pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#10b981";
    return `
      <div style="background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:0.6rem 0.75rem;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:2px;">
          <strong style="font-size:0.78rem; color:var(--text-main); line-height:1.2;">${escapeHtml(c.name)}</strong>
          <span class="badge ${c.category === 'INSURANCE_TPA' ? 'badge-primary' : 'badge-info'}" style="font-size:0.65rem; padding:1px 4px;">
            ${c.category.replace(/_/g, ' ')}
          </span>
        </div>
        <div style="margin-top:4px; display:flex; justify-content:space-between; align-items:baseline;">
          <span style="font-size:0.7rem; color:var(--text-muted);">Available:</span>
          <strong style="color:#059669; font-size:0.85rem;">₹${c.available_credit.toLocaleString('en-IN', {minimumFractionDigits: 0})}</strong>
        </div>
        <div style="font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:2px;">
          <span>Monthly Cap: ₹${c.monthly_credit_limit.toLocaleString('en-IN', {minimumFractionDigits: 0})}</span>
          <span>${pct}% util</span>
        </div>
        <div style="background:#e2e8f0; border-radius:3px; height:4px; overflow:hidden; margin-top:4px;">
          <div style="background:${progressColor}; width:${Math.min(pct, 100)}%; height:100%;"></div>
        </div>
      </div>
    `;
  }).join("");
}

function toggleCorporateCreditQuickView() {
  const panel = document.getElementById("corporateCreditQuickPanel");
  if (!panel) return;
  const isHidden = panel.style.display === "none";
  panel.style.display = isHidden ? "block" : "none";
  if (isHidden && allReceptionCorporateClients.length === 0) {
    loadReceptionCorporatePartners();
  }
}

function onRegCategoryToggle(val) {
  const btnWalkin = document.getElementById("btnRegWalkin");
  const btnCorporate = document.getElementById("btnRegCorporate");
  const corpArea = document.getElementById("regCorporateFieldsArea");
  const badge = document.getElementById("regCategoryBadge");

  if (val === "CORPORATE_TIEUP") {
    if (btnCorporate) {
      btnCorporate.style.borderColor = "var(--primary-600)";
      btnCorporate.style.borderWidth = "2px";
    }
    if (btnWalkin) {
      btnWalkin.style.borderColor = "var(--border-subtle)";
      btnWalkin.style.borderWidth = "1px";
    }
    if (corpArea) corpArea.style.display = "block";
    if (badge) {
      badge.textContent = "Corporate / Tie-up";
      badge.className = "badge badge-primary";
    }
    if (allReceptionCorporateClients.length === 0) {
      loadReceptionCorporatePartners();
    }
  } else {
    if (btnWalkin) {
      btnWalkin.style.borderColor = "var(--primary-600)";
      btnWalkin.style.borderWidth = "2px";
    }
    if (btnCorporate) {
      btnCorporate.style.borderColor = "var(--border-subtle)";
      btnCorporate.style.borderWidth = "1px";
    }
    if (corpArea) corpArea.style.display = "none";
    if (badge) {
      badge.textContent = "Walk-in";
      badge.className = "badge badge-neutral";
    }
    const box = document.getElementById("regCorporateCreditBox");
    if (box) box.style.display = "none";
  }
}

function onRegCorporatePartnerSelect() {
  const select = document.getElementById("regCorporateClientSelect");
  const box = document.getElementById("regCorporateCreditBox");
  if (!select || !box) return;

  const clientId = parseInt(select.value, 10);
  if (!clientId) {
    box.style.display = "none";
    return;
  }

  const client = allReceptionCorporateClients.find(c => c.id === clientId);
  if (!client) {
    box.style.display = "none";
    return;
  }

  box.style.display = "block";
  document.getElementById("regCorpPartnerName").textContent = client.name;
  document.getElementById("regCorpCategoryBadge").textContent = client.category.replace(/_/g, " ");
  document.getElementById("regCorpAvailableCredit").textContent = `₹${client.available_credit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
  document.getElementById("regCorpUtilizedText").textContent = `Utilized: ₹${client.current_utilized_credit.toLocaleString('en-IN')} / Limit: ₹${client.monthly_credit_limit.toLocaleString('en-IN')} (${client.utilization_percentage}% utilized)`;
}

window.toggleCorporateCreditQuickView = toggleCorporateCreditQuickView;
window.onRegCategoryToggle = onRegCategoryToggle;
window.onRegCorporatePartnerSelect = onRegCorporatePartnerSelect;


async function handleBookAppointment(e) {
  e.preventDefault();
  if (!selectedPatient) {
    showToast("Please select a patient first from the list.", "warning");
    return;
  }

  const form = e.target;
  const doctorSelect = form.doctorSelect;
  const selectedDoctorOption = doctorSelect.options[doctorSelect.selectedIndex];
  const department = selectedDoctorOption.getAttribute("data-dept");

  const payload = {
    patient_id: selectedPatient.id,
    doctor_id: parseInt(doctorSelect.value, 10),
    department: department || "General Medicine",
    appointment_date: form.appointmentDate.value,
    time_slot: form.timeSlot.value,
    reason_for_visit: form.reasonForVisit.value || "OPD Consultation"
  };

  try {
    const appt = await apiFetch("/api/appointments/", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast(`Appointment booked successfully! Token #${appt.token_number}`, "success");
    
    // Save confirmation details for slip printing
    const docText = selectedDoctorOption.text || "";
    const docParts = docText.split(" - ");
    const docFee = docText.includes("₹") ? docText.split("₹")[1] : "500";
    
    window._lastConfirmedAppointment = {
      token_number: appt.token_number,
      patient_name: selectedPatient.full_name,
      patient_mrn: selectedPatient.mrn,
      patient_phone: selectedPatient.phone_number || "-",
      doctor_name: docParts[0] || "Doctor",
      doctor_dept: department || "General Medicine",
      consultation_fee: docFee,
      time_slot: appt.time_slot,
      appointment_date: appt.appointment_date
    };

    // Populate adorable modal
    const tokenBadge = document.getElementById("modalTokenBadge");
    if (tokenBadge) tokenBadge.innerText = `Token #${appt.token_number}`;
    const pName = document.getElementById("modalPatientName");
    if (pName) pName.innerText = selectedPatient.full_name;
    const pMrn = document.getElementById("modalPatientMrn");
    if (pMrn) pMrn.innerText = `MRN: ${selectedPatient.mrn}`;
    const dName = document.getElementById("modalDoctorName");
    if (dName) dName.innerText = docParts[0] || "Doctor";
    const dDept = document.getElementById("modalDoctorDept");
    if (dDept) dDept.innerText = department || "General Medicine";
    const sTime = document.getElementById("modalSlotTime");
    if (sTime) sTime.innerText = `${appt.time_slot} • ${appt.appointment_date}`;
    const cFee = document.getElementById("modalConsultFee");
    if (cFee) cFee.innerText = `₹${docFee}`;

    // Open adorable modal instead of browser alert
    openModal("appointmentConfirmedModal");
    
    form.reset();
    document.getElementById("selectedPatientBanner").style.display = "none";
    selectedPatient = null;
    loadReceptionAnalytics();
  } catch (err) {}
}


window._receptionAlertsCache = [];
window._receptionAlertsOpen = false;

async function loadReceptionAnalytics() {
  try {
    const data = await apiFetch("/api/appointments/analytics");
    if (!data) return;

    // 1. Update Top KPI Cards
    const kpis = data.kpis || {};
    const kpiRecAppts = document.getElementById("kpiRecAppts");
    const kpiRecWaiting = document.getElementById("kpiRecWaiting");
    const kpiRecCompleted = document.getElementById("kpiRecCompleted");
    const kpiRecPatients = document.getElementById("kpiRecPatients");

    if (kpiRecAppts) kpiRecAppts.innerText = `${kpis.today_appointments || 0} visits`;
    if (kpiRecWaiting) kpiRecWaiting.innerText = `${kpis.checked_in_waiting || 0} waiting`;
    if (kpiRecCompleted) kpiRecCompleted.innerText = `${kpis.completed_consultations || 0} finished`;
    if (kpiRecPatients) kpiRecPatients.innerText = `${(kpis.total_patients || 0).toLocaleString()} patients`;

    // 2. Render Receptionist Alerts Dropdown
    renderReceptionAlerts(data.alerts || []);

    // 3. Render Doctor Capacity Bars
    renderDoctorCapacityBars(data.doctor_capacity || []);

  } catch (err) {
    console.warn("Could not load reception analytics:", err);
  }
}

function renderReceptionAlerts(alerts) {
  const container = document.getElementById("receptionAlertsContainer");
  if (!container) return;

  window._receptionAlertsCache = alerts || [];

  if (!alerts || alerts.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  container.style.display = "block";
  container.innerHTML = `
    <div style="background:rgba(245, 158, 11, 0.08); border:1px solid rgba(245, 158, 11, 0.35); border-radius:var(--radius-md); padding:0.85rem 1.15rem; margin-bottom:1.5rem;">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem; cursor:pointer;" onclick="toggleReceptionAlertsDropdown(event)">
        <div style="display:flex; align-items:center; gap:0.6rem;">
          <span style="display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:50%; background:rgba(245, 158, 11, 0.2); color:#b45309;">
            <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </span>
          <div>
            <strong style="color:#b45309; font-size:var(--font-sm);">
              ${alerts.length} Front-Desk Alert${alerts.length > 1 ? 's' : ''} &amp; Capacity Warning${alerts.length > 1 ? 's' : ''}
            </strong>
            <span style="font-size:var(--font-xs); color:var(--text-muted); margin-left:0.5rem;">(OPD flow &amp; slot guidance)</span>
          </div>
        </div>

        <div style="display:flex; align-items:center; gap:0.5rem;" onclick="event.stopPropagation()">
          <button type="button" class="btn btn-outline btn-sm" id="recAlertsBtn" onclick="toggleReceptionAlertsDropdown(event)" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:var(--font-xs); background:#fff; padding:0.3rem 0.65rem;">
            <span id="recAlertsBtnText">${window._receptionAlertsOpen ? 'Collapse Warnings' : `Expand Warnings (${alerts.length})`}</span>
            <svg id="recAlertsChevron" class="icon icon-sm" style="transition:transform 0.2s ease; transform:${window._receptionAlertsOpen ? 'rotate(180deg)' : 'rotate(0deg)'};" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
      </div>

      <div id="recAlertsContent" style="display:${window._receptionAlertsOpen ? 'block' : 'none'}; margin-top:0.75rem; padding-top:0.75rem; border-top:1px solid rgba(245, 158, 11, 0.25);">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem; margin-bottom:0.6rem; flex-wrap:wrap;">
          <input type="text" class="form-control form-control-sm" placeholder="Filter alerts..." oninput="filterReceptionAlerts(this.value)" style="max-width:280px; font-size:var(--font-xs); background:#fff; padding:0.3rem 0.6rem;">
          <span id="recAlertsCountLabel" style="font-size:var(--font-xs); color:var(--text-muted);">Max 260px scrollable view</span>
        </div>

        <div id="recAlertsList" style="max-height:260px; overflow-y:auto; display:flex; flex-direction:column; gap:0.4rem; padding-right:0.3rem;">
          ${renderRecAlertItems(alerts)}
        </div>
      </div>
    </div>
  `;
}

function renderRecAlertItems(items) {
  if (!items || items.length === 0) {
    return `<div style="text-align:center; padding:1rem; font-size:var(--font-xs); color:var(--text-muted); background:#fff; border-radius:var(--radius-sm);">No active front-desk alerts.</div>`;
  }
  return items.map(a => `
    <div style="display:flex; justify-content:space-between; align-items:center; background:#fff; padding:0.45rem 0.8rem; border-radius:var(--radius-sm); border:1px solid rgba(245, 158, 11, 0.2); font-size:var(--font-xs); gap:0.5rem; flex-wrap:wrap;">
      <div style="display:flex; align-items:center; gap:0.5rem;">
        <span class="badge ${a.severity === 'danger' ? 'badge-danger' : 'badge-warning'}" style="font-size:0.7rem; padding:0.15rem 0.45rem;">
          ${a.type.replace('_', ' ')}
        </span>
        <span style="color:var(--text-main);">${a.message}</span>
      </div>
    </div>
  `).join("");
}

function toggleReceptionAlertsDropdown(e) {
  if (e) e.stopPropagation();
  window._receptionAlertsOpen = !window._receptionAlertsOpen;
  const content = document.getElementById("recAlertsContent");
  const btnText = document.getElementById("recAlertsBtnText");
  const chevron = document.getElementById("recAlertsChevron");

  if (content) content.style.display = window._receptionAlertsOpen ? "block" : "none";
  if (btnText) btnText.innerText = window._receptionAlertsOpen ? "Collapse Warnings" : `Expand Warnings (${(window._receptionAlertsCache || []).length})`;
  if (chevron) chevron.style.transform = window._receptionAlertsOpen ? "rotate(180deg)" : "rotate(0deg)";
}

function filterReceptionAlerts(query) {
  const q = (query || "").toLowerCase().trim();
  const list = document.getElementById("recAlertsList");
  if (!list) return;
  const filtered = (window._receptionAlertsCache || []).filter(a => (a.message || "").toLowerCase().includes(q) || (a.type || "").toLowerCase().includes(q));
  list.innerHTML = renderRecAlertItems(filtered);
}

function renderDoctorCapacityBars(docCapacities) {
  const card = document.getElementById("doctorCapacityCard");
  const container = document.getElementById("doctorCapacityBars");
  if (!container || !card) return;

  if (!docCapacities || docCapacities.length === 0) {
    card.style.display = "none";
    return;
  }

  card.style.display = "block";
  container.innerHTML = docCapacities.map(d => {
    let barColor = "#10b981"; // Emerald
    let badgeClass = "badge-success";
    if (d.status === "FULL") {
      barColor = "#ef4444"; // Red
      badgeClass = "badge-danger";
    } else if (d.status === "NEAR_CAPACITY") {
      barColor = "#f59e0b"; // Amber
      badgeClass = "badge-warning";
    }

    return `
      <div style="background:var(--bg-surface-alt, #f8fafc); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:0.75rem 0.9rem;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
          <div>
            <strong style="font-size:var(--font-sm);">${d.doctor_name}</strong>
            <small style="color:var(--text-muted); display:block;">${d.department}</small>
          </div>
          <span class="badge ${badgeClass}" style="font-size:0.7rem;">
            ${d.available_slots} slot${d.available_slots !== 1 ? 's' : ''} left
          </span>
        </div>
        <div style="width:100%; height:6px; background:#e2e8f0; border-radius:3px; overflow:hidden; margin:0.4rem 0;">
          <div style="width:${d.utilization_pct}%; height:100%; background:${barColor}; border-radius:3px; transition:width 0.4s ease;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:var(--font-xs); color:var(--text-muted);">
          <span>${d.booked_slots} booked of ${d.max_slots}</span>
          <span>${d.utilization_pct}% utilized</span>
        </div>
      </div>
    `;
  }).join("");
}

// ----------------------------------------------------
// Printable Token Slip for Confirmed Appointments
// ----------------------------------------------------
function printAppointmentTokenSlip() {
  const appt = window._lastConfirmedAppointment;
  if (!appt) {
    showToast("No active appointment token to print", "warning");
    return;
  }

  const printWindow = window.open("", "_blank", "width=400,height=550");
  if (!printWindow) {
    window.print();
    return;
  }

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>OPD Token #${appt.token_number} - City Hospital</title>
      <style>
        body {
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          margin: 0;
          padding: 24px;
          color: #1e293b;
          text-align: center;
        }
        .header {
          border-bottom: 2px dashed #94a3b8;
          padding-bottom: 12px;
          margin-bottom: 16px;
        }
        .hospital-name {
          font-size: 18px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .token-box {
          margin: 16px auto;
          padding: 12px 24px;
          border: 2px solid #059669;
          border-radius: 12px;
          background: #ecfdf5;
          display: inline-block;
        }
        .token-title {
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          color: #059669;
          letter-spacing: 0.05em;
        }
        .token-num {
          font-size: 38px;
          font-weight: 900;
          color: #059669;
          line-height: 1.1;
        }
        .details-table {
          width: 100%;
          margin: 16px 0;
          border-collapse: collapse;
          text-align: left;
          font-size: 13px;
        }
        .details-table td {
          padding: 6px 0;
          border-bottom: 1px solid #f1f5f9;
        }
        .details-table td.label {
          color: #64748b;
          font-weight: 500;
        }
        .details-table td.val {
          font-weight: 700;
          text-align: right;
        }
        .footer {
          margin-top: 20px;
          font-size: 11px;
          color: #64748b;
          border-top: 1px dashed #cbd5e1;
          padding-top: 12px;
        }
        @media print {
          body { padding: 0; }
          .no-print { display: none; }
        }
      </style>
    </head>
    <body>
      <div class="header">
        <div class="hospital-name">City Hospital</div>
        <div style="font-size:11px; color:#64748b; margin-top:2px;">Medical District • OPD Consultation Queue</div>
      </div>

      <div class="token-box">
        <div class="token-title">Today's Token</div>
        <div class="token-num">#${appt.token_number}</div>
      </div>

      <table class="details-table">
        <tr>
          <td class="label">Patient:</td>
          <td class="val">${appt.patient_name}</td>
        </tr>
        <tr>
          <td class="label">MRN:</td>
          <td class="val">${appt.patient_mrn}</td>
        </tr>
        <tr>
          <td class="label">Consulting Doctor:</td>
          <td class="val">${appt.doctor_name}</td>
        </tr>
        <tr>
          <td class="label">Department:</td>
          <td class="val">${appt.doctor_dept}</td>
        </tr>
        <tr>
          <td class="label">Slot &amp; Date:</td>
          <td class="val">${appt.time_slot}<br><small style="color:#64748b;">${appt.appointment_date}</small></td>
        </tr>
        <tr>
          <td class="label">Consultation Fee:</td>
          <td class="val">₹${appt.consultation_fee}</td>
        </tr>
      </table>

      <div class="footer">
        <div>Please wait in the OPD lounge until your token number is displayed.</div>
        <div style="margin-top:4px;">Printed on: ${new Date().toLocaleTimeString()}</div>
      </div>

      <div class="no-print" style="margin-top:20px;">
        <button onclick="window.print()" style="padding:8px 16px; font-weight:bold; cursor:pointer;">Print Slip</button>
        <button onclick="window.close()" style="padding:8px 16px; margin-left:8px; cursor:pointer;">Close</button>
      </div>

      <script>
        window.onload = function() {
          setTimeout(function() { window.print(); }, 400);
        };
      </script>
    </body>
    </html>
  `;

  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
}

// ----------------------------------------------------
// Diagnostic Reports Dispatch & Delivery Desk
// ----------------------------------------------------
window._dispatchQueueCache = [];

async function loadDispatchQueue() {
  const tbody = document.getElementById("dispatchTableBody");
  if (!tbody) return;

  try {
    const data = await apiFetch("/api/lab/dispatch-queue");
    window._dispatchQueueCache = data || [];
    renderDispatchQueue(window._dispatchQueueCache);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:1.5rem; color:#ef4444;">Failed to load diagnostic dispatch queue.</td></tr>`;
  }
}

function filterDispatchQueue() {
  const query = (document.getElementById("dispatchSearchInput")?.value || "").toLowerCase().trim();
  if (!query) {
    renderDispatchQueue(window._dispatchQueueCache);
    return;
  }
  const filtered = window._dispatchQueueCache.filter(item => {
    return (item.patient?.name || "").toLowerCase().includes(query) ||
           (item.patient?.mrn || "").toLowerCase().includes(query) ||
           (item.test_name || "").toLowerCase().includes(query) ||
           (item.sample_barcode || "").toLowerCase().includes(query) ||
           (item.doctor?.name || "").toLowerCase().includes(query);
  });
  renderDispatchQueue(filtered);
}

function renderDispatchQueue(items) {
  const tbody = document.getElementById("dispatchTableBody");
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:2rem; color:var(--text-muted);">No diagnostic orders in queue.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(item => {
    // 1. Billing badge & state
    let billBadge = `<span class="badge badge-success" style="font-weight:600;">✓ PAID</span>`;
    let billRemindBtn = "";
    if (!item.billing?.is_paid) {
      billBadge = `
        <div>
          <span class="badge badge-danger" style="font-weight:600;">UNPAID (₹${item.billing?.balance?.toFixed(2) || '500.00'})</span>
          <div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px;">Inv: ${item.billing?.invoice_number || '-'}</div>
        </div>
      `;
      billRemindBtn = `
        <button class="btn btn-outline btn-sm" style="font-size:0.72rem; padding:0.25rem 0.5rem; border-color:#f59e0b; color:#d97706; margin-top:4px;" 
                onclick="sendBillingReminder(${item.order_id}, '${escapeJs(item.patient?.name)}', '${escapeJs(item.patient?.phone)}', ${item.billing?.balance || 500})">
          🔔 Notify Patient
        </button>
      `;
    }

    // 2. Doctor authentication badge
    let docBadge = `<span class="badge badge-neutral">AWAITING TECH</span>`;
    if (item.doctor_approval_status === "APPROVED") {
      docBadge = `<span class="badge badge-success" style="font-weight:600;">✓ APPROVED</span><div style="font-size:0.7rem; color:#059669; margin-top:2px;">Signed by Doctor</div>`;
    } else if (item.doctor_approval_status === "PENDING_REVIEW") {
      docBadge = `<span class="badge badge-info" style="font-weight:600;">⏳ AWAITING DOCTOR</span><div style="font-size:0.7rem; color:#2563eb; margin-top:2px;">Pending Sign-Off</div>`;
    } else if (item.doctor_approval_status === "REVISION_REQUESTED") {
      docBadge = `
        <span class="badge badge-warning" style="font-weight:600;">⚠️ REVISION NEEDED</span>
        <div style="font-size:0.7rem; color:#d97706; margin-top:2px;" title="${escapeJs(item.doctor_notes)}">In Lab Tech Queue</div>
      `;
    }

    // 3. Dispatch Delivery status
    let dispatchStatusHtml = "";
    if (item.dispatch?.status === "DISPATCHED") {
      dispatchStatusHtml = `
        <div style="font-size:0.78rem;">
          <strong style="color:#059669;">✓ Dispatched</strong>
          <div style="color:var(--text-muted); font-size:0.72rem;">Via ${item.dispatch.channels || 'WhatsApp'}</div>
          <div style="color:#94a3b8; font-size:0.68rem;">${item.dispatch.dispatched_at || ''}</div>
        </div>
      `;
    } else if (item.dispatch?.can_dispatch) {
      dispatchStatusHtml = `<span class="badge badge-success" style="background:#ecfdf5; color:#059669; border:1px solid #10b981;">Ready to Send</span>`;
    } else {
      let reasons = [];
      if (!item.billing?.is_paid) reasons.push("Bill Unpaid");
      if (item.doctor_approval_status !== "APPROVED") reasons.push("Doctor Pending");
      dispatchStatusHtml = `<span style="font-size:0.75rem; color:#ef4444; font-weight:500;">🔒 Locked (${reasons.join(", ")})</span>`;
    }

    // 4. Action button
    let actionButtons = `
      <div style="display:flex; flex-direction:column; gap:0.35rem; align-items:flex-start;">
        <button class="btn btn-sm ${item.dispatch?.can_dispatch ? 'btn-primary' : 'btn-outline'}" 
                style="font-size:0.78rem; padding:0.35rem 0.65rem;"
                ${!item.dispatch?.can_dispatch ? 'disabled title="Requires doctor approval & paid bill"' : ''}
                onclick="openDispatchModal(${item.order_id}, '${escapeJs(item.patient?.phone)}', '${escapeJs(item.patient?.email)}', '${escapeJs(item.patient?.name)}', '${escapeJs(item.test_name)}')">
          🚀 Dispatch Report
        </button>
        <a href="/api/lab/reports/${item.order_id}/pdf" target="_blank" class="btn btn-outline btn-sm" style="font-size:0.72rem; padding:0.25rem 0.5rem; text-decoration:none;">
          📄 View PDF
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
          <div style="font-size:0.72rem; color:#64748b;">📞 ${item.patient?.phone || '-'}</div>
        </td>
        <td>
          <strong>${item.test_name}</strong>
          <div><span class="badge badge-neutral" style="font-size:0.7rem;">${item.modality || item.department}</span></div>
        </td>
        <td>
          <div style="font-weight:600; color:var(--text-main);">${item.doctor?.name || 'Doctor'}</div>
          <div style="font-size:0.72rem; color:var(--text-muted);">${item.doctor?.department || ''}</div>
        </td>
        <td>
          ${billBadge}
          ${billRemindBtn}
        </td>
        <td>
          ${docBadge}
        </td>
        <td>
          ${dispatchStatusHtml}
        </td>
        <td>
          ${actionButtons}
        </td>
      </tr>
    `;
  }).join("");
}

function escapeJs(str) {
  if (!str) return "";
  return String(str).replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function openDispatchModal(orderId, phone, email, patientName, testName) {
  document.getElementById("dispatchOrderId").value = orderId;
  const pInput = document.getElementById("dispatchPhoneInput");
  if (pInput) pInput.value = phone && phone !== "-" ? phone : "";
  const eInput = document.getElementById("dispatchEmailInput");
  if (eInput) eInput.value = email || "";
  openModal("dispatchChannelsModal");
}

async function submitDispatchReport() {
  const orderId = document.getElementById("dispatchOrderId").value;
  const chkWA = document.getElementById("chkWhatsApp").checked;
  const chkEmail = document.getElementById("chkEmail").checked;
  const chkSMS = document.getElementById("chkSMS").checked;

  const channels = [];
  if (chkWA) channels.push("WHATSAPP");
  if (chkEmail) channels.push("EMAIL");
  if (chkSMS) channels.push("SMS");

  if (channels.length === 0) {
    showToast("Please select at least one dispatch channel (WhatsApp, Email, or SMS)", "warning");
    return;
  }

  const phone = document.getElementById("dispatchPhoneInput").value;
  const email = document.getElementById("dispatchEmailInput").value;

  const btn = document.getElementById("btnSubmitDispatch");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Dispatching...";
  }

  try {
    const res = await apiFetch(`/api/lab/orders/${orderId}/dispatch`, {
      method: "POST",
      body: JSON.stringify({
        channels: channels,
        recipient_phone: phone,
        recipient_email: email
      })
    });

    closeModal("dispatchChannelsModal");
    showToast(res.message || "Report dispatched successfully!", "success");

    // If WhatsApp was selected, optionally open pre-formatted web link in background/tab
    if (chkWA && res.whatsapp_url) {
      window.open(res.whatsapp_url, "_blank");
    }

    loadDispatchQueue();
  } catch (err) {
    // Toast handles error
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Send Verified Report Now";
    }
  }
}

async function sendBillingReminder(orderId, patientName, phone, balance) {
  try {
    const res = await apiFetch(`/api/lab/orders/${orderId}/notify-billing`, {
      method: "POST"
    });
    showToast(res.message || `Payment reminder sent to ${patientName}`, "success");
    if (res.whatsapp_url) {
      window.open(res.whatsapp_url, "_blank");
    }
  } catch (err) {}
}


