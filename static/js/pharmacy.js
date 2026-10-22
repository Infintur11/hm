/**
 * Closed-Loop Pharmacy Dispensary & Formulary Intelligence Module
 */

let stockChartInstance = null;
let categoryChartInstance = null;
window._medicinesCache = [];

document.addEventListener("DOMContentLoaded", () => {
  refreshAllPharmacyData();
});

async function refreshAllPharmacyData() {
  await Promise.all([
    loadPharmacyAnalytics(),
    loadPharmacyQueue(),
    loadFormularyStock()
  ]);
}

/**
 * 1. Analytics, KPIs, Visual Charts & Forecast Engine
 */
async function loadPharmacyAnalytics() {
  try {
    const data = await apiFetch("/api/pharmacy/analytics");
    if (!data) return;

    // A. Update Top KPI Cards
    const kpis = data.kpis || {};
    const kpiSkus = document.getElementById("kpiSkus");
    const kpiValuation = document.getElementById("kpiValuation");
    const kpiTotalUnits = document.getElementById("kpiTotalUnits");
    const kpiAlerts = document.getElementById("kpiAlerts");
    const kpiAlertSub = document.getElementById("kpiAlertSub");
    const kpiClearance = document.getElementById("kpiClearance");
    const kpiDispenseBreakdown = document.getElementById("kpiDispenseBreakdown");
    const kpiRunout = document.getElementById("kpiRunout");

    if (kpiSkus) kpiSkus.innerText = `${kpis.total_skus || 0} SKUs`;
    if (kpiValuation) kpiValuation.innerText = `₹${(kpis.total_inventory_value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    if (kpiTotalUnits) kpiTotalUnits.innerText = `${(kpis.total_units || 0).toLocaleString()} units on shelf`;
    if (kpiAlerts) kpiAlerts.innerText = `${kpis.low_stock_count || 0} Alert${kpis.low_stock_count !== 1 ? 's' : ''}`;
    if (kpiAlertSub) kpiAlertSub.innerText = `${kpis.low_stock_count || 0} items at/below reorder limit`;
    if (kpiClearance) kpiClearance.innerText = `${kpis.clearance_rate_pct || 100}%`;
    if (kpiDispenseBreakdown) kpiDispenseBreakdown.innerText = `${kpis.prescriptions_dispensed || 0} dispensed • ${kpis.prescriptions_pending || 0} pending`;
    if (kpiRunout) kpiRunout.innerText = `${kpis.critical_runout_count || 0} SKUs`;

    // B. Render Alert Banners
    renderAlertBanners(data.alerts || []);

    // C. Render Charts
    renderStockBarChart(data.stock_comparison || []);
    renderCategoryDonutChart(data.categories || []);

    // D. Render 14-Day Forecast Table
    renderForecastTable(data.forecast || []);

    // E. Populate Restock Dropdown
    populateRestockDropdown(data.stock_comparison || []);

  } catch (err) {
    console.warn("Could not load pharmacy analytics:", err);
  }
}

window._alertsCache = [];
window._alertsDropdownOpen = false;

/**
 * Render Active Alert Banners as a Collapsible Dropdown
 */
function renderAlertBanners(alerts) {
  const container = document.getElementById("pharmacyAlertsContainer");
  if (!container) return;

  window._alertsCache = alerts || [];

  if (!alerts || alerts.length === 0) {
    container.style.display = "none";
    container.innerHTML = "";
    return;
  }

  const criticalCount = alerts.filter(a => a.severity === 'danger').length;
  const warningCount = alerts.filter(a => a.severity === 'warning').length;

  container.style.display = "block";
  container.innerHTML = `
    <div style="background:rgba(239, 68, 68, 0.07); border:1px solid var(--danger-border); border-radius:var(--radius-md); padding:0.85rem 1.15rem; margin-bottom:1.5rem; transition:all 0.2s ease;">
      <!-- Dropdown Header Bar -->
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.6rem; cursor:pointer;" onclick="toggleAlertsDropdown(event)">
        <div style="display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap;">
          <span style="display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:50%; background:rgba(239, 68, 68, 0.15); color:var(--danger-text);">
            <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          </span>
          <div>
            <strong style="color:var(--danger-text); font-size:var(--font-sm);">
              ${alerts.length} Actionable Inventory &amp; Stockout Warning${alerts.length > 1 ? 's' : ''} Detected
            </strong>
            <span style="font-size:var(--font-xs); color:var(--text-muted); margin-left:0.5rem;">
              (${criticalCount} critical &bull; ${warningCount} reorder warnings)
            </span>
          </div>
        </div>

        <div style="display:flex; align-items:center; gap:0.5rem;" onclick="event.stopPropagation()">
          <button type="button" class="btn btn-outline btn-sm" id="alertsDropdownToggleBtn" onclick="toggleAlertsDropdown(event)" style="display:inline-flex; align-items:center; gap:0.35rem; font-size:var(--font-xs); background:#fff; padding:0.3rem 0.65rem;">
            <span id="alertsDropdownBtnText">${window._alertsDropdownOpen ? 'Collapse Warnings' : `Expand Warnings (${alerts.length})`}</span>
            <svg id="alertsDropdownChevron" class="icon icon-sm" style="transition:transform 0.2s ease; transform:${window._alertsDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)'};" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Collapsible Dropdown Content Container -->
      <div id="alertsDropdownContent" style="display:${window._alertsDropdownOpen ? 'block' : 'none'}; margin-top:0.75rem; padding-top:0.75rem; border-top:1px solid rgba(239, 68, 68, 0.2);">
        <!-- Search filter for 1000s of alerts -->
        <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem; margin-bottom:0.6rem; flex-wrap:wrap;">
          <input type="text" id="alertsSearchInput" class="form-control form-control-sm" placeholder="Search alerts by medicine name..." oninput="filterAlertsList(this.value)" style="max-width:280px; font-size:var(--font-xs); background:#fff; padding:0.3rem 0.6rem;">
          <span id="alertsCountLabel" style="font-size:var(--font-xs); color:var(--text-muted);">
            Showing all ${alerts.length} alerts &bull; Max 260px scrollable view
          </span>
        </div>

        <!-- Scrollable Alerts Viewport -->
        <div id="alertsListContainer" style="max-height:260px; overflow-y:auto; display:flex; flex-direction:column; gap:0.4rem; padding-right:0.3rem;">
          ${renderAlertItemsHtml(alerts)}
        </div>
      </div>
    </div>
  `;
}

function renderAlertItemsHtml(alertItems) {
  if (!alertItems || alertItems.length === 0) {
    return `<div style="text-align:center; padding:1rem; font-size:var(--font-xs); color:var(--text-muted); background:#fff; border-radius:var(--radius-sm);">No matching warnings found.</div>`;
  }

  return alertItems.map(a => `
    <div style="display:flex; justify-content:space-between; align-items:center; background:#fff; padding:0.45rem 0.8rem; border-radius:var(--radius-sm); border:1px solid rgba(239, 68, 68, 0.2); font-size:var(--font-xs); gap:0.5rem; flex-wrap:wrap;">
      <div style="display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap;">
        <span class="badge ${a.severity === 'danger' ? 'badge-danger' : 'badge-warning'}" style="font-size:0.7rem; padding:0.15rem 0.45rem;">
          ${a.type.replace('_', ' ')}
        </span>
        <span style="color:var(--text-main);">${a.message}</span>
      </div>
      <button class="btn btn-primary btn-sm" onclick="openRestockModal(${a.medicine_id}, '${a.medicine_name}', 50)" style="padding:0.2rem 0.6rem; font-size:0.75rem; white-space:nowrap; display:inline-flex; align-items:center; gap:0.25rem;">
        <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>${a.action || 'Replenish'}</span>
      </button>
    </div>
  `).join("");
}

function toggleAlertsDropdown(e) {
  if (e) e.stopPropagation();
  window._alertsDropdownOpen = !window._alertsDropdownOpen;

  const content = document.getElementById("alertsDropdownContent");
  const btnText = document.getElementById("alertsDropdownBtnText");
  const chevron = document.getElementById("alertsDropdownChevron");

  if (content) {
    content.style.display = window._alertsDropdownOpen ? "block" : "none";
  }
  if (btnText) {
    btnText.innerText = window._alertsDropdownOpen ? "Collapse Warnings" : `Expand Warnings (${(window._alertsCache || []).length})`;
  }
  if (chevron) {
    chevron.style.transform = window._alertsDropdownOpen ? "rotate(180deg)" : "rotate(0deg)";
  }
}

function filterAlertsList(query) {
  const q = (query || "").toLowerCase().trim();
  const listContainer = document.getElementById("alertsListContainer");
  const countLabel = document.getElementById("alertsCountLabel");
  if (!listContainer) return;

  const filtered = (window._alertsCache || []).filter(a => 
    (a.medicine_name || "").toLowerCase().includes(q) ||
    (a.message || "").toLowerCase().includes(q) ||
    (a.type || "").toLowerCase().includes(q)
  );

  listContainer.innerHTML = renderAlertItemsHtml(filtered);
  if (countLabel) {
    countLabel.innerText = `Showing ${filtered.length} of ${window._alertsCache.length} alerts`;
  }
}

/**
 * Bar Chart: Stock vs Reorder Level
 */
function renderStockBarChart(items) {
  const canvas = document.getElementById("stockBarChart");
  if (!canvas || typeof Chart === 'undefined') return;

  const topItems = items.slice(0, 10);
  const labels = topItems.map(i => i.brand_name);
  const stockData = topItems.map(i => i.stock_quantity);
  const reorderData = topItems.map(i => i.reorder_level);

  const backgroundColors = topItems.map(i => {
    if (i.health_status === 'CRITICAL' || i.stock_quantity <= i.reorder_level) return 'rgba(239, 68, 68, 0.85)';
    if (i.health_status === 'WARNING') return 'rgba(245, 158, 11, 0.85)';
    return 'rgba(16, 185, 129, 0.85)';
  });

  if (stockChartInstance) {
    stockChartInstance.destroy();
  }

  stockChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Available Units on Shelf',
          data: stockData,
          backgroundColor: backgroundColors,
          borderRadius: 4,
          maxBarThickness: 32
        },
        {
          label: 'Safety Reorder Trigger',
          data: reorderData,
          type: 'line',
          borderColor: '#64748b',
          borderWidth: 2,
          borderDash: [4, 4],
          pointRadius: 4,
          pointBackgroundColor: '#64748b',
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: { font: { size: 11 } }
        },
        tooltip: {
          callbacks: {
            footer: (items) => {
              const index = items[0].dataIndex;
              const item = topItems[index];
              return `Status: ${item.health_status} | Unit Price: ₹${item.unit_price}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Quantity (Units)', font: { size: 11 } },
          grid: { color: 'rgba(0,0,0,0.05)' }
        },
        x: {
          ticks: { font: { size: 10 } },
          grid: { display: false }
        }
      }
    }
  });
}

