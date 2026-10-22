/**
 * Cashier Desk & Billing Module
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

let activeInvoice = null;
let activePaymentIdempotencyKey = null;
let activePaymentIdempotencyStorageKey = null;

let allCorporateClients = [];

document.addEventListener("DOMContentLoaded", () => {
  loadInvoices();
  loadCashierAnalytics();
  loadCorporateClientsList();

  const filterSelect = document.getElementById("invoiceFilterSelect");
  if (filterSelect) {
    filterSelect.addEventListener("change", (e) => {
      const q = document.getElementById("billingSearchInput")?.value || "";
      loadInvoices(e.target.value, q);
    });
  }

  const searchInput = document.getElementById("billingSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const status = document.getElementById("invoiceFilterSelect")?.value || "";
      loadInvoices(status, e.target.value);
    });
  }

  const payForm = document.getElementById("paymentForm");
  if (payForm) {
    payForm.addEventListener("submit", handleCollectPayment);
  }
});

async function loadCorporateClientsList() {
  try {
    const clients = await apiFetch("/api/corporate/clients?active_only=true");
    allCorporateClients = clients || [];
    const select = document.getElementById("corporateClientSelect");
    if (!select) return;
    select.innerHTML = '<option value="">-- Choose Corporate / Insurance Partner --</option>' +
      allCorporateClients.map(c => `
        <option value="${c.id}" data-limit="${c.monthly_credit_limit}" data-available="${c.available_credit}">
          ${escapeHtml(c.name)} (${c.category.replace('_', ' ')}) — Avail Credit: ₹${c.available_credit.toLocaleString('en-IN', {minimumFractionDigits: 0})}
        </option>
      `).join("");
  } catch (err) {}
}

function handleBillingSegmentChange(segment) {
  const isCorp = (segment === "CORPORATE_TIEUP");
  const corpFields = document.getElementById("corporateTieupFields");
  const badge = document.getElementById("billingSegmentBadge");
  const btnWalkin = document.getElementById("btnSegmentWalkin");
  const btnCorp = document.getElementById("btnSegmentCorporate");

  if (corpFields) corpFields.style.display = isCorp ? "block" : "none";
  if (badge) {
    badge.textContent = isCorp ? "Corporate / Tie-up" : "Walk-in Private";
    badge.className = isCorp ? "badge badge-primary" : "badge badge-info";
  }

  if (btnWalkin && btnCorp) {
    if (isCorp) {
      btnCorp.style.border = "2px solid var(--primary-600)";
      btnCorp.style.background = "rgba(37, 99, 235, 0.05)";
      btnWalkin.style.border = "1px solid #cbd5e1";
      btnWalkin.style.background = "#ffffff";
      
      const methodSelect = document.getElementById("paymentMethodSelect");
      if (methodSelect) {
        methodSelect.value = "INSURANCE";
        handlePaymentMethodChange();
      }
    } else {
      btnWalkin.style.border = "2px solid var(--primary-600)";
      btnWalkin.style.background = "rgba(37, 99, 235, 0.05)";
      btnCorp.style.border = "1px solid #cbd5e1";
      btnCorp.style.background = "#ffffff";
    }
  }
}

function handleCorporatePartnerSelect() {
  const select = document.getElementById("corporateClientSelect");
  const infoBox = document.getElementById("corporateCreditInfoBox");
  if (!select || !infoBox) return;

  const clientId = parseInt(select.value, 10);
  const client = allCorporateClients.find(c => c.id === clientId);

  if (client) {
    infoBox.style.display = "flex";
    document.getElementById("corporateCreditPartnerName").textContent = client.name;
    document.getElementById("corporateCreditAvailableBadge").textContent = `₹${client.available_credit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
    document.getElementById("corporateCreditTotalLimit").textContent = `/ Limit: ₹${client.monthly_credit_limit.toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
  } else {
    infoBox.style.display = "none";
  }
}

async function loadInvoices(status = "", searchTerm = "") {
  const tbody = document.getElementById("invoiceTableBody");
  if (!tbody) return;

  try {
    const url = status ? `/api/billing/invoices?status=${encodeURIComponent(status)}` : "/api/billing/invoices";
    let invoices = await apiFetch(url);

    if (searchTerm) {
      const term = searchTerm.toLowerCase().trim();
      invoices = (invoices || []).filter(inv => 
        (inv.patient_name || "").toLowerCase().includes(term) ||
        (inv.patient_mrn || "").toLowerCase().includes(term) ||
        (inv.invoice_number || "").toLowerCase().includes(term)
      );
    }

    if (!invoices || invoices.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:2rem;">No invoices found matching filter.</td></tr>`;
      return;
    }

    tbody.innerHTML = invoices.map(inv => `
      <tr>
        <td><strong>${inv.invoice_number}</strong></td>
        <td>${inv.patient_name}<br><small style="color:var(--text-muted);">MRN: ${inv.patient_mrn}</small></td>
        <td><strong style="color:var(--primary-600);">${inv.attending_doctor_name || 'Consulting Physician'}</strong></td>
        <td>₹${inv.net_payable.toFixed(2)}</td>
        <td>₹${inv.paid_amount.toFixed(2)}</td>
        <td>
          <span class="badge ${inv.payment_status === 'PAID' ? 'badge-success' : inv.payment_status === 'PARTIAL' ? 'badge-warning' : 'badge-danger'}">
            ${inv.payment_status}
          </span>
        </td>
        <td>
          <span class="badge badge-neutral">${inv.payment_method || '-'}</span>
          ${inv.upi_id ? `<div style="font-size:0.7rem; color:var(--text-muted);">UTR: ${inv.upi_id}</div>` : ''}
          ${inv.cheque_number ? `<div style="font-size:0.7rem; color:var(--text-muted);">Chq #${inv.cheque_number}</div>` : ''}
        </td>
        <td>
          <button class="btn btn-primary btn-sm" onclick="viewInvoiceDetail(${inv.id})">
            ${inv.payment_status === 'PAID' ? 'View / Print' : 'Collect Payment'}
          </button>
        </td>
      </tr>
    `).join("");
  } catch (err) {}
}

async function viewInvoiceDetail(invoiceId) {
  try {
    activeInvoice = await apiFetch(`/api/billing/invoices/${invoiceId}`);
    
    document.getElementById("modalInvNumber").innerText = activeInvoice.invoice_number;
    document.getElementById("modalPatientInfo").innerText = `${activeInvoice.patient.name} (${activeInvoice.patient.mrn}) - ${activeInvoice.patient.age_gender}`;
    document.getElementById("modalDoctorInfo").innerText = activeInvoice.attending_doctor_name || 'Consulting Physician';
    document.getElementById("modalTotalAmount").innerText = `₹${activeInvoice.net_payable.toFixed(2)}`;
    
    const balance = Math.max(0, activeInvoice.net_payable - activeInvoice.paid_amount);
    document.getElementById("amountToPayInput").value = balance.toFixed(2);
    
    // Line items
    const tbody = document.getElementById("modalInvoiceItemsBody");
    tbody.innerHTML = activeInvoice.items.map(item => `
      <tr>
        <td><span class="badge badge-neutral">${item.type}</span></td>
        <td>${item.description}</td>
        <td>${item.quantity}</td>
        <td>₹${item.unit_price.toFixed(2)}</td>
        <td>₹${item.total_price.toFixed(2)}</td>
      </tr>
    `).join("");

    // Reset denominations & split inputs
    resetPaymentFields();
    handlePaymentMethodChange();

    // Toggle Payment fields if already paid
    if (activeInvoice.payment_status === "PAID") {
      document.getElementById("paymentInputsArea").style.display = "none";
      document.getElementById("btnCollect").style.display = "none";
      document.getElementById("btnPrintReceipt").style.display = "inline-flex";
    } else {
      document.getElementById("paymentInputsArea").style.display = "block";
      document.getElementById("btnCollect").style.display = "inline-flex";
      document.getElementById("btnPrintReceipt").style.display = "none";
    }

    openModal("invoiceDetailModal");
  } catch (err) {}
}

function resetPaymentFields() {
  const denoms = ["500", "200", "100", "50", "20", "10", "5", "2", "1"];
  denoms.forEach(d => {
    const el = document.getElementById(`denom_${d}`);
    if (el) el.value = "";
  });
  const upiEl = document.getElementById("upiTxnIdInput");
  if (upiEl) upiEl.value = "";
  const chqEl = document.getElementById("chequeNumberInput");
  if (chqEl) chqEl.value = "";
  const bnkEl = document.getElementById("bankNameInput");
  if (bnkEl) bnkEl.value = "";
  const insPrv = document.getElementById("insProviderInput");
  if (insPrv) insPrv.value = "";
  const insPol = document.getElementById("insPolicyInput");
  if (insPol) insPol.value = "";
  const refEl = document.getElementById("transactionRefInput");
  if (refEl) refEl.value = "";
  
  // Reset segment to WALK_IN by default
  const radioWalkin = document.getElementById("radioSegmentWalkin");
  if (radioWalkin) {
    radioWalkin.checked = true;
    handleBillingSegmentChange("WALK_IN");
  }
  const corpSelect = document.getElementById("corporateClientSelect");
  if (corpSelect) corpSelect.value = "";
  const corpPolicy = document.getElementById("corporatePolicyIdInput");
  if (corpPolicy) corpPolicy.value = "";
  const corpInfo = document.getElementById("corporateCreditInfoBox");
  if (corpInfo) corpInfo.style.display = "none";

  window._splitRows = [];
  recalculateCashDenominations();
}

function handlePaymentMethodChange() {
  const method = document.getElementById("paymentMethodSelect")?.value || "CASH";
  const cashPanel = document.getElementById("cashDenomPanel");
  const upiPanel = document.getElementById("upiPanel");
  const chequePanel = document.getElementById("chequePanel");
  const insPanel = document.getElementById("insurancePanel");
  const splitPanel = document.getElementById("splitPanel");
  const genRef = document.getElementById("genericRefPanel");

  if (cashPanel) cashPanel.style.display = (method === "CASH") ? "block" : "none";
  if (upiPanel) upiPanel.style.display = (method === "UPI") ? "block" : "none";
  if (chequePanel) chequePanel.style.display = (method === "CHEQUE") ? "block" : "none";
  if (insPanel) insPanel.style.display = (method === "INSURANCE") ? "block" : "none";
  if (splitPanel) splitPanel.style.display = (method === "SPLIT") ? "block" : "none";
  if (genRef) genRef.style.display = (method === "CARD") ? "block" : "none";

  if (method === "CASH") {
    recalculateCashDenominations();
  } else if (method === "SPLIT") {
    if (window._splitRows.length === 0) {
      const payable = parseFloat(document.getElementById("amountToPayInput")?.value) || 0;
      // Default initial split: 30% UPI + 70% Cash as requested by user example!
      const upiSlice = Math.round(payable * 0.3);
      const cashSlice = payable - upiSlice;
      addSplitRow("UPI", upiSlice);
      addSplitRow("CASH", cashSlice);
    }
    recalculateSplitAllocations();
  }
}

function recalculateCashDenominations() {
  const denoms = [
    { key: "500", val: 500 },
    { key: "200", val: 200 },
    { key: "100", val: 100 },
    { key: "50", val: 50 },
    { key: "20", val: 20 },
    { key: "10", val: 10 },
    { key: "5", val: 5 },
    { key: "2", val: 2 },
    { key: "1", val: 1 },
  ];

  let totalTendered = 0;
  denoms.forEach(d => {
    const count = parseInt(document.getElementById(`denom_${d.key}`)?.value || "0", 10);
    if (!isNaN(count) && count > 0) {
      totalTendered += count * d.val;
    }
  });

  const amountToPay = parseFloat(document.getElementById("amountToPayInput")?.value || "0") || 0;
  const change = Math.max(0, totalTendered - amountToPay);
  const shortage = Math.max(0, amountToPay - totalTendered);

  const tenderedEl = document.getElementById("denomTotalTendered");
  if (tenderedEl) tenderedEl.innerText = `₹${totalTendered.toFixed(2)}`;
  const changeEl = document.getElementById("denomChangeToReturn");
  if (changeEl) changeEl.innerText = `₹${change.toFixed(2)}`;

  const badge = document.getElementById("denomTallyBadge");
  if (badge) {
    if (totalTendered === 0) {
      badge.className = "badge badge-neutral";
      badge.innerText = "Enter Note Counts";
    } else if (totalTendered >= amountToPay) {
      badge.className = "badge badge-success";
      badge.innerText = change > 0 ? `✓ Tally OK (Return ₹${change.toFixed(2)})` : "✓ Exact Cash Tendered";
    } else {
      badge.className = "badge badge-warning";
      badge.innerText = `Need ₹${shortage.toFixed(2)} more`;
    }
  }

  return { totalTendered, change, shortage };
}

window._splitRows = [];

function addSplitRow(defaultMethod = "UPI", defaultAmount = 0) {
  window._splitRows.push({
    id: Date.now() + Math.random(),
    method: defaultMethod,
    amount: defaultAmount,
    reference: ""
  });
  renderSplitRows();
}

function removeSplitRow(index) {
  window._splitRows.splice(index, 1);
  renderSplitRows();
}

function renderSplitRows() {
  const container = document.getElementById("splitRowsContainer");
  if (!container) return;

  container.innerHTML = window._splitRows.map((row, idx) => `
    <div style="display:grid; grid-template-columns:140px 120px 1fr 36px; gap:0.5rem; align-items:center; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:0.4rem 0.6rem;">
      <select class="form-select" style="height:32px; font-size:0.8rem; padding:2px 8px;" onchange="updateSplitRowMethod(${idx}, this.value)">
        <option value="UPI" ${row.method === 'UPI' ? 'selected' : ''}>UPI (16-Digit)</option>
        <option value="CASH" ${row.method === 'CASH' ? 'selected' : ''}>Cash</option>
        <option value="CHEQUE" ${row.method === 'CHEQUE' ? 'selected' : ''}>Cheque</option>
        <option value="INSURANCE" ${row.method === 'INSURANCE' ? 'selected' : ''}>Insurance</option>
        <option value="CARD" ${row.method === 'CARD' ? 'selected' : ''}>Card</option>
      </select>
      <div style="position:relative;">
        <span style="position:absolute; left:6px; top:6px; font-size:0.75rem; color:#64748b;">₹</span>
        <input type="number" min="0" step="0.5" class="form-control" style="height:32px; font-size:0.8rem; padding:2px 6px 2px 18px;" value="${row.amount}" oninput="updateSplitRowAmount(${idx}, this.value)">
      </div>
      <input type="text" class="form-control" style="height:32px; font-size:0.75rem; padding:2px 8px;" placeholder="${row.method === 'UPI' ? '16-digit UTR ID' : row.method === 'CHEQUE' ? 'Cheque # & Bank' : row.method === 'INSURANCE' ? 'TPA / Policy #' : 'Txn / Note'}" value="${row.reference || ''}" oninput="updateSplitRowRef(${idx}, this.value)">
      <button type="button" class="btn btn-outline btn-sm" style="height:32px; width:32px; padding:0; display:flex; align-items:center; justify-content:center; color:#ef4444;" onclick="removeSplitRow(${idx})">&times;</button>
    </div>
  `).join("");

  recalculateSplitAllocations();
}

function updateSplitRowMethod(idx, method) {
  if (window._splitRows[idx]) {
    window._splitRows[idx].method = method;
    renderSplitRows();
  }
}

function updateSplitRowAmount(idx, amount) {
  if (window._splitRows[idx]) {
    window._splitRows[idx].amount = parseFloat(amount) || 0;
    recalculateSplitAllocations();
  }
}

function updateSplitRowRef(idx, ref) {
  if (window._splitRows[idx]) {
    window._splitRows[idx].reference = ref;
  }
}

function recalculateSplitAllocations() {
  const totalPayable = parseFloat(document.getElementById("amountToPayInput")?.value || "0") || 0;
  let allocated = 0;
  window._splitRows.forEach(r => { allocated += (r.amount || 0); });
  const remaining = totalPayable - allocated;

  const allocEl = document.getElementById("splitAllocatedTotal");
  if (allocEl) allocEl.innerText = `₹${allocated.toFixed(2)}`;
  const remEl = document.getElementById("splitRemainingBalance");
  if (remEl) {
    remEl.innerText = `₹${remaining.toFixed(2)}`;
    remEl.style.color = (Math.abs(remaining) < 0.01) ? "#059669" : "#ef4444";
  }
}

async function handleCollectPayment(e) {
  e.preventDefault();
  if (!activeInvoice) return;

  const amount = parseFloat(document.getElementById("amountToPayInput").value);
  const method = document.getElementById("paymentMethodSelect").value;
  let ref = null;
  let bankName = null;
  let chequeNumber = null;
  let upiId = null;
  let insProvider = null;
  let insPolicy = null;
  let cashDenoms = null;
  let splitRowsPayload = null;

  // Granular validation for each payment mode
  if (method === "CASH") {
    const tally = recalculateCashDenominations();
    if (tally.totalTendered < amount) {
      showToast(`Cash shortage! Received ₹${tally.totalTendered.toFixed(2)} of ₹${amount.toFixed(2)}. Need ₹${tally.shortage.toFixed(2)} more.`, "warning");
      return;
    }
    cashDenoms = {
      "500": parseInt(document.getElementById("denom_500")?.value || "0", 10),
      "200": parseInt(document.getElementById("denom_200")?.value || "0", 10),
      "100": parseInt(document.getElementById("denom_100")?.value || "0", 10),
      "50": parseInt(document.getElementById("denom_50")?.value || "0", 10),
      "20": parseInt(document.getElementById("denom_20")?.value || "0", 10),
      "10": parseInt(document.getElementById("denom_10")?.value || "0", 10),
      "5": parseInt(document.getElementById("denom_5")?.value || "0", 10),
      "2": parseInt(document.getElementById("denom_2")?.value || "0", 10),
      "1": parseInt(document.getElementById("denom_1")?.value || "0", 10),
      "tendered": tally.totalTendered,
      "change": tally.change
    };
    ref = `CASH-TENDERED-₹${tally.totalTendered}-CHANGE-₹${tally.change}`;
  } else if (method === "UPI") {
    upiId = (document.getElementById("upiTxnIdInput")?.value || "").trim();
    if (!upiId) {
      showToast("Please enter the 16-digit UPI Transaction ID / UTR", "warning");
      document.getElementById("upiTxnIdInput")?.focus();
      return;
    }
    if (upiId.length < 10) {
      showToast("UPI Transaction ID must be at least 12-16 digits", "warning");
      return;
    }
    ref = `UPI-UTR-${upiId}`;
  } else if (method === "CHEQUE") {
    chequeNumber = (document.getElementById("chequeNumberInput")?.value || "").trim();
    bankName = (document.getElementById("bankNameInput")?.value || "").trim();
    if (!chequeNumber || !bankName) {
      showToast("Please enter both Cheque Number and Issuing Bank Name", "warning");
      return;
    }
    ref = `CHQ-${chequeNumber}-${bankName}`;
  } else if (method === "INSURANCE") {
    const isCorporate = document.getElementById("radioSegmentCorporate")?.checked;
    if (isCorporate) {
      const corpSelect = document.getElementById("corporateClientSelect");
      const corpId = corpSelect ? parseInt(corpSelect.value, 10) : null;
      const corpPolicy = (document.getElementById("corporatePolicyIdInput")?.value || "").trim();
      if (!corpId) {
        showToast("Please select a Corporate / Insurance Partner from dropdown", "warning");
        return;
      }
      if (!corpPolicy) {
        showToast("Please enter Policy # / TPA Card ID or Employee ID", "warning");
        return;
      }
      const client = allCorporateClients.find(c => c.id === corpId);
      insProvider = client ? client.name : "Corporate Partner";
      insPolicy = corpPolicy;
      ref = `CORP-${client ? client.code : 'TIEUP'}-${corpPolicy}`;
    } else {
      insProvider = (document.getElementById("insProviderInput")?.value || "").trim();
      insPolicy = (document.getElementById("insPolicyInput")?.value || "").trim();
      if (!insProvider || !insPolicy) {
        showToast("Please enter Insurance / TPA Partner and Policy ID", "warning");
        return;
      }
      ref = `INS-${insProvider}-${insPolicy}`;
    }
  } else if (method === "SPLIT") {
    let totalAlloc = 0;
    window._splitRows.forEach(r => { totalAlloc += (r.amount || 0); });
    if (Math.abs(totalAlloc - amount) > 0.05) {
      showToast(`Split allocation total (₹${totalAlloc.toFixed(2)}) must exactly match amount to collect (₹${amount.toFixed(2)})`, "warning");
      return;
    }
    splitRowsPayload = window._splitRows;
    ref = `SPLIT-${splitRowsPayload.map(s => `${s.method}:₹${s.amount}`).join(";")}`;
  } else {
    ref = document.getElementById("transactionRefInput")?.value || "CARD-PAYMENT";
  }

  const isCorporate = document.getElementById("radioSegmentCorporate")?.checked;
  const corpSelect = document.getElementById("corporateClientSelect");
  const corpId = (isCorporate && corpSelect && corpSelect.value) ? parseInt(corpSelect.value, 10) : null;
  const corpPolicy = isCorporate ? (document.getElementById("corporatePolicyIdInput")?.value || "").trim() : null;

  if (isCorporate && !corpId) {
    showToast("Please select a Corporate / Insurance Partner", "warning");
    return;
  }
  if (isCorporate && !corpPolicy) {
    showToast("Please enter Policy # / TPA Card ID or Employee ID", "warning");
    return;
  }

  if (!activePaymentIdempotencyKey) {
    activePaymentIdempotencyStorageKey = `hms_payment_key_${activeInvoice.id}_${activeInvoice.paid_amount}_${amount}_${method}`;
    try { activePaymentIdempotencyKey = sessionStorage.getItem(activePaymentIdempotencyStorageKey); } catch (err) {}
    if (!activePaymentIdempotencyKey) {
      activePaymentIdempotencyKey = `payment-${crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
      try { sessionStorage.setItem(activePaymentIdempotencyStorageKey, activePaymentIdempotencyKey); } catch (err) {}
    }
  }

  const submitButton = document.getElementById("btnCollect");
  submitButton.disabled = true;

  try {
    const payload = {
      invoice_id: activeInvoice.id,
      amount_paid: amount,
      payment_method: method,
      transaction_ref: ref,
      idempotency_key: activePaymentIdempotencyKey,
      bank_name: bankName,
      cheque_number: chequeNumber,
      upi_id: upiId,
      insurance_provider: insProvider,
      insurance_policy_number: insPolicy,
      cash_denominations: cashDenoms,
      split_payments: splitRowsPayload,
      attending_doctor_id: activeInvoice.attending_doctor_id,
      billing_type: isCorporate ? "CORPORATE_TIEUP" : "WALK_IN",
      corporate_client_id: corpId,
      corporate_policy_id: corpPolicy,
      corporate_claim_amount: isCorporate ? amount : 0
    };

    const res = await apiFetch("/api/billing/collect", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast(`Payment of ₹${amount.toFixed(2)} recorded! Invoice marked ${res.payment_status}. Doctor commission unlocked!`, "success");
    closeModal("invoiceDetailModal");
    loadInvoices();
    loadCashierAnalytics();
    try { sessionStorage.removeItem(activePaymentIdempotencyStorageKey); } catch (err) {}
    activePaymentIdempotencyKey = null;
    activePaymentIdempotencyStorageKey = null;

    // Open printable receipt with doctor name
    window.open(`/receipt/${activeInvoice.id}`, "_blank");
  } catch (err) {
    // Keep idempotency key for safe retry
  } finally {
    submitButton.disabled = false;
  }
}


function printCurrentReceipt() {
  if (activeInvoice) {
    window.open(`/receipt/${activeInvoice.id}`, "_blank");
  }
}

let cashierAlertsData = [];

async function loadCashierAnalytics() {
  try {
    const data = await apiFetch("/api/billing/cashier-analytics");
    if (!data) return;

    // Update 4 KPIs
    const kpiCollected = document.getElementById("kpiCashierCollected");
    const kpiReceivable = document.getElementById("kpiCashierReceivable");
    const kpiPaid = document.getElementById("kpiCashierPaidCount");
    const kpiUnpaid = document.getElementById("kpiCashierUnpaidCount");
    const kpiUnpaidSub = document.getElementById("kpiCashierUnpaidSub");

    if (kpiCollected) kpiCollected.textContent = `₹${(data.kpis.total_collected ?? 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    if (kpiReceivable) kpiReceivable.textContent = `₹${(data.kpis.total_receivable_unpaid ?? 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    if (kpiPaid) kpiPaid.textContent = data.kpis.paid_invoices_count ?? 0;
    if (kpiUnpaid) kpiUnpaid.textContent = data.kpis.unpaid_invoices_count ?? 0;
    if (kpiUnpaidSub) {
      kpiUnpaidSub.textContent = `${data.kpis.total_invoices ?? 0} total invoices in system`;
    }

    // Render alerts
    cashierAlertsData = data.alerts || [];
    renderCashierAlerts(cashierAlertsData);
  } catch (err) {
    console.error("Failed to load cashier analytics:", err);
  }
}

function renderCashierAlerts(alerts) {
  const container = document.getElementById("cashierAlertsContainer");
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
      <div style="display:flex; justify-content:space-between; align-items:center; padding:0.75rem 1rem; border-bottom:1px solid #fed7aa; cursor:pointer;" onclick="toggleCashierAlerts()">
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <svg class="icon" style="color:#c2410c;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <strong style="color:#9a3412;">Cashier Settlement & Pharmacy Lock Alerts (${count} Action${count > 1 ? 's' : ''})</strong>
          <span style="font-size:var(--font-xs); color:#7c2d12; background:#ffedd5; padding:0.15rem 0.5rem; border-radius:999px; border:1px solid #fdba74;">Dispensing Blocked</span>
        </div>
        <div style="display:flex; align-items:center; gap:0.5rem;">
          <button type="button" class="btn btn-outline btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem; border-color:#fdba74; color:#9a3412;" id="toggleCashierAlertsBtn">
            Hide Alerts &#9652;
          </button>
        </div>
      </div>
      <div id="cashierAlertsBody" style="padding:0.75rem 1rem;">
        <div style="margin-bottom:0.6rem;">
          <input type="text" id="cashierAlertSearch" class="form-control" placeholder="Filter alerts by patient, invoice number, or alert type..." style="font-size:0.8rem; padding:0.35rem 0.6rem; height:auto; background:#fff; border-color:#fed7aa;" oninput="filterCashierAlerts(this.value)">
        </div>
        <div id="cashierAlertsList" style="max-height:260px; overflow-y:auto; display:flex; flex-direction:column; gap:0.5rem; padding-right:0.25rem;">
          ${buildCashierAlertItemsHTML(alerts)}
        </div>
      </div>
    </div>
  `;
}

function buildCashierAlertItemsHTML(alerts) {
  if (alerts.length === 0) {
    return `<div style="font-size:0.8rem; color:#78716c; text-align:center; padding:0.5rem;">No alerts match filter.</div>`;
  }
  return alerts.map(a => `
    <div style="display:flex; justify-content:space-between; align-items:center; background:#ffffff; border:1px solid ${a.severity === 'danger' ? '#fecaca' : '#fed7aa'}; border-radius:var(--radius-md); padding:0.5rem 0.75rem;">
      <div style="display:flex; align-items:center; gap:0.5rem;">
        <span class="badge ${a.severity === 'danger' ? 'badge-danger' : 'badge-warning'}" style="font-size:0.7rem;">${a.type}</span>
        <span style="font-size:0.825rem; color:var(--text-main);">${a.message}</span>
      </div>
      <button class="btn btn-primary btn-sm" style="font-size:0.75rem; padding:0.2rem 0.6rem; white-space:nowrap; margin-left:0.5rem;" onclick="viewInvoiceDetail(${a.invoice_id})">
        ${a.action}
      </button>
    </div>
  `).join("");
}

function filterCashierAlerts(query) {
  const q = (query || "").toLowerCase().trim();
  const filtered = cashierAlertsData.filter(a => 
    (a.message || "").toLowerCase().includes(q) ||
    (a.type || "").toLowerCase().includes(q)
  );
  const list = document.getElementById("cashierAlertsList");
  if (list) list.innerHTML = buildCashierAlertItemsHTML(filtered);
}

function toggleCashierAlerts() {
  const body = document.getElementById("cashierAlertsBody");
  const btn = document.getElementById("toggleCashierAlertsBtn");
  if (!body) return;
  if (body.style.display === "none") {
    body.style.display = "block";
    if (btn) btn.innerHTML = "Hide Alerts &#9652;";
  } else {
    body.style.display = "none";
    if (btn) btn.innerHTML = "Show Alerts &#9662;";
  }
}

