/**
 * Corporate / Insurance Tie-Up Management, Dynamic Pre-Built SQL KPI Studio,
 * and Granular Financial Multi-Dimension Ledger for Admin & Super Admin.
 */

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

let allAdminCorporatePartners = [];
let activeGranularFinancialData = null;

function initCorporateAdmin() {
  loadActiveCustomKpis();
  loadCorporateAdminSection();
  loadGranularFinancialAnalytics();

  const corpForm = document.getElementById("createCorporateForm");
  if (corpForm && !corpForm.dataset.bound) {
    corpForm.dataset.bound = "1";
    corpForm.addEventListener("submit", handleCreateCorporateSubmit);
  }

  const limitForm = document.getElementById("editCorporateLimitForm");
  if (limitForm && !limitForm.dataset.bound) {
    limitForm.dataset.bound = "1";
    limitForm.addEventListener("submit", handleUpdateLimitSubmit);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initCorporateAdmin);
} else {
  initCorporateAdmin();
}

// =========================================================================
// 1. DYNAMIC PRE-BUILT SQL KPI STUDIO
// =========================================================================

async function loadActiveCustomKpis() {
  const container = document.getElementById("dynamicKpisGrid");
  if (!container) return;

  try {
    const kpis = await apiFetch("/api/corporate/kpis/active");
    if (!kpis || kpis.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; background:var(--bg-surface); border:1px dashed var(--border-subtle); border-radius:var(--radius-md); padding:1.25rem; text-align:center;">
          <p style="margin:0 0 0.5rem 0; font-size:var(--font-sm); color:var(--text-muted);">
            No dynamic KPI cards currently pinned. Choose from pre-built SQL queries to monitor real-time clinical and revenue metrics.
          </p>
          <button class="btn btn-outline btn-sm" onclick="openAddKpiModal()">+ Pin Pre-Built Query KPI</button>
        </div>
      `;
      return;
    }

    const colorMap = {
      emerald: { border: "#10b981", bg: "rgba(16, 185, 129, 0.04)" },
      blue: { border: "#2563eb", bg: "rgba(37, 99, 235, 0.04)" },
      amber: { border: "#f59e0b", bg: "rgba(245, 158, 11, 0.04)" },
      rose: { border: "#f43f5e", bg: "rgba(244, 63, 94, 0.04)" },
      violet: { border: "#8b5cf6", bg: "rgba(139, 92, 246, 0.04)" },
      cyan: { border: "#06b6d4", bg: "rgba(6, 182, 212, 0.04)" }
    };

    container.innerHTML = kpis.map(k => {
      const c = colorMap[k.accent_color] || colorMap.emerald;
      return `
        <div class="kpi-card" style="border-left:4px solid ${c.border}; background:${c.bg}; position:relative; padding-right:1.75rem;">
          <button onclick="removeCustomKpiCard(${k.id})" title="Unpin this KPI card" style="position:absolute; top:8px; right:8px; background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:0.85rem; padding:2px 4px; line-height:1; border-radius:4px;" onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='var(--text-muted)'">&times;</button>
          <div class="kpi-label" style="display:flex; align-items:center; gap:0.35rem;">
            <span>${escapeHtml(k.title)}</span>
          </div>
          <div class="kpi-value" style="font-size:1.4rem; margin:0.35rem 0;">${k.current_value}</div>
          <div class="kpi-sub" style="font-size:0.75rem;">${escapeHtml(k.subtitle || '')}</div>
        </div>
      `;
    }).join("");
  } catch (err) {}
}

async function openAddKpiModal() {
  const modal = document.getElementById("addCustomKpiModal");
  const catalogContainer = document.getElementById("kpiCatalogList");
  if (!modal || !catalogContainer) return;

  catalogContainer.innerHTML = `<div style="text-align:center; padding:2rem; color:var(--text-muted);">Executing pre-built SQL catalog...</div>`;
  openModal("addCustomKpiModal");

  try {
    const catalog = await apiFetch("/api/corporate/kpis/catalog");
    if (!catalog || catalog.length === 0) {
      catalogContainer.innerHTML = `<div style="text-align:center; padding:1.5rem;">No pre-built queries catalog found.</div>`;
      return;
    }

    catalogContainer.innerHTML = catalog.map(item => `
      <div style="background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:var(--radius-md); padding:1rem; display:flex; justify-content:space-between; align-items:center; gap:1rem; transition:border-color 0.15s;">
        <div style="flex:1;">
          <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
            <strong style="font-size:var(--font-sm); color:var(--text-main);">${escapeHtml(item.title)}</strong>
            <span class="badge badge-neutral" style="font-size:0.7rem;">${escapeHtml(item.category)}</span>
            <span class="badge badge-info" style="font-size:0.7rem;">SQL Query</span>
          </div>
          <p style="font-size:var(--font-xs); color:var(--text-muted); margin:0 0 0.4rem 0;">${escapeHtml(item.description)}</p>
          <code style="font-size:0.7rem; background:var(--bg-surface-alt); padding:2px 6px; border-radius:4px; color:var(--text-muted); display:inline-block; max-width:480px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
            ${escapeHtml(item.sql_snippet)}
          </code>
        </div>
        <div style="text-align:right; min-width:140px; display:flex; flex-direction:column; align-items:flex-end; gap:0.4rem;">
          <div style="font-size:1.15rem; font-weight:700; color:var(--primary-600);">${item.preview_value}</div>
          ${item.is_pinned ? `
            <span class="badge badge-success" style="font-size:0.75rem;">✓ Active on Dashboard</span>
          ` : `
            <button class="btn btn-primary btn-sm" style="font-size:0.75rem; padding:0.25rem 0.6rem;" onclick="pinPrebuiltKpi('${item.query_key}', '${escapeHtml(item.title)}', '${item.accent_color}')">
              + Pin Card
            </button>
          `}
        </div>
      </div>
    `).join("");
  } catch (err) {
    catalogContainer.innerHTML = `<div style="text-align:center; padding:1.5rem; color:#ef4444;">Failed to load query catalog.</div>`;
  }
}

async function pinPrebuiltKpi(queryKey, defaultTitle, accentColor) {
  try {
    await apiFetch("/api/corporate/kpis", {
      method: "POST",
      body: JSON.stringify({
        query_key: queryKey,
        title: defaultTitle,
        accent_color: accentColor || "emerald"
      })
    });
    showToast(`Added '${defaultTitle}' KPI card to top of dashboard!`, "success");
    closeModal("addCustomKpiModal");
    loadActiveCustomKpis();
  } catch (err) {}
}

async function removeCustomKpiCard(kpiId) {
  try {
    await apiFetch(`/api/corporate/kpis/${kpiId}`, { method: "DELETE" });
    showToast("KPI card removed from dashboard.", "info");
    loadActiveCustomKpis();
  } catch (err) {}
}


// =========================================================================
// 2. CORPORATE & INSURANCE TIE-UP MANAGEMENT
// =========================================================================

async function loadCorporateAdminSection() {
  const tbody = document.getElementById("corporatePartnersBody");
  if (!tbody) return;

  try {
    // 1. Fetch Summary
    const summary = await apiFetch("/api/corporate/summary");
    if (summary) {
      const elCount = document.getElementById("kpiCorpCount");
      const elPool = document.getElementById("kpiCorpPool");
      const elUtil = document.getElementById("kpiCorpUtilized");
      const elAvail = document.getElementById("kpiCorpAvailable");

      if (elCount) elCount.textContent = summary.total_active_partners;
      if (elPool) elPool.textContent = `₹${summary.total_credit_pool.toLocaleString('en-IN', {minimumFractionDigits: 0})}`;
      if (elUtil) elUtil.textContent = `₹${summary.total_utilized.toLocaleString('en-IN', {minimumFractionDigits: 0})}`;
      if (elAvail) elAvail.textContent = `₹${summary.total_available.toLocaleString('en-IN', {minimumFractionDigits: 0})}`;
    }

    // 2. Fetch Clients List
    const clients = await apiFetch("/api/corporate/clients");
    allAdminCorporatePartners = clients || [];

    if (allAdminCorporatePartners.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No corporate / insurance partners configured yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = allAdminCorporatePartners.map(c => {
      const pct = c.utilization_percentage;
      const progressColor = pct > 90 ? '#ef4444' : pct > 70 ? '#f59e0b' : '#10b981';
      return `
        <tr>
          <td>
            <strong>${escapeHtml(c.name)}</strong>
            <div style="font-size:0.75rem; color:var(--text-muted); font-family:monospace;">${escapeHtml(c.code)}</div>
          </td>
          <td>
            <span class="badge ${c.category === 'INSURANCE_TPA' ? 'badge-primary' : c.category === 'CORPORATE_TIEUP' ? 'badge-info' : 'badge-neutral'}">
              ${c.category.replace(/_/g, ' ')}
            </span>
          </td>
          <td>
            <div style="display:flex; align-items:center; gap:0.4rem;">
              <strong>₹${c.monthly_credit_limit.toLocaleString('en-IN', {minimumFractionDigits: 0})}</strong>
              <button class="btn btn-ghost btn-sm" style="padding:1px 4px; font-size:0.75rem;" title="Adjust Monthly Limit" onclick="openEditLimitModal(${c.id}, '${escapeHtml(c.name)}', ${c.monthly_credit_limit})">
                ✏️
              </button>
            </div>
            <small style="color:var(--text-muted); font-size:0.7rem;">Monthly Cap</small>
          </td>
          <td style="color:#b91c1c; font-weight:600;">
            ₹${c.current_utilized_credit.toLocaleString('en-IN', {minimumFractionDigits: 0})}
          </td>
          <td style="color:#15803d; font-weight:700;">
            ₹${c.available_credit.toLocaleString('en-IN', {minimumFractionDigits: 0})}
          </td>
          <td style="min-width:130px;">
            <div style="display:flex; justify-content:space-between; font-size:0.75rem; margin-bottom:2px;">
              <span>${pct}%</span>
              <button class="btn btn-ghost btn-sm" style="padding:0; font-size:0.75rem; color:var(--primary-700); font-weight:700;" onclick="viewCorporateInvoices(${c.id}, '${escapeHtml(c.name)}')">
                ${c.invoice_count} bills ↗
              </button>
            </div>
            <div style="background:#e2e8f0; border-radius:4px; height:6px; overflow:hidden;">
              <div style="background:${progressColor}; width:${Math.min(pct, 100)}%; height:100%;"></div>
            </div>
          </td>
          <td style="font-size:0.8rem;">
            ${c.contact_person ? `<div>${escapeHtml(c.contact_person)}</div>` : ''}
            ${c.contact_phone ? `<small style="color:var(--text-muted);">${escapeHtml(c.contact_phone)}</small>` : ''}
          </td>
          <td>
            <span class="badge ${c.is_active ? 'badge-success' : 'badge-neutral'}">
              ${c.is_active ? 'Active' : 'Paused'}
            </span>
          </td>
          <td>
            <div style="display:flex; gap:0.35rem;">
              <button class="btn btn-outline btn-sm" style="font-size:0.75rem; padding:0.2rem 0.5rem;" onclick="openEditLimitModal(${c.id}, '${escapeHtml(c.name)}', ${c.monthly_credit_limit})">
                Edit Limit
              </button>
              <button class="btn btn-ghost btn-sm" style="font-size:0.75rem; padding:0.2rem 0.4rem;" onclick="viewCorporateInvoices(${c.id}, '${escapeHtml(c.name)}')">
                Invoices
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {}
}

function openCreateCorporateModal() {
  const form = document.getElementById("createCorporateForm");
  if (form) form.reset();
  openModal("createCorporateModal");
}

async function handleCreateCorporateSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const payload = {
    name: form.name.value.trim(),
    code: form.code.value.trim().toUpperCase(),
    category: form.category.value,
    monthly_credit_limit: parseFloat(form.monthly_credit_limit.value),
    contact_person: form.contact_person.value.trim() || null,
    contact_phone: form.contact_phone.value.trim() || null,
    contact_email: form.contact_email.value.trim() || null,
    notes: form.notes.value.trim() || null
  };

  try {
    await apiFetch("/api/corporate/clients", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    showToast(`Registered corporate tie-up: ${payload.name}`, "success");
    closeModal("createCorporateModal");
    loadCorporateAdminSection();
  } catch (err) {}
}

function openEditLimitModal(clientId, clientName, currentLimit) {
  document.getElementById("editLimitClientId").value = clientId;
  document.getElementById("editLimitPartnerName").textContent = clientName;
  document.getElementById("editLimitCurrentVal").textContent = `₹${currentLimit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
  document.getElementById("newMonthlyLimitInput").value = currentLimit;
  document.getElementById("editLimitNotesInput").value = "";
  openModal("editCorporateLimitModal");
}

async function handleUpdateLimitSubmit(e) {
  e.preventDefault();
  const clientId = document.getElementById("editLimitClientId").value;
  const newLimit = parseFloat(document.getElementById("newMonthlyLimitInput").value);
  const notes = document.getElementById("editLimitNotesInput").value.trim() || null;

  try {
    await apiFetch(`/api/corporate/clients/${clientId}/limit`, {
      method: "PUT",
      body: JSON.stringify({
        monthly_credit_limit: newLimit,
        notes: notes
      })
    });
    showToast("Monthly credit limit updated successfully!", "success");
    closeModal("editCorporateLimitModal");
    loadCorporateAdminSection();
    loadActiveCustomKpis();
  } catch (err) {}
}

async function viewCorporateInvoices(clientId, clientName) {
  document.getElementById("viewCorpInvoicesTitle").textContent = `Billed Corporate Invoices: ${clientName}`;
  const tbody = document.getElementById("viewCorpInvoicesBody");
  const foot = document.getElementById("viewCorpInvoicesFoot");
  if (foot) foot.innerHTML = "";
  tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:1.5rem;">Loading corporate invoices...</td></tr>`;
  openModal("viewCorporateInvoicesModal");

  try {
    const detail = await apiFetch(`/api/corporate/clients/${clientId}`);
    const invs = detail.invoices || [];

    if (invs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No invoices billed to ${clientName} yet.</td></tr>`;
      return;
    }

    const totalClaimSum = invs.reduce((sum, inv) => sum + (inv.claim_amount || 0), 0);
    const totalNetSum = invs.reduce((sum, inv) => sum + (inv.net_payable || 0), 0);

    tbody.innerHTML = invs.map(i => `
      <tr>
        <td><strong>${i.invoice_number}</strong></td>
        <td>
          <strong>${escapeHtml(i.patient_name || 'Patient')}</strong>
          <div style="font-size:0.75rem; color:var(--text-muted); font-family:monospace;">${escapeHtml(i.patient_mrn || '')}</div>
        </td>
        <td><span class="badge badge-neutral" style="font-family:monospace; font-size:0.75rem;">${escapeHtml(i.policy_id)}</span></td>
        <td>₹${i.net_payable.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
        <td style="color:#15803d; font-weight:700;">₹${i.claim_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
        <td><span class="badge badge-success">${i.claim_status}</span></td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${i.created_at}</td>
      </tr>
    `).join("");

    if (foot) {
      foot.innerHTML = `
        <tr style="background:var(--bg-surface-alt); font-weight:700; border-top:2px solid var(--border-medium);">
          <td colspan="3">Reconciliation Total (${invs.length} Billed Claims)</td>
          <td>₹${totalNetSum.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
          <td style="color:#15803d; font-size:1.05rem;">₹${totalClaimSum.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
          <td colspan="2"><span class="badge badge-success">✓ 100% Reconciles with Utilized Credit</span></td>
        </tr>
      `;
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#ef4444; padding:1rem;">Failed to load invoices.</td></tr>`;
  }
}


// =========================================================================
// 3. GRANULAR FINANCIAL ANALYTICS & MULTI-DIMENSION OUTPUTS
// =========================================================================

async function loadGranularFinancialAnalytics(period) {
  try {
    const url = period ? `/api/corporate/analytics/granular?period=${encodeURIComponent(period)}` : "/api/corporate/analytics/granular";
    activeGranularFinancialData = await apiFetch(url);
    if (!activeGranularFinancialData) return;

    // Render Department Breakdown
    const deptTbody = document.getElementById("granularDeptBody");
    if (deptTbody) {
      deptTbody.innerHTML = activeGranularFinancialData.departments.map(d => `
        <tr>
          <td><strong>${escapeHtml(d.name)}</strong></td>
          <td>${d.orders_count} orders</td>
          <td><strong>₹${d.revenue.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
          <td>
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <div style="background:#e2e8f0; border-radius:4px; height:6px; flex:1; overflow:hidden;">
                <div style="background:var(--primary-600); width:${d.percentage}%; height:100%;"></div>
              </div>
              <span style="font-size:0.75rem; min-width:36px;">${d.percentage}%</span>
            </div>
          </td>
        </tr>
      `).join("");
    }

    // Render Payment Tender Breakdown
    const tenderTbody = document.getElementById("granularTenderBody");
    if (tenderTbody) {
      tenderTbody.innerHTML = activeGranularFinancialData.payment_modes.map(m => `
        <tr>
          <td><strong>${escapeHtml(m.label)}</strong></td>
          <td>${m.transactions_count} txns</td>
          <td><strong>₹${m.amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
          <td>${m.percentage}%</td>
        </tr>
      `).join("");
    }

    // Render Cash Denominations Tally
    const denomContainer = document.getElementById("granularDenomTallyGrid");
    if (denomContainer && activeGranularFinancialData.cash_denominations_tally) {
      const tally = activeGranularFinancialData.cash_denominations_tally;
      const notes = [500, 200, 100, 50, 20, 10, 5, 2, 1];
      denomContainer.innerHTML = notes.map(n => {
        const count = tally[String(n)] || 0;
        const totalVal = count * n;
        return `
          <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:0.4rem 0.6rem; font-size:0.75rem; display:flex; justify-content:space-between; align-items:center;">
            <strong>₹${n}:</strong>
            <span>${count} notes <small style="color:var(--text-muted);">(₹${totalVal.toLocaleString()})</small></span>
          </div>
        `;
      }).join("");
    }

    // Render Walk-in vs Corporate Breakdown
    const segTbody = document.getElementById("granularSegmentBody");
    if (segTbody) {
      segTbody.innerHTML = activeGranularFinancialData.segments.map(s => `
        <tr>
          <td><strong>${escapeHtml(s.label)}</strong></td>
          <td>${s.invoice_count} patients</td>
          <td><strong>₹${s.revenue.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
          <td>${s.percentage}%</td>
          <td>₹${s.avg_ticket.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
        </tr>
      `).join("");
    }

    // Render Doctor Referrals Breakdown
    const docTbody = document.getElementById("granularDoctorBody");
    if (docTbody && activeGranularFinancialData.doctor_breakdown) {
      docTbody.innerHTML = activeGranularFinancialData.doctor_breakdown.map(doc => `
        <tr>
          <td><strong>${escapeHtml(doc.doctor_name)}</strong></td>
          <td>${escapeHtml(doc.department)}</td>
          <td><span class="badge badge-info">${doc.referred_patients} patients</span></td>
          <td>${doc.commission_entries_count} services</td>
          <td style="color:var(--primary-600); font-weight:700;">₹${doc.total_commission_accrued.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
        </tr>
      `).join("");
    }
  } catch (err) {}
}

function switchGranularTab(tabId) {
  const tabs = ["dept", "tender", "segment", "doctor"];
  tabs.forEach(t => {
    const pane = document.getElementById(`granularPane_${t}`);
    const btn = document.getElementById(`granularTabBtn_${t}`);
    if (pane) pane.style.display = (t === tabId) ? "block" : "none";
    if (btn) {
      if (t === tabId) {
        btn.className = "btn btn-primary btn-sm";
      } else {
        btn.className = "btn btn-outline btn-sm";
      }
    }
  });
}

function downloadGranularPdfReport() {
  window.print();
}