/**
 * Doughnut Chart: Therapeutic Category Mix
 */
function renderCategoryDonutChart(categories) {
  const canvas = document.getElementById("categoryDonutChart");
  if (!canvas || typeof Chart === 'undefined') return;

  const topCats = categories.slice(0, 6);
  const labels = topCats.map(c => c.category);
  const values = topCats.map(c => c.value);

  const palette = [
    '#2563eb', // Slate Blue
    '#10b981', // Emerald
    '#f59e0b', // Amber
    '#8b5cf6', // Violet
    '#06b6d4', // Cyan
    '#ef4444', // Crimson
  ];

  if (categoryChartInstance) {
    categoryChartInstance.destroy();
  }

  categoryChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: palette.slice(0, labels.length),
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { boxWidth: 12, font: { size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const val = ctx.raw || 0;
              const cat = topCats[ctx.dataIndex];
              return ` ${ctx.label}: ₹${val.toLocaleString('en-IN')} (${cat.skus} SKUs, ${cat.units} units)`;
            }
          }
        }
      },
      cutout: '62%'
    }
  });
}

/**
 * Render 14-Day Stockout Forecast Table
 */
function renderForecastTable(forecastItems) {
  const tbody = document.getElementById("forecastTableBody");
  if (!tbody) return;

  if (!forecastItems || forecastItems.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No active medications found.</td></tr>`;
    return;
  }

  tbody.innerHTML = forecastItems.map(f => {
    let statusBadge = `<span class="badge badge-success">Healthy Supply</span>`;
    let daysDisplay = `<strong style="color:var(--success-text);">${f.days_remaining}d</strong>`;

    if (f.urgency === 'STOCKOUT') {
      statusBadge = `<span class="badge badge-danger">OUT OF STOCK</span>`;
      daysDisplay = `<strong style="color:var(--danger-text);">0 days (Depleted)</strong>`;
    } else if (f.urgency === 'URGENT') {
      statusBadge = `<span class="badge badge-danger">CRITICAL RUNOUT</span>`;
      daysDisplay = `<strong style="color:var(--danger-text);">${f.days_remaining} days</strong>`;
    } else if (f.urgency === 'REORDER_SOON') {
      statusBadge = `<span class="badge badge-warning">REORDER SOON</span>`;
      daysDisplay = `<strong style="color:#d97706;">${f.days_remaining} days</strong>`;
    }

    return `
      <tr>
        <td>
          <strong>${f.brand_name}</strong><br>
          <small style="color:var(--text-muted);">${f.generic_name} &bull; ${f.dosage_form}</small>
        </td>
        <td>
          <span style="font-weight:600; color:${f.stock_quantity <= f.reorder_level ? 'var(--danger-text)' : 'inherit'};">
            ${f.stock_quantity} units
          </span>
        </td>
        <td>${f.reorder_level} units</td>
        <td><strong>~${f.daily_burn_velocity}</strong> <small style="color:var(--text-muted);">units/day</small></td>
        <td>${daysDisplay}</td>
        <td><small>${f.runout_date}</small></td>
        <td>
          <span class="badge badge-neutral">+${f.suggested_reorder_qty} units</span>
        </td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="openRestockModal(${f.id}, '${f.brand_name}', ${f.suggested_reorder_qty})" style="padding:0.25rem 0.55rem; font-size:var(--font-xs); display:inline-flex; align-items:center; gap:0.25rem;">
            <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>Restock</span>
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

/**
 * 2. Active Prescription Queue (Closed-Loop Gatekeeper)
 */
async function loadPharmacyQueue() {
  const tbody = document.getElementById("pharmacyQueueBody");
  if (!tbody) return;

  try {
    const queue = await apiFetch("/api/pharmacy/queue");
    if (!queue || queue.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:2rem;">No pending prescriptions in dispensary queue.</td></tr>`;
      return;
    }

    tbody.innerHTML = queue.map(q => `
      <tr>
        <td><strong>${q.patient_name}</strong><br><small style="color:var(--text-muted);">${q.patient_phone}</small></td>
        <td><strong>${q.medicine_name}</strong><br><small>${q.dosage} (${q.frequency})</small></td>
        <td>${q.quantity_prescribed} units<br><small>${q.instructions}</small></td>
        <td>
          ${q.current_stock > 10 ? 
            `<span class="badge badge-success">${q.current_stock} in stock</span>` : 
            `<span class="badge badge-danger">Low Stock (${q.current_stock})</span>`}
        </td>
        <td>
          ${q.is_paid ? 
            `<span class="badge badge-success" style="display:inline-flex; align-items:center; gap:0.3rem;"><svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"/></svg> Zero Balance (${q.invoice_number})</span>` : 
            `<span class="badge badge-danger" style="display:inline-flex; align-items:center; gap:0.3rem;"><svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Payment Locked (${q.invoice_number})</span>`}
        </td>
        <td>
          ${q.is_dispensed ? 
            `<span class="badge badge-success">Dispensed</span>` : 
            `<span class="badge badge-warning">Awaiting Dispense</span>`}
        </td>
        <td>
          ${q.is_dispensed ? `
            <span style="font-size:var(--font-xs); color:var(--text-muted);">Dispensed &amp; Logged</span>
          ` : q.is_paid ? `
            <button class="btn btn-success btn-sm" onclick="dispenseMedication(${q.id}, '${q.medicine_name}')" style="display:inline-flex; align-items:center; gap:0.25rem;">
              <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="20 6 9 17 4 12"/></svg>
              <span>Verify &amp; Dispense</span>
            </button>
          ` : `
            <button class="btn btn-secondary btn-sm" disabled style="opacity:0.65; cursor:not-allowed; display:inline-flex; align-items:center; gap:0.25rem;" title="Invoice balance outstanding. Direct patient to Cashier desk.">
              <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              <span>Locked (Awaiting Cashier)</span>
            </button>
          `}
        </td>
      </tr>
    `).join("");
  } catch (err) {}
}

async function dispenseMedication(prescriptionItemId, medName) {
  try {
    await apiFetch("/api/pharmacy/dispense", {
      method: "POST",
      body: JSON.stringify({ prescription_item_id: prescriptionItemId })
    });
    showToast(`Dispensed ${medName}! Stock auto-decremented.`, "success");
    refreshAllPharmacyData();
  } catch (err) {}
}

/**
 * 3. Hospital Formulary Catalog & Live Search
 */
async function loadFormularyStock() {
  try {
    const meds = await apiFetch("/api/pharmacy/medicines");
    window._medicinesCache = meds || [];
    renderFormularyTable(window._medicinesCache);
  } catch (err) {}
}

function renderFormularyTable(meds) {
  const tbody = document.getElementById("formularyTableBody");
  if (!tbody) return;

  if (!meds || meds.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No matching medicines found in catalog.</td></tr>`;
    return;
  }

  tbody.innerHTML = meds.map(m => `
    <tr>
      <td><strong>${m.brand_name}</strong></td>
      <td>${m.generic_name}</td>
      <td><span class="badge badge-neutral">${m.category}</span></td>
      <td>${m.dosage_form} (${m.strength})</td>
      <td><small style="color:var(--text-muted);">${m.batch_number} &bull; Exp: ${m.expiry_date}</small></td>
      <td>
        <strong style="color:${m.is_low_stock ? 'var(--danger-text)' : 'inherit'};">${m.stock_quantity}</strong>
        ${m.is_low_stock ? `<span class="badge badge-danger" style="margin-left:0.35rem;">Reorder</span>` : ''}
      </td>
      <td>${m.reorder_level || 20}</td>
      <td>₹${m.unit_price.toFixed(2)}</td>
      <td>
        <button class="btn btn-primary btn-sm" onclick="openRestockModal(${m.id}, '${m.brand_name}', 50)" style="padding:0.2rem 0.55rem; font-size:var(--font-xs); display:inline-flex; align-items:center; gap:0.2rem;">
          <svg class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          <span>Restock</span>
        </button>
      </td>
    </tr>
  `).join("");
}

function filterFormularyTable() {
  const q = (document.getElementById("formularySearch").value || "").toLowerCase().trim();
  if (!q) {
    renderFormularyTable(window._medicinesCache);
    return;
  }
  const filtered = window._medicinesCache.filter(m => 
    m.brand_name.toLowerCase().includes(q) ||
    m.generic_name.toLowerCase().includes(q) ||
    m.category.toLowerCase().includes(q)
  );
  renderFormularyTable(filtered);
}

/**
 * 4. Quick Restock Modal Logic
 */
function populateRestockDropdown(medicines) {
  const select = document.getElementById("restockMedicineSelect");
  if (!select) return;

  const currentVal = select.value;
  select.innerHTML = `<option value="">-- Choose medication to restock --</option>` + 
    medicines.map(m => `
      <option value="${m.id}">${m.brand_name} (Current Stock: ${m.stock_quantity} | Safety: ${m.reorder_level})</option>
    `).join("");

  if (currentVal) select.value = currentVal;
}

function openRestockModal(medId = null, medName = null, suggestedQty = 50) {
  const select = document.getElementById("restockMedicineSelect");
  const qtyInput = document.getElementById("restockQuantityInput");
  const batchInput = document.getElementById("restockBatchInput");

  if (select && medId) {
    select.value = medId;
  }
  if (qtyInput) {
    qtyInput.value = suggestedQty || 50;
  }
  if (batchInput) {
    batchInput.value = `BAT-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;
  }

  openModal("restockModal");
}

function quickSetQuantity(qty) {
  const qtyInput = document.getElementById("restockQuantityInput");
  if (qtyInput) {
    qtyInput.value = qty;
  }
}

async function handleRestockSubmit(e) {
  e.preventDefault();
  const select = document.getElementById("restockMedicineSelect");
  const qtyInput = document.getElementById("restockQuantityInput");
  const batchInput = document.getElementById("restockBatchInput");
  const submitBtn = document.getElementById("restockSubmitBtn");

  const medId = parseInt(select.value);
  const qty = parseInt(qtyInput.value);
  const batch = batchInput.value.trim() || null;

  if (!medId || isNaN(qty) || qty <= 0) {
    showToast("Please select a medicine and enter a valid quantity.", "error");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerText = "Restocking...";

  try {
    const res = await apiFetch("/api/pharmacy/restock", {
      method: "POST",
      body: JSON.stringify({
        medicine_id: medId,
        quantity_to_add: qty,
        batch_number: batch
      })
    });

    showToast(`Replenished +${qty} units of ${res.brand_name}! (Total Stock: ${res.new_stock})`, "success");
    closeModal("restockModal");
    refreshAllPharmacyData();
  } catch (err) {
    // Handled by apiFetch
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerText = "Confirm Restock";
  }
}

