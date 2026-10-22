/**
 * AegisHealth Diagnostic Services & PACS Radiology Workstation
 * Handles Pathology Multi-Parameter Analysis, Digital PACS Image Viewer/Editor,
 * Test Template Management, and Specimen Workflows.
 */

let currentTab = "ALL";
let currentStatusFilter = "";
let searchQuery = "";

let activeOrderId = null;
let radActiveOrderId = null;
let activeOrderData = null;

let allOrders = [];
let allTemplates = [];
let allPatients = [];

const escapeHtml = val => String(val ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

document.addEventListener("DOMContentLoaded", () => {
  initPacsCanvas();
  refreshDiagnosticData();
  loadAllTemplatesCatalog();

  const filterSelect = document.getElementById("diagnosticStatusFilter");
  if (filterSelect) {
    filterSelect.addEventListener("change", (e) => handleStatusFilterChange(e.target.value));
  }

  const labForm = document.getElementById("labResultForm");
  if (labForm) {
    labForm.addEventListener("submit", handleSaveLabResult);
  }

  const radForm = document.getElementById("radiologyReportForm");
  if (radForm) {
    radForm.addEventListener("submit", handleSaveRadiologyReport);
  }

  const singleInput = document.getElementById("resultValueInput");
  if (singleInput) {
    singleInput.addEventListener("input", (e) => {
      checkSingleBoundaryAlert(e.target.value);
    });
  }
});

// ============================================================================
// NAVIGATION & WORKLIST
// ============================================================================

function switchDiagnosticTab(tab) {
  currentTab = tab;
  const btnAll = document.getElementById("tabBtnAll");
  const btnLab = document.getElementById("tabBtnLab");
  const btnRad = document.getElementById("tabBtnRad");
  const btnTmpl = document.getElementById("tabBtnTmpl");

  [btnAll, btnLab, btnRad, btnTmpl].forEach(b => {
    if (b) {
      b.classList.remove("btn-primary");
      b.classList.add("btn-ghost");
    }
  });

  const activeBtn = tab === "ALL" ? btnAll : tab === "Laboratory" ? btnLab : tab === "Radiology" ? btnRad : btnTmpl;
  if (activeBtn) {
    activeBtn.classList.remove("btn-ghost");
    activeBtn.classList.add("btn-primary");
  }

  const worklistCard = document.getElementById("worklistCard");
  const templateStudioCard = document.getElementById("templateStudioCard");
  const filtersRow = document.getElementById("worklistFiltersRow");

  if (tab === "TEMPLATES") {
    if (worklistCard) worklistCard.style.display = "none";
    if (templateStudioCard) templateStudioCard.style.display = "block";
    if (filtersRow) filtersRow.style.display = "none";
    loadTemplatesTable();
  } else {
    if (worklistCard) worklistCard.style.display = "block";
    if (templateStudioCard) templateStudioCard.style.display = "none";
    if (filtersRow) filtersRow.style.display = "flex";

    const titleEl = document.getElementById("worklistSectionTitle");
    if (titleEl) {
      titleEl.textContent = tab === "Radiology" ? "Radiology & Imaging Worklist" :
                            tab === "Laboratory" ? "Clinical Pathology & Biochemistry Worklist" :
                            "Diagnostic Investigations Worklist";
    }
    renderWorklistTable();
  }
}

async function refreshDiagnosticData() {
  await Promise.allSettled([
    loadDiagnosticWorklist(),
    loadDiagnosticAnalytics()
  ]);
}

async function loadDiagnosticWorklist() {
  const tbody = document.getElementById("labWorklistBody");
  if (!tbody) return;

  try {
    const orders = await apiFetch("/api/lab/worklist");
    allOrders = orders || [];
    renderWorklistTable();
  } catch (err) {
    console.error("Failed to load worklist:", err);
  }
}

function handleStatusFilterChange(val) {
  currentStatusFilter = val;
  renderWorklistTable();
}

function handleSearchWorklist(val) {
  searchQuery = (val || "").toLowerCase().trim();
  renderWorklistTable();
}

function renderWorklistTable() {
  const tbody = document.getElementById("labWorklistBody");
  const countBadge = document.getElementById("worklistCountBadge");
  if (!tbody) return;

  let filtered = allOrders.filter(ord => {
    // 1. Department tab filter
    if (currentTab === "Laboratory" && ord.department === "Radiology") return false;
    if (currentTab === "Radiology" && ord.department !== "Radiology") return false;

    // 2. Status filter
    if (currentStatusFilter && ord.sample_status !== currentStatusFilter) return false;

    // 3. Search query filter
    if (searchQuery) {
      const match = (ord.patient_name || "").toLowerCase().includes(searchQuery) ||
                    (ord.patient_mrn || "").toLowerCase().includes(searchQuery) ||
                    (ord.test_name || "").toLowerCase().includes(searchQuery) ||
                    (ord.sample_barcode || "").toLowerCase().includes(searchQuery) ||
                    (ord.department || "").toLowerCase().includes(searchQuery);
      if (!match) return false;
    }
    return true;
  });

  if (countBadge) {
    countBadge.textContent = `${filtered.length} order${filtered.length === 1 ? '' : 's'}`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align:center; color:var(--text-muted); padding:2.5rem 1rem;">
          No diagnostic investigations found matching this selection.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(ord => {
    const isRad = ord.department === "Radiology" || Boolean(ord.modality);
    const hasScan = Boolean(ord.annotated_image_url || ord.image_url);
    const scanThumb = ord.annotated_image_url || ord.image_url;

    // Status label & badge
    let statusClass = "badge-warning";
    let statusLabel = isRad ? "Scheduled / Waiting" : "Waiting for Sample";
    if (ord.sample_status === "SAMPLE_COLLECTED") {
      statusClass = "badge-info";
      statusLabel = isRad ? "In Imaging Suite" : "Specimen Received";
    } else if (ord.sample_status === "COMPLETED") {
      statusClass = "badge-success";
      statusLabel = "Report Verified";
    }

    return `
      <tr>
        <td>
          <div style="font-weight:600; color:var(--text-main);">${escapeHtml(ord.test_name)}</div>
          <div style="display:flex; align-items:center; gap:0.35rem; margin-top:0.2rem;">
            <span class="badge ${isRad ? 'badge-primary' : 'badge-secondary'}" style="font-size:0.7rem;">${escapeHtml(ord.department)}</span>
            ${ord.modality ? `<span class="badge badge-info" style="font-size:0.7rem; font-weight:700;">${escapeHtml(ord.modality)}</span>` : ''}
          </div>
        </td>
        <td>
          <strong>${escapeHtml(ord.patient_name)}</strong>
          <div style="font-size:var(--font-xs); color:var(--text-muted);">
            MRN: ${escapeHtml(ord.patient_mrn)} &bull; ${escapeHtml(ord.patient_age)}Y/${escapeHtml(ord.patient_gender)}
          </div>
        </td>
        <td>
          <div style="font-size:var(--font-sm);">${escapeHtml(ord.sample_type)}</div>
          <div style="font-family:monospace; font-size:0.75rem; color:var(--primary-700); font-weight:600;">
            ${escapeHtml(ord.sample_barcode || 'Unbarcoded')}
          </div>
        </td>
        <td>
          <div style="font-size:var(--font-sm);">Dr. ${escapeHtml(ord.doctor_name)}</div>
          ${ord.clinical_notes ? `<div style="font-size:0.75rem; color:var(--text-muted); max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(ord.clinical_notes)}">${escapeHtml(ord.clinical_notes)}</div>` : ''}
        </td>
        <td>
          <span class="badge ${statusClass}">${statusLabel}</span>
          ${ord.doctor_approval_status === 'REVISION_REQUESTED' ? `
            <br><span class="badge badge-warning" style="margin-top:0.25rem; font-size:0.68rem; background:#fef3c7; color:#92400e; border:1px solid #fde68a;" title="${escapeHtml(ord.doctor_notes)}">⚠️ Doctor Revision Required</span>
          ` : ord.doctor_approval_status === 'APPROVED' ? `
            <br><span class="badge badge-success" style="margin-top:0.25rem; font-size:0.68rem;">✓ Doctor Signed</span>
          ` : ''}
          ${ord.is_abnormal ? `<br><span class="badge badge-danger" style="margin-top:0.25rem; font-size:0.65rem;">Outside Normal Range</span>` : ''}
        </td>

        <td>
          ${isRad ? (
            hasScan ? `
              <div style="display:flex; align-items:center; gap:0.4rem; cursor:pointer;" onclick="openRadiologyStudio(${ord.id})">
                <img src="${scanThumb}" style="width:36px; height:36px; object-fit:cover; border-radius:4px; border:1px solid #0284c7; background:#000;" alt="Scan">
                <span style="font-size:0.75rem; color:#0284c7; font-weight:600;">${ord.annotated_image_url ? 'Annotated' : 'Scan'}</span>
              </div>
            ` : `<span style="font-size:0.75rem; color:var(--text-faint);">No scan yet</span>`
          ) : (
            ord.result_value ? `
              <div style="font-weight:600; font-size:var(--font-sm);">${escapeHtml(ord.result_value)} ${escapeHtml(ord.unit)}</div>
              ${ord.normal_range && ord.normal_range !== '-' ? `<div style="font-size:0.7rem; color:var(--text-muted);">Ref: ${escapeHtml(ord.normal_range)}</div>` : ''}
            ` : `<span style="font-size:0.75rem; color:var(--text-faint);">Not entered</span>`
          )}
        </td>
        <td style="text-align:right;">
          <div style="display:inline-flex; align-items:center; gap:0.4rem;">
            ${ord.sample_status === 'ORDERED' ? `
              <button class="btn btn-outline btn-sm" onclick="markSampleCollected(${ord.id}, ${isRad})" style="font-size:0.75rem; padding:0.25rem 0.5rem;">
                ${isRad ? 'Mark In Suite' : 'Collect Sample'}
              </button>
            ` : ''}

            ${isRad ? `
              <button class="btn btn-primary btn-sm" onclick="openRadiologyStudio(${ord.id})" style="font-size:0.75rem; padding:0.25rem 0.55rem; background:#1e40af; border-color:#1e40af;">
                ${ord.sample_status === 'COMPLETED' ? 'Edit PACS Report' : 'Open PACS Studio'}
              </button>
            ` : `
              <button class="btn ${ord.sample_status === 'COMPLETED' ? 'btn-outline' : 'btn-primary'} btn-sm" onclick="openLabResultModal(${ord.id})" style="font-size:0.75rem; padding:0.25rem 0.55rem;">
                ${ord.sample_status === 'COMPLETED' ? 'Edit Report' : 'Enter Report'}
              </button>
            `}

            ${ord.sample_status === 'COMPLETED' ? `
              <button class="btn btn-ghost btn-sm" onclick="downloadOrderPdf(${ord.id})" title="Print / Download PDF" style="font-size:0.75rem; padding:0.25rem 0.4rem; color:var(--primary-700);">
                📄 PDF
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function markSampleCollected(orderId, isRadiology = false) {
  try {
    const res = await apiFetch(`/api/lab/orders/${orderId}/sample-collected`, {
      method: "PATCH"
    });
    showToast(isRadiology ? `Patient received in imaging room! Barcode: ${res.barcode}` : `Specimen accessioned! Barcode: ${res.barcode}`, "success");
    refreshDiagnosticData();
  } catch (err) {
    showToast("Failed to update specimen status", "error");
  }
}

function downloadOrderPdf(orderId) {
  if (!orderId) return;
  window.open(`/api/lab/reports/${orderId}/pdf`, "_blank");
}

// ============================================================================
// MODAL 1: LAB MULTI-PARAMETER & SINGLE REPORT ENTRY
// ============================================================================

async function openLabResultModal(orderId) {
  activeOrderId = orderId;
  const form = document.getElementById("labResultForm");
  if (form) form.reset();

  const boundaryContainer = document.getElementById("boundaryAlertContainer");
  if (boundaryContainer) {
    boundaryContainer.style.display = "none";
    boundaryContainer.innerHTML = "";
  }

  try {
    const ord = await apiFetch(`/api/lab/orders/${orderId}`);
    activeOrderData = ord;

    document.getElementById("modalOrderId").value = ord.id;
    document.getElementById("modalTestTitle").innerText = `${ord.test_name}`;
    const docPrefix = (ord.doctor_name || "").startsWith("Dr.") ? "" : "Dr. ";
    document.getElementById("modalPatientSubtitle").textContent = `Patient: ${ord.patient_name} (MRN: ${ord.patient_mrn}) • Ref Doctor: ${docPrefix}${ord.doctor_name}`;
    document.getElementById("modalBarcodeBadge").innerText = ord.sample_barcode || "N/A";
    document.getElementById("modalNormalRange").innerText = `Normal Range: ${ord.normal_range || "Configured in schema"} ${ord.unit || ""}`;

    // Doctor revision banner
    if (ord.doctor_approval_status === "REVISION_REQUESTED" && ord.doctor_notes) {
      if (boundaryContainer) {
        boundaryContainer.style.display = "block";
        boundaryContainer.innerHTML = `
          <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:0.85rem 1rem; margin-bottom:1rem; color:#92400e;">
            <strong style="display:flex; align-items:center; gap:0.4rem; font-size:0.875rem;">
              <span>⚠️ CLINICAL REVISION REQUESTED BY CONSULTING DOCTOR:</span>
            </strong>
            <p style="margin:0.35rem 0 0 0; font-size:0.85rem; font-weight:600; line-height:1.4;">"${escapeHtml(ord.doctor_notes)}"</p>
            <small style="color:#b45309; display:block; margin-top:0.4rem;">Please make requested changes to parameter values or technician notes, then submit to return to doctor for final sign-off.</small>
          </div>
        `;
      }
    }

    document.getElementById("techNotesInput").value = ord.technician_notes || "";

    document.getElementById("panicFlagSelect").value = ord.panic_flag || "NORMAL";
    document.getElementById("isAbnormalCheckbox").checked = Boolean(ord.is_abnormal);

    const pdfBtn = document.getElementById("labPdfBtn");
    if (pdfBtn) pdfBtn.style.display = ord.sample_status === "COMPLETED" ? "inline-block" : "none";

    // Check if multi-parameter test
    const multiSection = document.getElementById("multiParamSection");
    const singleSection = document.getElementById("singleParamSection");
    const multiTbody = document.getElementById("multiParamTableBody");

    let paramsSchema = [];
    if (ord.parameters_json) {
      try {
        paramsSchema = typeof ord.parameters_json === "string" ? JSON.parse(ord.parameters_json) : ord.parameters_json;
      } catch (e) {}
    }

    // Existing parameter results
    let savedParams = [];
    if (ord.parameter_results) {
      try {
        savedParams = typeof ord.parameter_results === "string" ? JSON.parse(ord.parameter_results) : ord.parameter_results;
      } catch (e) {}
    }

    if (paramsSchema && paramsSchema.length > 0) {
      multiSection.style.display = "block";
      singleSection.style.display = "none";

      const savedMap = new Map(savedParams.map(p => [p.name, p]));

      multiTbody.innerHTML = paramsSchema.map((param, idx) => {
        const saved = savedMap.get(param.name);
        const val = saved ? saved.value : (param.default_val || "");
        const flag = saved ? saved.flag : "NORMAL";

        return `
          <tr data-param-row="${idx}">
            <td style="font-weight:600;">${escapeHtml(param.name)}</td>
            <td>
              <input type="text" class="form-control form-control-sm multi-param-val"
                     data-name="${escapeHtml(param.name)}"
                     data-unit="${escapeHtml(param.unit || '')}"
                     data-range="${escapeHtml(param.range || '')}"
                     value="${escapeHtml(val)}"
                     placeholder="${escapeHtml(param.range || '')}"
                     oninput="handleMultiParamInput(this, ${idx})">
            </td>
            <td style="color:var(--text-muted); font-size:0.75rem;">${escapeHtml(param.unit || '-')}</td>
            <td style="color:var(--text-muted); font-size:0.75rem;">${escapeHtml(param.range || '-')}</td>
            <td>
              <span id="paramFlagBadge_${idx}" class="badge ${flag.includes('HIGH') || flag.includes('LOW') ? 'badge-danger' : 'badge-secondary'}" style="font-size:0.7rem;">
                ${flag}
              </span>
            </td>
          </tr>
        `;
      }).join("");

    } else {
      multiSection.style.display = "none";
      singleSection.style.display = "block";
      document.getElementById("resultValueInput").value = ord.result_value || "";
      checkSingleBoundaryAlert(ord.result_value || "");
    }

    openModal("labResultModal");
  } catch (err) {
    showToast("Failed to load investigation details", "error");
  }
}

function handleMultiParamInput(inputEl, idx) {
  const val = parseFloat((inputEl.value || "").trim());
  const rangeStr = inputEl.dataset.range || "";
  const badge = document.getElementById(`paramFlagBadge_${idx}`);
  if (!badge) return;

  if (isNaN(val) || !rangeStr) {
    badge.className = "badge badge-secondary";
    badge.textContent = "NORMAL";
    return;
  }

  const rangeMatch = rangeStr.match(/([\d\.]+)\s*-\s*([\d\.]+)/);
  const lessMatch = rangeStr.match(/<\s*([\d\.]+)/);
  const greaterMatch = rangeStr.match(/>\s*([\d\.]+)/);

  let flag = "NORMAL";
  let isOut = false;

  if (rangeMatch) {
    const min = parseFloat(rangeMatch[1]);
    const max = parseFloat(rangeMatch[2]);
    if (val < min) { flag = "LOW"; isOut = true; }
    else if (val > max) { flag = "HIGH"; isOut = true; }
  } else if (lessMatch) {
    const max = parseFloat(lessMatch[1]);
    if (val >= max) { flag = "HIGH"; isOut = true; }
  } else if (greaterMatch) {
    const min = parseFloat(greaterMatch[1]);
    if (val <= min) { flag = "LOW"; isOut = true; }
  }

  badge.textContent = flag;
  if (isOut) {
    badge.className = "badge badge-danger";
    document.getElementById("isAbnormalCheckbox").checked = true;
    document.getElementById("panicFlagSelect").value = flag === "HIGH" ? "CRITICAL HIGH" : "CRITICAL LOW";
  } else {
    badge.className = "badge badge-secondary";
  }
}

function checkSingleBoundaryAlert(valueStr) {
  const alertContainer = document.getElementById("boundaryAlertContainer");
  const abnormalCheckbox = document.getElementById("isAbnormalCheckbox");
  if (!alertContainer || !activeOrderData) return;

  const rangeStr = activeOrderData.normal_range || "";
  const unit = activeOrderData.unit || "";
  const val = parseFloat((valueStr || "").trim());

  if (isNaN(val) || !rangeStr || rangeStr === "-") {
    alertContainer.style.display = "none";
    alertContainer.innerHTML = "";
    return;
  }

  let isOut = false;
  let reason = "";

  const rangeMatch = rangeStr.match(/([\d\.]+)\s*-\s*([\d\.]+)/);
  const lessMatch = rangeStr.match(/<\s*([\d\.]+)/);
  const greaterMatch = rangeStr.match(/>\s*([\d\.]+)/);

  if (rangeMatch) {
    const min = parseFloat(rangeMatch[1]);
    const max = parseFloat(rangeMatch[2]);
    if (val < min) { isOut = true; reason = `Value is below normal range (${min} ${unit})`; }
    else if (val > max) { isOut = true; reason = `Value is above normal range (${max} ${unit})`; }
  } else if (lessMatch) {
    const max = parseFloat(lessMatch[1]);
    if (val >= max) { isOut = true; reason = `Value exceeds threshold (${max} ${unit})`; }
  } else if (greaterMatch) {
    const min = parseFloat(greaterMatch[1]);
    if (val <= min) { isOut = true; reason = `Value is below threshold (${min} ${unit})`; }
  }

  if (isOut) {
    alertContainer.style.display = "block";
    alertContainer.innerHTML = `
      <div style="background:#fef2f2; border:1px solid #f87171; border-radius:6px; padding:0.6rem 0.85rem; color:#991b1b; display:flex; align-items:center; gap:0.5rem; font-size:0.85rem;">
        <svg class="icon icon-sm" style="color:#dc2626;" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <div><strong>Out of Reference Range:</strong> ${reason}. Configured Range: <strong>${rangeStr} ${unit}</strong>.</div>
      </div>
    `;
    if (abnormalCheckbox) abnormalCheckbox.checked = true;
    document.getElementById("panicFlagSelect").value = "ABNORMAL";
  } else {
    alertContainer.style.display = "none";
    alertContainer.innerHTML = "";
    if (abnormalCheckbox) abnormalCheckbox.checked = false;
    document.getElementById("panicFlagSelect").value = "NORMAL";
  }
}

async function handleSaveLabResult(e) {
  e.preventDefault();
  if (!activeOrderId) return;

  const isAbnormal = document.getElementById("isAbnormalCheckbox").checked;
  const panicFlag = document.getElementById("panicFlagSelect").value;
  const notes = document.getElementById("techNotesInput").value.trim() || null;

  let resultValue = "";
  let parameterResults = null;

  const multiRows = document.querySelectorAll(".multi-param-val");
  if (multiRows && multiRows.length > 0) {
    const paramList = [];
    multiRows.forEach((inputEl, idx) => {
      const badge = document.getElementById(`paramFlagBadge_${idx}`);
      paramList.push({
        name: inputEl.dataset.name,
        value: inputEl.value.trim(),
        unit: inputEl.dataset.unit,
        range: inputEl.dataset.range,
        flag: badge ? badge.textContent.trim() : "NORMAL"
      });
    });
    parameterResults = JSON.stringify(paramList);
    resultValue = "Multi-Parameter Analyte Panel Completed";
  } else {
    resultValue = document.getElementById("resultValueInput").value.trim();
  }

  const payload = {
    order_id: activeOrderId,
    result_value: resultValue || "Completed",
    is_abnormal: isAbnormal,
    panic_flag: panicFlag,
    technician_notes: notes,
    parameter_results: parameterResults
  };

  try {
    await apiFetch("/api/lab/results", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    showToast("Laboratory report saved and verified successfully!", "success");
    closeModal("labResultModal");
    refreshDiagnosticData();
  } catch (err) {
    showToast("Failed to save laboratory report", "error");
  }
}

// ============================================================================
// MODAL 2: RADIOLOGY PACS WORKSTATION & MEDICAL IMAGE STUDIO
// ============================================================================

let pacsCanvas, pacsCtx;
let pacsImage = null;
let pacsZoom = 1.0;
let pacsPanX = 0, pacsPanY = 0;
let pacsRotation = 0;
let pacsBrightness = 0;
let pacsContrast = 0;
let pacsInvert = false;
let pacsCurrentTool = "pan"; // pan, arrow, circle, draw, measure
let pacsAnnotations = [];
let pacsIsMouseDown = false;
let pacsStartX = 0, pacsStartY = 0;
let pacsCurrentDrawing = null;

function initPacsCanvas() {
  pacsCanvas = document.getElementById("pacsCanvas");
  if (!pacsCanvas) return;
  pacsCtx = pacsCanvas.getContext("2d");

  // Resize canvas to match viewport container
  const resizeCanvas = () => {
    const viewport = document.getElementById("pacsViewport");
    if (!viewport) return;
    pacsCanvas.width = viewport.clientWidth;
    pacsCanvas.height = viewport.clientHeight;
    renderPacs();
  };

  window.addEventListener("resize", resizeCanvas);

  pacsCanvas.addEventListener("mousedown", onPacsMouseDown);
  pacsCanvas.addEventListener("mousemove", onPacsMouseMove);
  pacsCanvas.addEventListener("mouseup", onPacsMouseUp);
  pacsCanvas.addEventListener("mouseleave", onPacsMouseUp);
  pacsCanvas.addEventListener("wheel", onPacsWheel, { passive: false });
}

function onPacsWheel(e) {
  e.preventDefault();
  const zoomFactor = e.deltaY < 0 ? 0.1 : -0.1;
  zoomPacs(zoomFactor);
}

function getCanvasCoordinates(e) {
  const rect = pacsCanvas.getBoundingClientRect();
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  };
}

// Convert screen viewport coordinates to image coordinate space
function screenToImageCoords(screenX, screenY) {
  const cx = pacsCanvas.width / 2 + pacsPanX;
  const cy = pacsCanvas.height / 2 + pacsPanY;
  const rad = (-pacsRotation * Math.PI) / 180;

  // Un-translate
  const dx = (screenX - cx) / pacsZoom;
  const dy = (screenY - cy) / pacsZoom;

  // Un-rotate
  const imgX = dx * Math.cos(rad) - dy * Math.sin(rad);
  const imgY = dx * Math.sin(rad) + dy * Math.cos(rad);

  return { x: imgX, y: imgY };
}

function onPacsMouseDown(e) {
  pacsIsMouseDown = true;
  const pos = getCanvasCoordinates(e);
  pacsStartX = pos.x;
  pacsStartY = pos.y;

  if (pacsCurrentTool === "pan") {
    pacsCanvas.style.cursor = "grabbing";
  } else {
    const imgPos = screenToImageCoords(pos.x, pos.y);
    const color = document.getElementById("pacsColor") ? document.getElementById("pacsColor").value : "#facc15";

    if (pacsCurrentTool === "draw") {
      pacsCurrentDrawing = {
        type: "draw",
        color: color,
        width: 3,
        points: [imgPos]
      };
    } else if (pacsCurrentTool === "arrow") {
      pacsCurrentDrawing = {
        type: "arrow",
        color: color,
        width: 3,
        x1: imgPos.x,
        y1: imgPos.y,
        x2: imgPos.x,
        y2: imgPos.y
      };
    } else if (pacsCurrentTool === "circle") {
      pacsCurrentDrawing = {
        type: "circle",
        color: color,
        width: 3,
        cx: imgPos.x,
        cy: imgPos.y,
        rx: 0,
        ry: 0
      };
    } else if (pacsCurrentTool === "measure") {
      pacsCurrentDrawing = {
        type: "measure",
        color: color,
        width: 3,
        x1: imgPos.x,
        y1: imgPos.y,
        x2: imgPos.x,
        y2: imgPos.y,
        lengthMm: 0
      };
    }
  }
}

function onPacsMouseMove(e) {
  if (!pacsIsMouseDown) return;
  const pos = getCanvasCoordinates(e);

  if (pacsCurrentTool === "pan") {
    pacsPanX += (pos.x - pacsStartX);
    pacsPanY += (pos.y - pacsStartY);
    pacsStartX = pos.x;
    pacsStartY = pos.y;
    renderPacs();
  } else if (pacsCurrentDrawing) {
    const imgPos = screenToImageCoords(pos.x, pos.y);

    if (pacsCurrentDrawing.type === "draw") {
      pacsCurrentDrawing.points.push(imgPos);
    } else if (pacsCurrentDrawing.type === "arrow" || pacsCurrentDrawing.type === "measure") {
      pacsCurrentDrawing.x2 = imgPos.x;
      pacsCurrentDrawing.y2 = imgPos.y;

      if (pacsCurrentDrawing.type === "measure") {
        const dx = pacsCurrentDrawing.x2 - pacsCurrentDrawing.x1;
        const dy = pacsCurrentDrawing.y2 - pacsCurrentDrawing.y1;
        // Approximate pixel-to-mm ratio for standard medical radiography
        const distPx = Math.sqrt(dx * dx + dy * dy);
        pacsCurrentDrawing.lengthMm = (distPx * 0.264).toFixed(1);

        const lbl = document.getElementById("pacsMeasurementLabel");
        if (lbl) {
          lbl.style.display = "block";
          lbl.textContent = `Distance: ${pacsCurrentDrawing.lengthMm} mm (${Math.round(distPx)} px)`;
        }
      }
    } else if (pacsCurrentDrawing.type === "circle") {
      pacsCurrentDrawing.rx = Math.abs(imgPos.x - pacsCurrentDrawing.cx);
      pacsCurrentDrawing.ry = Math.abs(imgPos.y - pacsCurrentDrawing.cy);
    }
    renderPacs();
  }
}

function onPacsMouseUp(e) {
  if (!pacsIsMouseDown) return;
  pacsIsMouseDown = false;
  if (pacsCurrentTool === "pan") {
    pacsCanvas.style.cursor = "grab";
  } else if (pacsCurrentDrawing) {
    pacsAnnotations.push(pacsCurrentDrawing);
    pacsCurrentDrawing = null;
    renderPacs();
  }
}

function setPacsTool(tool) {
  pacsCurrentTool = tool;
  const btns = document.querySelectorAll(".pacs-tool-btn");
  btns.forEach(b => {
    b.classList.remove("active");
    b.style.background = "#1e293b";
    b.style.color = "#cbd5e1";
    b.style.border = "1px solid #334155";
  });

  const activeId = tool === "pan" ? "toolPan" : tool === "arrow" ? "toolArrow" : tool === "circle" ? "toolCircle" : tool === "draw" ? "toolDraw" : "toolMeasure";
  const activeBtn = document.getElementById(activeId);
  if (activeBtn) {
    activeBtn.classList.add("active");
    activeBtn.style.background = "#2563eb";
    activeBtn.style.color = "#ffffff";
    activeBtn.style.border = "none";
  }

  if (pacsCanvas) {
    pacsCanvas.style.cursor = tool === "pan" ? "grab" : "crosshair";
  }
}

function applyPacsFilters() {
  const bInput = document.getElementById("pacsBrightness");
  const cInput = document.getElementById("pacsContrast");
  if (bInput) pacsBrightness = parseInt(bInput.value, 10);
  if (cInput) pacsContrast = parseInt(cInput.value, 10);
  renderPacs();
}

function togglePacsInvert() {
  pacsInvert = !pacsInvert;
  const btn = document.getElementById("btnInvertScan");
  if (btn) {
    btn.textContent = pacsInvert ? "Invert (Positive)" : "Invert (Negative)";
    btn.style.background = pacsInvert ? "#2563eb" : "#1e293b";
    btn.style.color = "#fff";
  }
  renderPacs();
}

function rotatePacsScan(deg = 90) {
  pacsRotation = (pacsRotation + deg) % 360;
  renderPacs();
}

function zoomPacs(delta) {
  pacsZoom = Math.min(Math.max(pacsZoom + delta, 0.25), 4.5);
  renderPacs();
}

function resetPacsView() {
  pacsZoom = 1.0;
  pacsPanX = 0;
  pacsPanY = 0;
  pacsRotation = 0;
  pacsBrightness = 0;
  pacsContrast = 0;
  pacsInvert = false;

  const bInput = document.getElementById("pacsBrightness");
  const cInput = document.getElementById("pacsContrast");
  const invertBtn = document.getElementById("btnInvertScan");
  if (bInput) bInput.value = 0;
  if (cInput) cInput.value = 0;
  if (invertBtn) {
    invertBtn.textContent = "Invert (Negative)";
    invertBtn.style.background = "#1e293b";
    invertBtn.style.color = "#e2e8f0";
  }
  renderPacs();
}

function undoPacsAnnotation() {
  if (pacsAnnotations.length > 0) {
    pacsAnnotations.pop();
    renderPacs();
  }
}

function clearPacsAnnotations() {
  pacsAnnotations = [];
  pacsCurrentDrawing = null;
  const lbl = document.getElementById("pacsMeasurementLabel");
  if (lbl) lbl.style.display = "none";
  renderPacs();
}

function renderPacs() {
  if (!pacsCanvas || !pacsCtx) return;

  const w = pacsCanvas.width;
  const h = pacsCanvas.height;

  // Clear background (darkroom black)
  pacsCtx.save();
  pacsCtx.fillStyle = "#020617";
  pacsCtx.fillRect(0, 0, w, h);

  if (!pacsImage || !pacsImage.complete || pacsImage.naturalWidth === 0) {
    pacsCtx.restore();
    return;
  }

  // Set DICOM windowing filters
  const bVal = 100 + pacsBrightness; // 0 to 200%
  const cVal = 100 + pacsContrast;   // 0 to 200%
  const invVal = pacsInvert ? 100 : 0;
  pacsCtx.filter = `brightness(${bVal}%) contrast(${cVal}%) invert(${invVal}%)`;

  // Translate to center + pan offset, rotate and zoom
  const cx = w / 2 + pacsPanX;
  const cy = h / 2 + pacsPanY;

  pacsCtx.translate(cx, cy);
  pacsCtx.rotate((pacsRotation * Math.PI) / 180);
  pacsCtx.scale(pacsZoom, pacsZoom);

  // Draw image centered in image coordinate space
  const imgW = pacsImage.naturalWidth;
  const imgH = pacsImage.naturalHeight;
  pacsCtx.drawImage(pacsImage, -imgW / 2, -imgH / 2, imgW, imgH);

  // Turn off image filters for sharp vector annotations
  pacsCtx.filter = "none";

  // Draw all saved and active annotations in image coordinate space
  const drawList = [...pacsAnnotations];
  if (pacsCurrentDrawing) drawList.push(pacsCurrentDrawing);

  for (const ann of drawList) {
    pacsCtx.strokeStyle = ann.color || "#facc15";
    pacsCtx.fillStyle = ann.color || "#facc15";
    pacsCtx.lineWidth = ann.width || 3;
    pacsCtx.lineCap = "round";
    pacsCtx.lineJoin = "round";

    if (ann.type === "draw" && ann.points && ann.points.length > 1) {
      pacsCtx.beginPath();
      pacsCtx.moveTo(ann.points[0].x, ann.points[0].y);
      for (let i = 1; i < ann.points.length; i++) {
        pacsCtx.lineTo(ann.points[i].x, ann.points[i].y);
      }
      pacsCtx.stroke();
    } else if (ann.type === "arrow") {
      drawArrow(pacsCtx, ann.x1, ann.y1, ann.x2, ann.y2, ann.color, ann.width);
    } else if (ann.type === "circle") {
      pacsCtx.beginPath();
      pacsCtx.ellipse(ann.cx, ann.cy, Math.max(ann.rx, 4), Math.max(ann.ry, 4), 0, 0, Math.PI * 2);
      pacsCtx.stroke();
    } else if (ann.type === "measure") {
      drawCaliper(pacsCtx, ann.x1, ann.y1, ann.x2, ann.y2, ann.lengthMm, ann.color);
    }
  }

  pacsCtx.restore();
}

function drawArrow(ctx, fromX, fromY, toX, toY, color, width) {
  const headlen = 16;
  const dx = toX - fromX;
  const dy = toY - fromY;
  const angle = Math.atan2(dy, dx);

  ctx.beginPath();
  ctx.moveTo(fromX, fromY);
  ctx.lineTo(toX, toY);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(toX, toY);
  ctx.lineTo(toX - headlen * Math.cos(angle - Math.PI / 6), toY - headlen * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(toX - headlen * Math.cos(angle + Math.PI / 6), toY - headlen * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fill();
}

function drawCaliper(ctx, x1, y1, x2, y2, lengthMm, color) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  // Draw end ticks
  const tickLen = 8;
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const perp = angle + Math.PI / 2;

  ctx.beginPath();
  ctx.moveTo(x1 - tickLen * Math.cos(perp), y1 - tickLen * Math.sin(perp));
  ctx.lineTo(x1 + tickLen * Math.cos(perp), y1 + tickLen * Math.sin(perp));
  ctx.moveTo(x2 - tickLen * Math.cos(perp), y2 - tickLen * Math.sin(perp));
  ctx.lineTo(x2 + tickLen * Math.cos(perp), y2 + tickLen * Math.sin(perp));
  ctx.stroke();

  // Draw measurement label
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  ctx.font = "bold 13px Helvetica, Arial, sans-serif";
  ctx.fillStyle = "#0f172a";
  const text = `${lengthMm} mm`;
  const tWidth = ctx.measureText(text).width;
  ctx.fillRect(midX - tWidth / 2 - 4, midY - 18, tWidth + 8, 18);
  ctx.fillStyle = color || "#facc15";
  ctx.fillText(text, midX - tWidth / 2, midY - 4);
}

function loadPacsScanUrl(url) {
  const promptEl = document.getElementById("pacsEmptyPrompt");
  const infoEl = document.getElementById("scanLoadedInfo");
  if (!url) {
    if (promptEl) promptEl.style.display = "flex";
    if (infoEl) infoEl.textContent = "Scan: None";
    pacsImage = null;
    renderPacs();
    return;
  }

  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    pacsImage = img;
    if (promptEl) promptEl.style.display = "none";
    if (infoEl) infoEl.textContent = `Scan: ${img.naturalWidth} x ${img.naturalHeight} px`;

    // Scale to fit viewport
    const viewport = document.getElementById("pacsViewport");
    if (viewport) {
      pacsCanvas.width = viewport.clientWidth;
      pacsCanvas.height = viewport.clientHeight;
      const scaleX = (viewport.clientWidth * 0.88) / img.naturalWidth;
      const scaleY = (viewport.clientHeight * 0.88) / img.naturalHeight;
      pacsZoom = Math.min(scaleX, scaleY, 1.0);
      pacsPanX = 0;
      pacsPanY = 0;
    }
    renderPacs();
  };
  img.onerror = () => {
    showToast("Failed to load diagnostic scan image", "error");
    if (promptEl) promptEl.style.display = "flex";
  };
  img.src = url;
}

function loadDefaultSampleScan() {
  const modality = (activeOrderData && activeOrderData.modality) || "XRAY";
  const sampleUrl = modality === "CT" ? "/static/uploads/radiology/sample_brain_ct.jpg" : "/static/uploads/radiology/sample_chest_xray.jpg";
  document.getElementById("radImageUrl").value = sampleUrl;
  loadPacsScanUrl(sampleUrl);
  showToast(`Standard ${modality} reference scan loaded into PACS workstation!`, "success");
}

async function handlePacsFileUpload(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);
  if (radActiveOrderId) {
    formData.append("order_id", radActiveOrderId);
  }

  try {
    const res = await fetch("/api/lab/radiology/upload", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      document.getElementById("radImageUrl").value = data.image_url;
      loadPacsScanUrl(data.image_url);
      showToast("Diagnostic scan uploaded to PACS storage!", "success");
    } else {
      showToast("Upload failed: " + (data.detail || "Server error"), "error");
    }
  } catch (err) {
    showToast("Failed to upload scan file", "error");
  }
}

async function savePacsAnnotatedImage() {
  if (!radActiveOrderId) {
    showToast("No active radiology order", "error");
    return;
  }
  if (!pacsImage) {
    showToast("Please load or upload a medical scan first", "warning");
    return;
  }

  // Create high-res offscreen canvas matching original scan dimensions
  const offCanvas = document.createElement("canvas");
  const imgW = pacsImage.naturalWidth;
  const imgH = pacsImage.naturalHeight;
  offCanvas.width = imgW;
  offCanvas.height = imgH;
  const offCtx = offCanvas.getContext("2d");

  // Apply DICOM windowing filters
  const bVal = 100 + pacsBrightness;
  const cVal = 100 + pacsContrast;
  const invVal = pacsInvert ? 100 : 0;
  offCtx.filter = `brightness(${bVal}%) contrast(${cVal}%) invert(${invVal}%)`;

  // Draw scan image
  offCtx.drawImage(pacsImage, 0, 0, imgW, imgH);
  offCtx.filter = "none";

  // Translate coordinates from centered space to [0, 0, imgW, imgH]
  offCtx.translate(imgW / 2, imgH / 2);

  for (const ann of pacsAnnotations) {
    offCtx.strokeStyle = ann.color || "#facc15";
    offCtx.fillStyle = ann.color || "#facc15";
    offCtx.lineWidth = Math.max(ann.width, 3);
    offCtx.lineCap = "round";
    offCtx.lineJoin = "round";

    if (ann.type === "draw" && ann.points && ann.points.length > 1) {
      offCtx.beginPath();
      offCtx.moveTo(ann.points[0].x, ann.points[0].y);
      for (let i = 1; i < ann.points.length; i++) {
        offCtx.lineTo(ann.points[i].x, ann.points[i].y);
      }
      offCtx.stroke();
    } else if (ann.type === "arrow") {
      drawArrow(offCtx, ann.x1, ann.y1, ann.x2, ann.y2, ann.color, ann.width);
    } else if (ann.type === "circle") {
      offCtx.beginPath();
      offCtx.ellipse(ann.cx, ann.cy, Math.max(ann.rx, 4), Math.max(ann.ry, 4), 0, 0, Math.PI * 2);
      offCtx.stroke();
    } else if (ann.type === "measure") {
      drawCaliper(offCtx, ann.x1, ann.y1, ann.x2, ann.y2, ann.lengthMm, ann.color);
    }
  }

  const base64Data = offCanvas.toDataURL("image/png");

  try {
    const res = await apiFetch("/api/lab/radiology/annotate", {
      method: "POST",
      body: JSON.stringify({
        order_id: radActiveOrderId,
        image_data: base64Data
      })
    });
    document.getElementById("radAnnotatedImageUrl").value = res.annotated_image_url;
    showToast("Annotated radiograph saved and attached to report!", "success");
  } catch (err) {
    showToast("Failed to save annotated radiograph", "error");
  }
}

async function openRadiologyStudio(orderId) {
  radActiveOrderId = orderId;
  resetPacsView();
  clearPacsAnnotations();

  try {
    const ord = await apiFetch(`/api/lab/orders/${orderId}`);
    activeOrderData = ord;

    document.getElementById("radOrderId").value = ord.id;
    document.getElementById("radModalTitle").textContent = `${ord.test_name}`;
    document.getElementById("radModalModalityBadge").textContent = ord.modality || "RADIOLOGY";
    document.getElementById("radModalPatientInfo").innerHTML = `
      <strong>${escapeHtml(ord.patient_name)}</strong> (MRN: ${escapeHtml(ord.patient_mrn)}) &bull;
      ${escapeHtml(ord.patient_age)}Y / ${escapeHtml(ord.patient_gender)} &bull;
      Ref: ${(ord.doctor_name || '').startsWith('Dr.') ? '' : 'Dr. '}${escapeHtml(ord.doctor_name)} &bull; Accession: <code>${escapeHtml(ord.sample_barcode || 'N/A')}</code>
    `;

    document.getElementById("radClinicalHistory").value = ord.clinical_history || ord.clinical_notes || "";
    document.getElementById("radTechnique").value = ord.technique || (ord.modality === "CT" ? "Axial non-contrast CT sections obtained at 5mm intervals" : "PA view of the chest obtained in upright inspiration");
    document.getElementById("radFindings").value = ord.findings || "";
    document.getElementById("radImpression").value = ord.impression || "";
    document.getElementById("radAbnormalCheck").checked = Boolean(ord.is_abnormal);

    document.getElementById("radImageUrl").value = ord.image_url || "";
    document.getElementById("radAnnotatedImageUrl").value = ord.annotated_image_url || "";

    const pdfBtn = document.getElementById("radPdfDownloadBtn");
    if (pdfBtn) pdfBtn.style.display = ord.sample_status === "COMPLETED" ? "inline-block" : "none";

    // Open Modal
    openModal("radiologyStudioModal");

    // Load Scan image
    setTimeout(() => {
      const scanUrl = ord.annotated_image_url || ord.image_url;
      if (scanUrl) {
        loadPacsScanUrl(scanUrl);
      } else {
        loadPacsScanUrl(null);
      }
    }, 150);

  } catch (err) {
    showToast("Failed to load radiology order details", "error");
  }
}

function insertNormalBoilerplate() {
  if (!activeOrderData) return;
  const tmplText = activeOrderData.template_text;

  if (tmplText) {
    const parts = tmplText.split("IMPRESSION:");
    if (parts.length > 1) {
      document.getElementById("radFindings").value = parts[0].replace("FINDINGS:", "").trim();
      document.getElementById("radImpression").value = parts[1].trim();
    } else {
      document.getElementById("radFindings").value = tmplText;
      document.getElementById("radImpression").value = "Within normal physiological limits.";
    }
  } else {
    document.getElementById("radFindings").value = "No focal parenchymal consolidation, infiltrate, or pleural effusion identified.\nCardiothoracic ratio is normal (< 0.50).\nVisualized bony thorax and soft tissues appear unremarkable.";
    document.getElementById("radImpression").value = "Normal diagnostic imaging examination. No acute pathology.";
  }
  showToast("Normal findings template inserted!", "info");
}

async function handleSaveRadiologyReport(e) {
  e.preventDefault();
  if (!radActiveOrderId) return;

  const findings = document.getElementById("radFindings").value.trim();
  const impression = document.getElementById("radImpression").value.trim();
  const clinicalHistory = document.getElementById("radClinicalHistory").value.trim();
  const technique = document.getElementById("radTechnique").value.trim();
  const isAbnormal = document.getElementById("radAbnormalCheck").checked;
  const imageUrl = document.getElementById("radImageUrl").value.trim() || null;
  const annotatedImageUrl = document.getElementById("radAnnotatedImageUrl").value.trim() || null;

  const payload = {
    order_id: radActiveOrderId,
    result_value: impression.substring(0, 95) || "Report Signed",
    is_abnormal: isAbnormal,
    panic_flag: isAbnormal ? "ABNORMAL" : "NORMAL",
    clinical_history: clinicalHistory,
    technique: technique,
    findings: findings,
    impression: impression,
    image_url: imageUrl,
    annotated_image_url: annotatedImageUrl,
    modality: (activeOrderData && activeOrderData.modality) || "XRAY"
  };

  try {
    await apiFetch("/api/lab/results", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    showToast("Radiology report signed and saved to PACS EHR!", "success");
    closeModal("radiologyStudioModal");
    refreshDiagnosticData();
  } catch (err) {
    showToast("Failed to save radiology report", "error");
  }
}

// ============================================================================
// MODAL 3: QUICK ORDER INVESTIGATION
// ============================================================================

async function openOrderModal() {
  const form = document.getElementById("orderInvestigationForm");
  if (form) form.reset();

  const previewBox = document.getElementById("orderTemplatePreviewBox");
  if (previewBox) previewBox.style.display = "none";

  try {
    const [pts, tmpls] = await Promise.all([
      apiFetch("/api/patients"),
      apiFetch("/api/lab/templates")
    ]);

    allPatients = pts || [];
    allTemplates = tmpls || [];

    const pSelect = document.getElementById("orderPatientSelect");
    if (pSelect) {
      pSelect.innerHTML = `<option value="">-- Choose Registered Patient --</option>` +
        allPatients.map(p => `<option value="${p.id}">${escapeHtml(p.full_name)} (MRN: ${escapeHtml(p.mrn)})</option>`).join("");
    }

    const tSelect = document.getElementById("orderTemplateSelect");
    if (tSelect) {
      tSelect.innerHTML = `<option value="">-- Choose Investigation --</option>` +
        allTemplates.map(t => `<option value="${t.id}">${escapeHtml(t.department)}: ${escapeHtml(t.test_name)} (Rs. ${t.standard_rate})</option>`).join("");
    }

    openModal("orderInvestigationModal");
  } catch (err) {
    showToast("Failed to initialize order dialog", "error");
  }
}

function handleOrderTemplateSelection(tmplId) {
  const previewBox = document.getElementById("orderTemplatePreviewBox");
  if (!previewBox) return;

  const t = allTemplates.find(x => String(x.id) === String(tmplId));
  if (!t) {
    previewBox.style.display = "none";
    return;
  }

  previewBox.style.display = "block";
  document.getElementById("previewDept").textContent = t.department + (t.modality ? ` (${t.modality})` : '');
  document.getElementById("previewRate").textContent = `Rs. ${t.standard_rate}`;
  document.getElementById("previewSample").textContent = t.sample_type;
}

async function handleCreateInvestigationOrder(e) {
  e.preventDefault();
  const patientId = document.getElementById("orderPatientSelect").value;
  const templateId = document.getElementById("orderTemplateSelect").value;
  const notes = document.getElementById("orderClinicalNotes").value.trim() || null;

  if (!patientId || !templateId) {
    showToast("Please select patient and investigation", "warning");
    return;
  }

  try {
    const res = await apiFetch("/api/lab/orders", {
      method: "POST",
      body: JSON.stringify({
        patient_id: parseInt(patientId, 10),
        template_id: parseInt(templateId, 10),
        clinical_notes: notes
      })
    });
    showToast(`Investigation scheduled! Accession barcode: ${res.barcode}`, "success");
    closeModal("orderInvestigationModal");
    refreshDiagnosticData();
  } catch (err) {
    showToast("Failed to create investigation order", "error");
  }
}

// ============================================================================
// SECTION 2: TEMPLATE MANAGEMENT STUDIO
// ============================================================================

async function loadAllTemplatesCatalog() {
  try {
    const tmpls = await apiFetch("/api/lab/templates/all");
    allTemplates = tmpls || [];
  } catch (err) {}
}

async function loadTemplatesTable(deptFilter = "") {
  const tbody = document.getElementById("templateTableBody");
  if (!tbody) return;

  try {
    const url = deptFilter ? `/api/lab/templates/all?department=${encodeURIComponent(deptFilter)}` : "/api/lab/templates/all";
    const templates = await apiFetch(url);
    allTemplates = templates || [];

    if (templates.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:2rem; color:var(--text-muted);">No templates configured.</td></tr>`;
      return;
    }

    tbody.innerHTML = templates.map(t => {
      let schemaLabel = "Single Value";
      if (t.parameters_json) {
        try {
          const arr = JSON.parse(t.parameters_json);
          schemaLabel = `Panel: ${arr.length} parameters`;
        } catch (e) {
          schemaLabel = "Custom JSON";
        }
      } else if (t.department === "Radiology") {
        schemaLabel = "PACS Report";
      }

      return `
        <tr>
          <td><strong style="font-family:monospace; color:var(--primary-700);">${escapeHtml(t.test_code)}</strong></td>
          <td><strong>${escapeHtml(t.test_name)}</strong></td>
          <td>
            <span class="badge ${t.department === 'Radiology' ? 'badge-primary' : 'badge-secondary'}" style="font-size:0.75rem;">
              ${escapeHtml(t.department)}
            </span>
            ${t.modality ? `<span class="badge badge-info" style="font-size:0.7rem; font-weight:700; margin-left:0.25rem;">${escapeHtml(t.modality)}</span>` : ''}
          </td>
          <td>${escapeHtml(t.sample_type)}</td>
          <td><strong>Rs. ${t.standard_rate}</strong></td>
          <td>${escapeHtml(t.normal_range || '-')} <small style="color:var(--text-muted);">${escapeHtml(t.unit || '')}</small></td>
          <td><span class="badge badge-info" style="font-size:0.7rem;">${schemaLabel}</span></td>
          <td>
            <span class="badge ${t.is_active ? 'badge-success' : 'badge-warning'}">
              ${t.is_active ? 'Active' : 'Inactive'}
            </span>
          </td>
          <td style="text-align:right;">
            <button class="btn btn-outline btn-sm" onclick="openEditTemplateModal(${t.id})" style="font-size:0.75rem; padding:0.2rem 0.5rem;">
              Edit Template
            </button>
          </td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    showToast("Failed to load templates catalog", "error");
  }
}

function openNewTemplateModal() {
  const form = document.getElementById("templateEditForm");
  if (form) form.reset();

  document.getElementById("editTemplateId").value = "";
  document.getElementById("templateModalTitle").textContent = "Add Diagnostic Test / Imaging Template";
  document.getElementById("tmplIsActiveInput").checked = true;

  handleTemplateDeptChange("Hematology");
  initVisualAnalyteBuilder("");
  openModal("templateEditModal");
}

function openEditTemplateModal(templateId) {
  const t = allTemplates.find(x => x.id === templateId);
  if (!t) return;

  document.getElementById("editTemplateId").value = t.id;
  document.getElementById("templateModalTitle").textContent = `Edit Template: ${t.test_name}`;
  document.getElementById("tmplCodeInput").value = t.test_code;
  document.getElementById("tmplNameInput").value = t.test_name;
  document.getElementById("tmplDeptSelect").value = t.department;
  document.getElementById("tmplModalitySelect").value = t.modality || "";
  document.getElementById("tmplRateInput").value = t.standard_rate;
  document.getElementById("tmplSampleInput").value = t.sample_type;
  document.getElementById("tmplRangeInput").value = t.normal_range || "";
  document.getElementById("tmplUnitInput").value = t.unit || "";
  document.getElementById("tmplParamsJsonInput").value = t.parameters_json || "";
  document.getElementById("tmplTemplateTextInput").value = t.template_text || "";
  document.getElementById("tmplIsActiveInput").checked = Boolean(t.is_active);

  handleTemplateDeptChange(t.department);
  initVisualAnalyteBuilder(t.parameters_json || "");
  openModal("templateEditModal");
}

function handleTemplateDeptChange(dept) {
  const labSection = document.getElementById("tmplLabParamSection");
  const radSection = document.getElementById("tmplRadTextSection");
  const modSelect = document.getElementById("tmplModalitySelect");

  if (dept === "Radiology") {
    if (labSection) labSection.style.display = "none";
    if (radSection) radSection.style.display = "block";
    if (modSelect && !modSelect.value) modSelect.value = "XRAY";
  } else {
    if (labSection) labSection.style.display = "block";
    if (radSection) radSection.style.display = "none";
    if (modSelect) modSelect.value = "";
  }
}

const PRESET_ANALYTES = {
  CBC: [
    {"name": "Hemoglobin (Hb)", "unit": "g/dL", "range": "13.5 - 17.5", "default_val": "14.2"},
    {"name": "Total Leukocyte Count (TLC)", "unit": "/mcL", "range": "4000 - 11000", "default_val": "7200"},
    {"name": "Platelet Count (PLT)", "unit": "/mcL", "range": "150000 - 450000", "default_val": "240000"},
    {"name": "Packed Cell Volume (PCV)", "unit": "%", "range": "40.0 - 50.0", "default_val": "44.5"},
    {"name": "Neutrophils", "unit": "%", "range": "40 - 75", "default_val": "62"},
    {"name": "Lymphocytes", "unit": "%", "range": "20 - 45", "default_val": "30"},
    {"name": "Eosinophils", "unit": "%", "range": "1 - 6", "default_val": "3"}
  ],
  LIPID: [
    {"name": "Total Cholesterol", "unit": "mg/dL", "range": "< 200", "default_val": "180"},
    {"name": "HDL Cholesterol (Good)", "unit": "mg/dL", "range": "> 40", "default_val": "48"},
    {"name": "LDL Cholesterol (Bad)", "unit": "mg/dL", "range": "< 100", "default_val": "95"},
    {"name": "Triglycerides", "unit": "mg/dL", "range": "< 150", "default_val": "135"},
    {"name": "VLDL Cholesterol", "unit": "mg/dL", "range": "5 - 30", "default_val": "22"}
  ],
  KFT: [
    {"name": "Blood Urea Nitrogen (BUN)", "unit": "mg/dL", "range": "7 - 20", "default_val": "14"},
    {"name": "Serum Creatinine", "unit": "mg/dL", "range": "0.7 - 1.3", "default_val": "0.95"},
    {"name": "Serum Uric Acid", "unit": "mg/dL", "range": "3.5 - 7.2", "default_val": "5.1"},
    {"name": "Serum Sodium", "unit": "mEq/L", "range": "135 - 145", "default_val": "140"},
    {"name": "Serum Potassium", "unit": "mEq/L", "range": "3.5 - 5.1", "default_val": "4.2"}
  ]
};

function initVisualAnalyteBuilder(jsonString) {
  const tbody = document.getElementById("visualAnalyteTableBody");
  if (!tbody) return;
  tbody.innerHTML = "";
  
  let list = [];
  if (jsonString && typeof jsonString === "string") {
    try {
      const parsed = JSON.parse(jsonString);
      if (Array.isArray(parsed)) list = parsed;
    } catch (e) {
      console.warn("Could not parse existing parameters_json:", e);
    }
  } else if (Array.isArray(jsonString)) {
    list = jsonString;
  }
  
  const notice = document.getElementById("visualAnalyteEmptyNotice");
  if (list.length === 0) {
    if (notice) notice.style.display = "block";
  } else {
    if (notice) notice.style.display = "none";
    list.forEach(item => addVisualAnalyteRow(item));
  }
  syncVisualAnalytesToJson();
}

function updateVisualAnalyteIndices() {
  const tbody = document.getElementById("visualAnalyteTableBody");
  if (!tbody) return;
  const rows = tbody.querySelectorAll("tr.visual-analyte-row");
  rows.forEach((r, idx) => {
    const badge = r.querySelector(".row-num-badge");
    if (badge) badge.textContent = String(idx + 1);
  });
}

function addVisualAnalyteRow(data = {}, isUserTriggered = false) {
  const tbody = document.getElementById("visualAnalyteTableBody");
  if (!tbody) return;
  const notice = document.getElementById("visualAnalyteEmptyNotice");
  if (notice) notice.style.display = "none";
  
  const currentCount = tbody.querySelectorAll("tr.visual-analyte-row").length;
  const tr = document.createElement("tr");
  tr.className = "visual-analyte-row";
  if (isUserTriggered) {
    tr.classList.add("row-highlight-pulse");
  }

  tr.innerHTML = `
    <td style="text-align:center; font-weight:700; color:var(--text-muted); font-size:0.75rem;">
      <span class="row-num-badge" style="background:var(--bg-surface-alt); padding:2px 6px; border-radius:4px; border:1px solid var(--border-subtle);">${currentCount + 1}</span>
    </td>
    <td>
      <input type="text" class="form-control form-control-sm analyte-name" style="font-weight:600;" placeholder="e.g. Hemoglobin (Hb)" value="${escapeHtml(data.name || '')}" oninput="syncVisualAnalytesToJson()" required>
    </td>
    <td>
      <input type="text" class="form-control form-control-sm analyte-unit" placeholder="e.g. g/dL" value="${escapeHtml(data.unit || '')}" oninput="syncVisualAnalytesToJson()">
    </td>
    <td>
      <input type="text" class="form-control form-control-sm analyte-range" placeholder="e.g. 13.5 - 17.5" value="${escapeHtml(data.range || '')}" oninput="syncVisualAnalytesToJson()">
    </td>
    <td>
      <input type="text" class="form-control form-control-sm analyte-default" placeholder="e.g. 14.2" value="${escapeHtml(data.default_val || '')}" oninput="syncVisualAnalytesToJson()">
    </td>
    <td style="text-align:center;">
      <button type="button" class="btn btn-ghost btn-sm" style="color:var(--danger-text, #ef4444); padding:0.2rem 0.4rem; font-size:0.85rem;" onclick="removeVisualAnalyteRow(this)" title="Remove parameter">
        🗑️
      </button>
    </td>
  `;
  tbody.appendChild(tr);
  updateVisualAnalyteIndices();
  syncVisualAnalytesToJson();

  if (isUserTriggered) {
    const rowNum = tbody.querySelectorAll("tr.visual-analyte-row").length;
    tr.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const nameInput = tr.querySelector(".analyte-name");
    if (nameInput) {
      setTimeout(() => nameInput.focus(), 120);
    }
    showToast(`Added new parameter row #${rowNum} at bottom of table`, "info");
  }
}

function removeVisualAnalyteRow(btn) {
  const tr = btn.closest("tr");
  if (tr) tr.remove();
  const tbody = document.getElementById("visualAnalyteTableBody");
  const notice = document.getElementById("visualAnalyteEmptyNotice");
  if (tbody && tbody.children.length === 0 && notice) {
    notice.style.display = "block";
  }
  updateVisualAnalyteIndices();
  syncVisualAnalytesToJson();
}

function loadPresetAnalyteSchema(presetKey) {
  const preset = PRESET_ANALYTES[presetKey];
  if (!preset) return;
  initVisualAnalyteBuilder(preset);
  showToast(`Pre-filled ${presetKey} panel parameters!`, "info");
}

function syncVisualAnalytesToJson() {
  const tbody = document.getElementById("visualAnalyteTableBody");
  const hiddenJson = document.getElementById("tmplParamsJsonInput");
  if (!tbody || !hiddenJson) return;
  
  const rows = tbody.querySelectorAll("tr.visual-analyte-row");
  const list = [];
  rows.forEach(r => {
    const name = r.querySelector(".analyte-name")?.value.trim() || "";
    const unit = r.querySelector(".analyte-unit")?.value.trim() || "";
    const range = r.querySelector(".analyte-range")?.value.trim() || "";
    const default_val = r.querySelector(".analyte-default")?.value.trim() || "";
    if (name) {
      list.push({ name, unit, range, default_val });
    }
  });
  hiddenJson.value = list.length > 0 ? JSON.stringify(list) : "";
}

async function handleSaveTemplate(e) {
  e.preventDefault();
  syncVisualAnalytesToJson();
  const templateId = document.getElementById("editTemplateId").value;
  const isEdit = Boolean(templateId);

  const payload = {
    test_code: document.getElementById("tmplCodeInput").value.trim().toUpperCase(),
    test_name: document.getElementById("tmplNameInput").value.trim(),
    department: document.getElementById("tmplDeptSelect").value,
    modality: document.getElementById("tmplModalitySelect").value || null,
    standard_rate: parseInt(document.getElementById("tmplRateInput").value, 10),
    sample_type: document.getElementById("tmplSampleInput").value.trim() || "Specimen",
    normal_range: document.getElementById("tmplRangeInput").value.trim() || null,
    unit_of_measurement: document.getElementById("tmplUnitInput").value.trim() || null,
    parameters_json: document.getElementById("tmplParamsJsonInput").value.trim() || null,
    template_text: document.getElementById("tmplTemplateTextInput").value.trim() || null,
    is_active: document.getElementById("tmplIsActiveInput").checked
  };

  try {
    if (isEdit) {
      await apiFetch(`/api/lab/templates/${templateId}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      showToast("Template updated successfully!", "success");
    } else {
      await apiFetch("/api/lab/templates", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      showToast("New investigation template created!", "success");
    }
    closeModal("templateEditModal");
    loadTemplatesTable();
    loadAllTemplatesCatalog();
  } catch (err) {
    showToast("Failed to save template: " + (err.message || "Validation error"), "error");
  }
}

// ============================================================================
// DIAGNOSTIC ANALYTICS & ALERTS
// ============================================================================

async function loadDiagnosticAnalytics() {
  try {
    const data = await apiFetch("/api/lab/analytics");
    if (!data) return;

    const kpiOrders = document.getElementById("kpiLabOrders");
    const kpiPendingColl = document.getElementById("kpiLabPendingColl");
    const kpiInAnalysis = document.getElementById("kpiLabInAnalysis");
    const kpiPanic = document.getElementById("kpiLabPanic");
    const kpiPanicSub = document.getElementById("kpiLabPanicSub");

    if (kpiOrders) kpiOrders.textContent = data.kpis.total_orders ?? 0;
    if (kpiPendingColl) kpiPendingColl.textContent = data.kpis.pending_collection ?? 0;
    if (kpiInAnalysis) kpiInAnalysis.textContent = data.kpis.in_analysis ?? 0;
    if (kpiPanic) kpiPanic.textContent = data.kpis.review_count ?? 0;
    if (kpiPanicSub) {
      kpiPanicSub.textContent = `${data.kpis.review_count ?? 0} outside configured range`;
    }

    renderLabAlerts(data.alerts || []);
  } catch (err) {
    console.error("Failed to load lab analytics:", err);
  }
}

function renderLabAlerts(alerts) {
  const container = document.getElementById("labAlertsContainer");
  if (!container) return;

  if (!alerts || alerts.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  container.style.display = "block";
  const count = alerts.length;

  container.innerHTML = `
    <div class="card" style="border-left:4px solid #ef4444; background:#fff1f2; padding:0; overflow:hidden;">
      <div style="display:flex; justify-content:space-between; align-items:center; padding:0.75rem 1rem; border-bottom:1px solid #fecdd3;">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <svg class="icon" style="color:#e11d48;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <strong style="color:#9f1239;">Diagnostic Alerts &amp; Panic Values (${count} Required Action${count > 1 ? 's' : ''})</strong>
        </div>
      </div>
      <div style="padding:0.75rem 1rem; display:flex; flex-direction:column; gap:0.4rem;">
        ${alerts.map(a => `
          <div style="display:flex; justify-content:space-between; align-items:center; background:#ffffff; border:1px solid #fed7aa; border-radius:var(--radius-md); padding:0.5rem 0.75rem;">
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <span class="badge ${a.severity === 'danger' ? 'badge-danger' : 'badge-warning'}" style="font-size:0.7rem;">${escapeHtml(a.type)}</span>
              <span style="font-size:0.825rem; color:var(--text-main);">${escapeHtml(a.message)}</span>
            </div>
            ${a.type === 'SAMPLE_COLLECTION_PENDING' ? `
              <button class="btn btn-primary btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem;" onclick="markSampleCollected(${a.order_id})">
                Accession Specimen
              </button>
            ` : `
              <span class="badge badge-secondary" style="font-size:0.7rem;">${escapeHtml(a.action)}</span>
            `}
          </div>
        `).join("")}
      </div>
    </div>
  `;
}
