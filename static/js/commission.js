(() => {
  const $ = id => document.getElementById(id);
  const currentPeriod = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = value => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(Number(value || 0));
  const humanize = value => String(value ?? "").toLowerCase().split(/[_\s]+/).filter(Boolean).map(word => word[0].toUpperCase() + word.slice(1)).join(" ");
  const settlementLabel = value => ({ PENDING: "In review", APPROVED: "Approved", PAID: "Paid", REJECTED: "Declined" }[value] || humanize(value));
  const key = prefix => `${prefix}-${crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;
  const persistedKey = (scope, signature) => {
    const storageKey = `hms_finance_key_${scope}_${signature}`;
    let value;
    try { value = sessionStorage.getItem(storageKey); } catch (err) {}
    if (!value) {
      value = key(scope);
      try { sessionStorage.setItem(storageKey, value); } catch (err) {}
    }
    return { value, clear: () => { try { sessionStorage.removeItem(storageKey); } catch (err) {} } };
  };
  let doctorPage = 1;
  let doctorTotal = 0;
  let searchTimer;
  let doctorLoadToken = 0;
  let transactionLoadToken = 0;
  let settlementLoadToken = 0;
  let doctorChart;
  let doctorServiceChart;
  let financeDoctorChart;
  let financeServiceChart;
  let financeCompareChart;
  let financeStatusChart;
  let financeCollectionsChart;
  let financeBalancesChart;
  let financeDepartmentChart;
  let financeReversalsChart;
  let financeLiabilityChart;
  let financeLoadToken = 0;
  let doctorAvailableAmount = 0;
  let doctorBalanceLoaded = false;
  let settlementSubmitting = false;

  function drawChart(canvas, previous, labels, values, type = "bar") {
    if (!canvas) return null;
    const chartCard = canvas.closest(".chart-card");
    let emptyState = chartCard && chartCard.querySelector(".chart-empty");
    const hasActivity = labels.length > 0 && values.some(value => Number.isFinite(Number(value)) && Number(value) !== 0);
    if (!hasActivity) {
      if (previous) previous.destroy();
      canvas.style.display = "none";
      if (chartCard && !emptyState) {
        emptyState = document.createElement("div");
        emptyState.className = "chart-empty";
        emptyState.setAttribute("role", "status");
        emptyState.style.padding = "2.5rem 1rem";
        emptyState.style.textAlign = "center";
        emptyState.style.color = "var(--text-muted)";
        emptyState.style.fontSize = "var(--font-sm)";
        emptyState.textContent = "No chart activity recorded for this period.";
        canvas.insertAdjacentElement("afterend", emptyState);
      }
      return null;
    }
    if (typeof Chart === "undefined") return null;
    canvas.style.display = "block";
    if (emptyState) emptyState.remove();
    if (previous) previous.destroy();

    const palette = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"];
    const isDoughnut = type === "doughnut";
    const bgColors = isDoughnut ? palette : labels.map((_, i) => palette[i % palette.length]);

    return new Chart(canvas.getContext("2d"), {
      type,
      data: {
        labels,
        datasets: [{
          label: "Amount (₹)",
          data: values,
          backgroundColor: bgColors,
          hoverBackgroundColor: bgColors,
          borderColor: isDoughnut ? "#ffffff" : bgColors,
          borderWidth: isDoughnut ? 2 : 1,
          borderRadius: isDoughnut ? 0 : 6,
          maxBarThickness: 42
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 14, bottom: 6, left: 4, right: 8 } },
        animation: { duration: 300 },
        plugins: {
          legend: {
            display: isDoughnut,
            position: "bottom",
            labels: { usePointStyle: true, boxWidth: 7, padding: 14, font: { size: 11, family: "inherit" } }
          },
          tooltip: {
            backgroundColor: "#0f172a",
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              label: (ctx) => ` ${fmt(ctx.raw)}`
            }
          }
        },
        cutout: isDoughnut ? "70%" : undefined,
        scales: isDoughnut ? {} : {
          y: {
            beginAtZero: true,
            grace: "20%",
            grid: { color: "rgba(0, 0, 0, 0.05)" },
            ticks: {
              font: { size: 10 },
              callback: (val) => "₹" + Number(val).toLocaleString("en-IN")
            }
          },
          x: {
            grid: { display: false },
            ticks: { font: { size: 11, weight: "500" } }
          }
        }
      }
    });
  }

  async function loadDoctorCommission(manual = false) {
    if (!$('doctorCommissionPanel')) return;
    const loadToken = ++doctorLoadToken;
    const previewNotice = $('doctorCommissionPreviewNotice');
    if (previewNotice) { previewNotice.hidden = true; previewNotice.textContent = ""; }
    doctorBalanceLoaded = false;

    const reqForm = $('commissionRequestForm');
    const requestButton = reqForm ? reqForm.querySelector('[type="submit"]') : null;
    if (reqForm) {
      reqForm.querySelectorAll("input").forEach(control => { control.disabled = false; });
      if (requestButton) { requestButton.disabled = true; requestButton.textContent = "Loading available amount…"; }
    }

    const periodInput = $('commissionPeriod');
    if (periodInput && !periodInput.value) periodInput.value = currentPeriod();
    const period = periodInput ? periodInput.value : currentPeriod();

    try {
      const data = await apiFetch(`/api/commissions/dashboard?period=${encodeURIComponent(period)}`);
      if (!data || loadToken !== doctorLoadToken) return;
      doctorAvailableAmount = Number(data.available || 0);
      doctorBalanceLoaded = true;

      if ($('heroAvailableAmount')) $('heroAvailableAmount').textContent = fmt(data.available);
      if ($('heroStatusChip')) {
        const isReady = Number(data.available) > 0;
        $('heroStatusChip').textContent = isReady ? "[🔓 Ready to Pull]" : (data.chip_label || "[🔒 Waiting for Patient Bill Settlement]");
        $('heroStatusChip').className = `badge ${isReady ? "badge-success" : "badge-warning"}`;
        $('heroStatusChip').title = isReady ? "Funds are released and available for instant payout" : (data.chip_explanation || "Locked until patient bills are settled");
      }
      if ($('commissionEarned')) $('commissionEarned').textContent = fmt(data.net_earned);
      if ($('commissionPending')) $('commissionPending').textContent = fmt(data.accrued_locked || data.pending_eligibility_estimate || 0);
      if ($('commissionAvailable')) $('commissionAvailable').textContent = fmt(data.available);
      if ($('commissionReserved')) $('commissionReserved').textContent = fmt(data.reserved);
      if ($('commissionApproved')) $('commissionApproved').textContent = fmt(data.approved_unpaid);
      if ($('commissionPaid')) $('commissionPaid').textContent = fmt(data.paid_in_period);
      if ($('commissionPrevious')) $('commissionPrevious').textContent = fmt(data.previous_net_earned);
      if ($('commissionPreviousLabel')) $('commissionPreviousLabel').textContent = `Net earned in ${data.previous_period}`;
      if ($('commissionReversed')) $('commissionReversed').textContent = fmt(data.reversed);

      if ($('commissionRequestAmount')) {
        $('commissionRequestAmount').max = doctorAvailableAmount;
        $('commissionRequestAmount').placeholder = doctorAvailableAmount > 0 ? `Up to ${fmt(doctorAvailableAmount)}` : "No amount available yet";
      }
      if (requestButton) {
        requestButton.disabled = doctorAvailableAmount <= 0;
        requestButton.textContent = doctorAvailableAmount > 0 ? "Request my payment" : "No amount available";
      }

      const chartData = data.monthly_trend || [];
      if ($('doctorCommissionChart')) {
        doctorChart = drawChart($('doctorCommissionChart'), doctorChart, chartData.map(x => x.period), chartData.map(x => Number(x.amount)));
      }
      if ($('doctorCommissionServiceChart')) {
        doctorServiceChart = drawChart($('doctorCommissionServiceChart'), doctorServiceChart,
          (data.by_service || []).map(x => x.service_type), (data.by_service || []).map(x => Number(x.amount)), "doughnut");
      }
      await Promise.all([loadCommissionTransactions(), loadMySettlements()]);
    } catch (err) {
      console.error("Commission dashboard failed", err);
      doctorBalanceLoaded = false;
      if (requestButton) { requestButton.disabled = true; requestButton.textContent = "Balance unavailable"; }
    }
  }

  async function loadCommissionTransactions() {
    if (!$('commissionTransactionsBody')) return;
    clearTimeout(searchTimer);
    const requestToken = ++transactionLoadToken;
    const q = $('commissionSearch').value.trim();
    searchTimer = setTimeout(async () => {
      const period = $('commissionPeriod').value || currentPeriod();
      try {
        const sort = $('commissionSort').value;
        const data = await apiFetch(`/api/commissions/transactions?period=${encodeURIComponent(period)}&page=${doctorPage}&page_size=20&sort=${encodeURIComponent(sort)}&q=${encodeURIComponent(q)}`);
        if (requestToken !== transactionLoadToken) return;
        doctorTotal = data.total;
        $('commissionPageLabel').textContent = `Page ${data.page} · ${data.total} transactions`;
        $('commissionTransactionsBody').innerHTML = data.items.length ? data.items.map(row => {
          const entryLabel = row.type === "REVERSAL" ? "Refund adjustment" : row.type === "ADJUSTMENT" ? "Manual adjustment" : "Earnings";
          const ruleLabel = row.calculation_type === "PERCENTAGE" && row.rate ? `${esc(row.rate)}% of bill` : "Fixed per service";
          return `<tr><td>${esc(new Date(row.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }))}<br><small>${entryLabel}</small></td>
            <td><strong>${esc(row.invoice_number)}</strong><br><small>${esc(humanize(row.service_type))} · ${esc(row.description)}</small></td>
            <td>${fmt(row.calculation_base)}</td><td>${ruleLabel}</td><td><strong>${fmt(row.amount)}</strong></td></tr>`;
        }).join("") : '<tr><td colspan="5">No earnings recorded for this month.</td></tr>';
      } catch (err) { if (requestToken === transactionLoadToken) $('commissionTransactionsBody').innerHTML = '<tr><td colspan="5">Commission history could not be loaded.</td></tr>'; }
    }, 250);
  }

  function commissionPage(delta) {
    const next = doctorPage + delta;
    if (next < 1 || (next - 1) * 20 >= doctorTotal) return;
    doctorPage = next;
    loadCommissionTransactions();
  }

  async function loadMySettlements() {
    const body = $('mySettlementBody');
    if (!body) return;
    const requestToken = ++settlementLoadToken;
    try {
      const rows = await apiFetch("/api/commissions/settlements");
      if (requestToken !== settlementLoadToken) return;
      body.innerHTML = rows.length ? rows.map(row => `<tr><td>${esc(row.request_number)}</td><td>${esc(row.period)}</td>
        <td>${fmt(row.amount)}</td><td><span class="badge ${row.status === "PAID" ? "badge-success" : row.status === "REJECTED" ? "badge-danger" : "badge-warning"}">${esc(settlementLabel(row.status))}</span></td>
        <td>${row.payout ? `${esc(row.payout.reference)}<br><small>${esc(row.payout.paid_at)}</small>` : "Not paid yet"}</td></tr>`).join("") : '<tr><td colspan="5">No payout requests yet.</td></tr>';
    } catch (err) { if (requestToken === settlementLoadToken) body.innerHTML = '<tr><td colspan="5">Settlement requests could not be loaded.</td></tr>'; }
  }

  function previewDoctorCommission() {
    if (!$('doctorCommissionPanel')) return;
    doctorLoadToken += 1;
    transactionLoadToken += 1;
    settlementLoadToken += 1;
    clearTimeout(searchTimer);
    const notice = $('doctorCommissionPreviewNotice');
    if (notice) {
      notice.textContent = "DEMONSTRATION ONLY — these figures are examples, not your earnings. No records were saved. Select Refresh to return to your real account.";
      notice.hidden = false;
    }
    doctorBalanceLoaded = false;
    doctorAvailableAmount = 0;
    const sample = {
      earned: 12450, pending: 1850, available: 9200, reserved: 2000,
      approved: 1250, paid: 3500, previous: 9800, reversed: 650
    };
    $('commissionEarned').textContent = fmt(sample.earned);
    $('commissionPending').textContent = fmt(sample.pending);
    $('commissionAvailable').textContent = fmt(sample.available);
    $('commissionReserved').textContent = fmt(sample.reserved);
    $('commissionApproved').textContent = fmt(sample.approved);
    $('commissionPaid').textContent = fmt(sample.paid);
    $('commissionPrevious').textContent = fmt(sample.previous);
    $('commissionPreviousLabel').textContent = "Net earned in 2026-09";
    $('commissionReversed').textContent = fmt(sample.reversed);
    if ($('commissionRequestAmount')) $('commissionRequestAmount').max = sample.available;
    if ($('commissionRequestForm')) $('commissionRequestForm').querySelectorAll("input, button").forEach(control => { control.disabled = true; });

    doctorTotal = 3;
    $('commissionPageLabel').textContent = "Sample preview · 3 earnings records";
    $('commissionTransactionsBody').innerHTML = `
      <tr><td>19 Oct 2026<br><small>Earnings</small></td><td><strong>INV-2026-1048</strong><br><small>Consultation · OPD visit</small></td><td>${fmt(4500)}</td><td>10% of bill</td><td><strong>${fmt(450)}</strong></td></tr>
      <tr><td>17 Oct 2026<br><small>Earnings</small></td><td><strong>INV-2026-1031</strong><br><small>Procedure · Minor procedure</small></td><td>${fmt(120000)}</td><td>8% of bill</td><td><strong>${fmt(9600)}</strong></td></tr>
      <tr><td>14 Oct 2026<br><small>Earnings</small></td><td><strong>INV-2026-1009</strong><br><small>Consultation · Specialist visit</small></td><td>${fmt(24000)}</td><td>10% of bill</td><td><strong>${fmt(2400)}</strong></td></tr>`;
    $('mySettlementBody').innerHTML = `
      <tr><td>REQ-008</td><td>Oct 2026</td><td>${fmt(2000)}</td><td><span class="badge badge-warning">In review</span></td><td>Not paid yet</td></tr>
      <tr><td>REQ-005</td><td>Sep 2026</td><td>${fmt(3500)}</td><td><span class="badge badge-success">Paid</span></td><td>DEMO-NEFT-1082<br><small>04 Oct 2026</small></td></tr>`;
    doctorChart = drawChart($('doctorCommissionChart'), doctorChart,
      ["Jun", "Jul", "Aug", "Sep", "Oct"], [7200, 9150, 8400, sample.previous, sample.earned]);
    doctorServiceChart = drawChart($('doctorCommissionServiceChart'), doctorServiceChart,
      ["Consultation", "Procedure"], [2850, 9600], "doughnut");
  }

  async function submitCommissionRequest(event) {
    event.preventDefault();
    if (settlementSubmitting) return;
    if (!doctorBalanceLoaded) {
      showToast("Your real available amount has not loaded yet. Refresh and try again.", "warning");
      return;
    }
    if (!$('doctorCommissionPreviewNotice').hidden) {
      showToast("Switch back to your real account data before requesting a payout.", "warning");
      return;
    }
    const amount = $('commissionRequestAmount')?.value || 0;
    const period = $('commissionPeriod')?.value || currentPeriod();
    const requestedAmount = Number(amount);
    if (!Number.isFinite(requestedAmount) || requestedAmount <= 0) {
      if ($('commissionRequestAmount')) $('commissionRequestAmount').focus();
      showToast("Enter an amount greater than ₹0.00.", "warning");
      return;
    }
    if (requestedAmount > doctorAvailableAmount) {
      if ($('commissionRequestAmount')) $('commissionRequestAmount').focus();
      showToast(`You can request up to ${fmt(doctorAvailableAmount)} right now.`, "warning");
      return;
    }
    if (!confirm(`Payout request summary\n\nAmount: ${fmt(requestedAmount)}\nAvailable now: ${fmt(doctorAvailableAmount)}\nMonth: ${period}\n\nFinance must approve the request before payment. Send this request?`)) return;
    const idem = persistedKey("settlement", `${period}_${amount}`);
    const submitButton = $('commissionRequestForm')?.querySelector('[type="submit"]');
    settlementSubmitting = true;
    if (submitButton) { submitButton.disabled = true; submitButton.textContent = "Sending request…"; }
    try {
      const result = await apiFetch("/api/commissions/settlements", { method: "POST", body: JSON.stringify({ period, amount, idempotency_key: idem.value }) });
      if (result) {
        idem.clear();
        const status = settlementLabel(result.status);
        showToast(`Request ${result.request_number} was received. Status: ${status}.`, "success");
        if ($('commissionRequestForm')) $('commissionRequestForm').reset();
        await loadDoctorCommission(true);
      }
    } catch (err) {
      // apiFetch displays the server's explanation; leave the entered amount in place for correction or retry.
    } finally {
      settlementSubmitting = false;
      if (submitButton) { submitButton.disabled = false; submitButton.textContent = "Request my payment"; }
    }
  }

  function downloadCommissionStatement() {
    const period = $('commissionPeriod')?.value || currentPeriod();
    window.location.href = `/api/commissions/statement.pdf?period=${encodeURIComponent(period)}`;
  }

  let doctorLedgerPageNum = 1;
  let doctorLedgerTotal = 0;

  async function loadDoctorLedger(page = 1) {
    const tbody = $('commissionLedgerBody');
    if (!tbody) return;
    doctorLedgerPageNum = page;
    const status = $('ledgerStatusFilter')?.value || "";
    const patientId = $('ledgerPatientFilter')?.value || "";
    const period = $('commissionPeriod')?.value || "";

    let url = `/api/commissions/ledger?page=${page}&page_size=20`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (patientId) url += `&patient_id=${encodeURIComponent(patientId)}`;
    if (period) url += `&period=${encodeURIComponent(period)}`;

    try {
      const data = await apiFetch(url);
      doctorLedgerTotal = data.total;
      const pageLabel = $('commissionLedgerPageLabel');
      if (pageLabel) pageLabel.textContent = `Showing ${data.items.length} of ${data.total} records (Page ${data.page})`;

      if (!data.items || data.items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:2rem;color:var(--text-muted);">No commission records found for selected filters.</td></tr>`;
        return;
      }

      tbody.innerHTML = data.items.map(row => {
        let blockingText = "";
        if (row.blocking_invoices && row.blocking_invoices.length > 0) {
          blockingText = `<br><span style="font-size:11px;color:var(--warning-text);">Unpaid bills: ${row.blocking_invoices.map(b => `${esc(b.invoice_number)} (₹${esc(b.unpaid_amount)} unpaid)`).join(", ")}</span>`;
        }
        return `
          <tr>
            <td>
              <strong>#${row.id}</strong><br>
              <small class="kpi-sub">${esc(row.accrued_at || "-")}</small>
            </td>
            <td>
              <strong>${esc(row.patient_name)}</strong><br>
              <small class="kpi-sub">MRN: ${esc(row.patient_mrn)}</small>
            </td>
            <td>
              <strong>${esc(row.invoice_number || "Invoice")}</strong><br>
              <small class="kpi-sub">${esc(humanize(row.service_type))} · ${esc(row.description)}</small>
            </td>
            <td>${fmt(row.base_amount)}</td>
            <td><strong>${fmt(row.calculated_commission)}</strong></td>
            <td>
              <span class="badge ${esc(row.chip_class)}" title="${esc(row.explanation)}">
                ${esc(row.chip_label)}
              </span>
            </td>
            <td>
              <span style="font-size:var(--font-xs);">${esc(row.explanation || row.execution_audit_log || "In order")}</span>
              ${blockingText}
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--danger-text);">Error loading ledger: ${esc(err.message)}</td></tr>`;
    }
  }

  function doctorLedgerPage(delta) {
    const next = doctorLedgerPageNum + delta;
    if (next < 1 || (next - 1) * 20 >= doctorLedgerTotal) return;
    loadDoctorLedger(next);
  }

  async function requestInstantPayout(doctorId = null) {
    const btn = $('btnInstantPayout');
    const outcomeBox = $('instantPayoutOutcome');
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Processing Payout…";
    }
    if (outcomeBox) {
      outcomeBox.style.display = "block";
      outcomeBox.innerHTML = `
        <div style="padding:1rem;background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:var(--radius-md);color:var(--text-muted);font-size:var(--font-sm);">
          Checking patient invoices and settlement rules…
        </div>
      `;
    }

    try {
      const url = doctorId ? `/api/commissions/instant-payout?doctor_id=${doctorId}` : `/api/commissions/instant-payout`;
      const res = await apiFetch(url, { method: "POST" });

      if (res.success) {
        showToast("Instant payout processed successfully!", "success");
        if (outcomeBox) {
          outcomeBox.innerHTML = `
            <div style="background:var(--success-bg);border:1px solid var(--success-border);border-radius:var(--radius-md);padding:1.25rem;">
              <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.75rem;">
                <div style="display:flex;align-items:center;gap:0.5rem;">
                  <span class="badge badge-success">${esc(res.chip_label || "[🔓 Ready to Pull]")}</span>
                  <strong style="color:var(--success-text);font-size:1.05rem;">Payout of ₹${esc(Number(res.payout_amount || 0).toFixed(2))} Processed</strong>
                </div>
                <span style="font-size:var(--font-xs);color:var(--success-text);">${esc(res.paid_at || "")}</span>
              </div>
              <p style="margin:0 0 0.75rem;font-size:var(--font-sm);color:var(--text-main);">${esc(res.message)}</p>
              <div style="background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:var(--radius-sm);padding:0.75rem;font-size:var(--font-xs);display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:0.5rem;">
                <div><strong>Account Holder:</strong> ${esc(res.bank_details?.account_holder || "Doctor")}</div>
                <div><strong>Bank:</strong> ${esc(res.bank_details?.bank_name || "State Bank of India")}</div>
                <div><strong>Account:</strong> ${esc(res.bank_details?.account_number || "****")}</div>
                <div><strong>IFSC:</strong> ${esc(res.bank_details?.ifsc || "SBIN0001234")}</div>
                <div><strong>Mode:</strong> ${esc(res.bank_details?.transfer_mode || "IMPS")}</div>
                <div><strong>Reference (UTR):</strong> <code style="font-size:var(--font-xs);">${esc(res.payment_reference || "-")}</code></div>
              </div>
            </div>
          `;
        }
      } else {
        showToast(res.message || "Payout cannot be settled yet.", "warning");
        let blockingHtml = "";
        if (res.blocking_details && res.blocking_details.length > 0) {
          blockingHtml = `
            <div style="margin-top:0.75rem;padding:0.75rem;background:var(--bg-surface);border:1px solid var(--warning-border);border-radius:var(--radius-sm);font-size:var(--font-xs);">
              <div style="font-weight:600;margin-bottom:0.4rem;color:var(--warning-text);">Uncompleted Patient Invoices Blocking Payout:</div>
              <ul style="margin:0;padding-left:1.25rem;">
                ${res.blocking_details.map(b => `
                  <li style="margin-bottom:0.25rem;">
                    <strong>${esc(b.patient_name)}</strong> (MRN: ${esc(b.patient_mrn)}) ·
                    Invoice: <code>${esc(b.invoice_number)}</code> ·
                    Unpaid Balance: <strong>${esc(b.unpaid_balance)}</strong> ·
                    Status: <span class="badge badge-warning" style="font-size:10px;">${esc(b.payment_status)}</span>
                  </li>
                `).join("")}
              </ul>
            </div>
          `;
        }
        if (outcomeBox) {
          outcomeBox.innerHTML = `
            <div style="background:var(--warning-bg);border:1px solid var(--warning-border);border-radius:var(--radius-md);padding:1.25rem;">
              <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
                <span class="badge badge-warning">${esc(res.chip_label || "[🔒 Waiting for Patient Bill Settlement]")}</span>
                <strong style="color:var(--warning-text);font-size:1.05rem;">Payout Cannot Be Settled Yet</strong>
              </div>
              <p style="margin:0;font-size:var(--font-sm);color:var(--text-main);">${esc(res.message)}</p>
              ${blockingHtml}
            </div>
          `;
        }
      }
    } catch (err) {
      if (outcomeBox) {
        outcomeBox.innerHTML = `
          <div style="background:var(--danger-bg);border:1px solid var(--danger-border);border-radius:var(--radius-md);padding:1rem;color:var(--danger-text);font-size:var(--font-sm);">
            ${esc(err.message || "Could not complete instant payout request.")}
          </div>
        `;
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Request Instant Payout";
      }
      await Promise.all([loadDoctorCommission(true), loadDoctorLedger(doctorLedgerPageNum)]);
    }
  }

  async function evaluateCommissions(doctorId = null) {
    try {
      const url = doctorId ? `/api/commissions/evaluate?doctor_id=${doctorId}` : `/api/commissions/evaluate`;
      const res = await apiFetch(url, { method: "POST" });
      const msg = res.result?.message || "Safety locks and patient bills evaluated successfully.";
      showToast(msg, "success");
      await Promise.all([loadDoctorCommission(true), loadDoctorLedger(1)]);
    } catch (err) {
      showToast(err.message || "Failed to evaluate commissions.", "danger");
    }
  }

  let adminLedgerPageNum = 1;
  let adminLedgerTotal = 0;

  async function loadAdminLedger(page = 1) {
    const tbody = $('adminLedgerBody');
    if (!tbody) return;
    adminLedgerPageNum = page;
    const doctorId = $('adminLedgerDoctorFilter')?.value || "";
    const department = $('adminLedgerDeptFilter')?.value?.trim() || "";
    const status = $('adminLedgerStatusFilter')?.value || "";
    const patientId = $('adminLedgerPatientFilter')?.value || "";
    const period = $('financeCommissionPeriod')?.value || "";

    let url = `/api/commissions/ledger?page=${page}&page_size=20`;
    if (doctorId) url += `&doctor_id=${encodeURIComponent(doctorId)}`;
    if (department) url += `&department=${encodeURIComponent(department)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (patientId) url += `&patient_id=${encodeURIComponent(patientId)}`;
    if (period) url += `&period=${encodeURIComponent(period)}`;

    try {
      const data = await apiFetch(url);
      adminLedgerTotal = data.total;
      const pageLabel = $('adminLedgerPageLabel');
      if (pageLabel) pageLabel.textContent = `Showing ${data.items.length} of ${data.total} records (Page ${data.page})`;

      if (!data.items || data.items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:2rem;color:var(--text-muted);">No ledger entries found matching filters.</td></tr>`;
        return;
      }

      tbody.innerHTML = data.items.map(row => {
        let blockingText = "";
        if (row.blocking_invoices && row.blocking_invoices.length > 0) {
          blockingText = `<br><span style="font-size:11px;color:var(--warning-text);">Unpaid bills: ${row.blocking_invoices.map(b => `${esc(b.invoice_number)} (₹${esc(b.unpaid_amount)})`).join(", ")}</span>`;
        }
        return `
          <tr>
            <td>
              <strong>#${row.id}</strong><br>
              <small class="kpi-sub">${esc(row.accrued_at || "-")}</small>
            </td>
            <td>
              <strong>${esc(row.doctor_name)}</strong><br>
              <small class="kpi-sub">${esc(row.department || "Medical")}</small>
            </td>
            <td>
              <strong>${esc(row.patient_name)}</strong><br>
              <small class="kpi-sub">MRN: ${esc(row.patient_mrn)}</small>
            </td>
            <td>
              <strong>${esc(row.invoice_number || "Invoice")}</strong><br>
              <small class="kpi-sub">${esc(humanize(row.service_type))}</small>
            </td>
            <td>${fmt(row.base_amount)}</td>
            <td><strong>${fmt(row.calculated_commission)}</strong></td>
            <td>
              <span class="badge ${esc(row.chip_class)}" title="${esc(row.explanation)}">
                ${esc(row.chip_label)}
              </span>
            </td>
            <td>
              <span style="font-size:var(--font-xs);">${esc(row.explanation || row.execution_audit_log || "In order")}</span>
              ${blockingText}
            </td>
          </tr>
        `;
      }).join("");
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;color:var(--danger-text);">Error loading ledger: ${esc(err.message)}</td></tr>`;
    }
  }

  function adminLedgerPage(delta) {
    const next = adminLedgerPageNum + delta;
    if (next < 1 || (next - 1) * 20 >= adminLedgerTotal) return;
    loadAdminLedger(next);
  }

  async function adminEvaluateRules() {
    try {
      const doctorId = $('adminLedgerDoctorFilter')?.value || null;
      const url = doctorId ? `/api/commissions/evaluate?doctor_id=${doctorId}` : `/api/commissions/evaluate`;
      const res = await apiFetch(url, { method: "POST" });
      showToast("Commission safety locks evaluated successfully.", "success");
      await Promise.all([loadFinanceCommission(), loadAdminLedger(1)]);
    } catch (err) {
      showToast(err.message || "Evaluation failed.", "danger");
    }
  }

  async function adminInstantPayout() {
    const doctorSelect = $('adminLedgerDoctorFilter');
    const doctorId = doctorSelect ? doctorSelect.value : null;
    if (!doctorId) {
      showToast("Please select a specific doctor first to request payout.", "warning");
      return;
    }
    const doctorName = doctorSelect.options[doctorSelect.selectedIndex].text;
    if (!confirm(`Trigger instant payout check and bank settlement for ${doctorName}?`)) return;

    const outcomeBox = $('adminInstantPayoutOutcome');
    if (outcomeBox) {
      outcomeBox.style.display = "block";
      outcomeBox.innerHTML = `<div style="padding:1rem;background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:var(--radius-md);color:var(--text-muted);font-size:var(--font-sm);">Processing payout check for ${esc(doctorName)}…</div>`;
    }

    try {
      const res = await apiFetch(`/api/commissions/instant-payout?doctor_id=${doctorId}`, { method: "POST" });
      if (res.success) {
        showToast(`Instant payout of ₹${Number(res.payout_amount || 0).toFixed(2)} processed for ${doctorName}!`, "success");
        if (outcomeBox) {
          outcomeBox.innerHTML = `
            <div style="background:var(--success-bg);border:1px solid var(--success-border);border-radius:var(--radius-md);padding:1rem;">
              <span class="badge badge-success">${esc(res.chip_label)}</span>
              <strong>Payout of ₹${esc(Number(res.payout_amount || 0).toFixed(2))} settled for ${esc(doctorName)}</strong>
              <div style="font-size:var(--font-xs);margin-top:0.35rem;">Reference: <code>${esc(res.payment_reference)}</code> · Transferred via ${esc(res.bank_details?.transfer_mode || "IMPS")}</div>
            </div>
          `;
        }
      } else {
        showToast(res.message, "warning");
        let blocking = "";
        if (res.blocking_details && res.blocking_details.length) {
          blocking = `<div style="margin-top:0.4rem;font-size:var(--font-xs);"><strong>Blocking Bills:</strong> ${res.blocking_details.map(b => `${esc(b.invoice_number)} (${esc(b.unpaid_balance)})`).join(", ")}</div>`;
        }
        if (outcomeBox) {
          outcomeBox.innerHTML = `
            <div style="background:var(--warning-bg);border:1px solid var(--warning-border);border-radius:var(--radius-md);padding:1rem;">
              <span class="badge badge-warning">${esc(res.chip_label)}</span>
              <strong>Payout Locked:</strong> ${esc(res.message)}
              ${blocking}
            </div>
          `;
        }
      }
    } catch (err) {
      if (outcomeBox) {
        outcomeBox.innerHTML = `<div style="background:var(--danger-bg);border:1px solid var(--danger-border);border-radius:var(--radius-md);padding:1rem;color:var(--danger-text);font-size:var(--font-sm);">${esc(err.message)}</div>`;
      }
    } finally {
      await Promise.all([loadFinanceCommission(), loadAdminLedger(adminLedgerPageNum)]);
    }
  }

  async function loadFinanceCommission() {
    if (!$('financeCommissionPanel')) return;
    const loadToken = ++financeLoadToken;
    const previewNotice = $('financeChartPreviewNotice');
    if (previewNotice) { previewNotice.hidden = true; previewNotice.textContent = ""; }
    const input = $('financeCommissionPeriod');
    if (!input.value) input.value = currentPeriod();
    const period = input.value;
    try {
      const [report, rules, settlements, payments, history, audit] = await Promise.all([
        apiFetch(`/api/commissions/reports/monthly?period=${encodeURIComponent(period)}`),
        apiFetch("/api/commissions/rules"), apiFetch("/api/commissions/settlements"),
        apiFetch("/api/billing/payments/pending-reconciliation?page=1&page_size=50"),
        apiFetch(`/api/billing/payments/history?period=${encodeURIComponent(period)}&page=1&page_size=50`),
        apiFetch("/api/commissions/audit?limit=100")
      ]);
      if (loadToken !== financeLoadToken) return;
      if (!report) return;
      $('finCollections').textContent = fmt(report.reconciled_collections);
      $('finCommissionEarned').textContent = fmt(report.commission_earned);
      $('finCommissionReversals').textContent = fmt(report.reversals);
      $('finCommissionNet').textContent = fmt(report.net_commission);
      $('finCommissionPaid').textContent = fmt(report.payouts);
      $('finCommissionLiability').textContent = fmt(report.outstanding_liability);
      $('finCommissionAvailable').textContent = fmt(report.available_balance);
      $('finCommissionReserved').textContent = fmt(report.reserved_balance);
      $('finCommissionApproved').textContent = fmt(report.approved_unpaid_balance);
      renderRules(rules || []);
      renderFinanceSettlements(settlements || []);
      renderPendingPayments((payments && payments.items) || []);
      renderFinancePaymentHistory((history && history.items) || []);
      renderCommissionAudit(audit || []);
      await loadAdminLedger(adminLedgerPageNum);
      financeDoctorChart = drawChart($('financeDoctorChart'), financeDoctorChart,
        (report.doctors || []).map(x => x.doctor_name), (report.doctors || []).map(x => Number(x.net_commission)));
      financeServiceChart = drawChart($('financeServiceChart'), financeServiceChart,
        (report.by_service || []).map(x => x.service_type), (report.by_service || []).map(x => Number(x.amount)), "doughnut");
      financeCompareChart = drawChart($('financeCompareChart'), financeCompareChart,
        ["Earned", "Paid"], [Number(report.net_commission), Number(report.payouts)]);
      financeStatusChart = drawChart($('financeStatusChart'), financeStatusChart,
        (report.request_status || []).map(x => x.status), (report.request_status || []).map(x => Number(x.count)), "doughnut");
      financeCollectionsChart = drawChart($('financeCollectionsChart'), financeCollectionsChart,
        ["Collections", "Commission"], [Number(report.reconciled_collections), Number(report.net_commission)]);
      financeBalancesChart = drawChart($('financeBalancesChart'), financeBalancesChart,
        ["Available", "Reserved", "Approved unpaid"], [Number(report.available_balance), Number(report.reserved_balance), Number(report.approved_unpaid_balance)], "doughnut");
      financeDepartmentChart = drawChart($('financeDepartmentChart'), financeDepartmentChart,
        (report.by_department || []).map(x => x.department), (report.by_department || []).map(x => Number(x.amount)));
      financeReversalsChart = drawChart($('financeReversalsChart'), financeReversalsChart,
        (report.reversals_by_month || []).map(x => x.period), (report.reversals_by_month || []).map(x => Number(x.amount)), "line");
      financeLiabilityChart = drawChart($('financeLiabilityChart'), financeLiabilityChart,
        (report.liability_trend || []).map(x => x.period), (report.liability_trend || []).map(x => Number(x.amount)), "line");
    } catch (err) { console.error("Finance commission report failed", err); }
  }

  function previewFinanceCharts() {
    if (!$('financeCommissionPanel')) return;
    financeLoadToken += 1;
    const notice = $('financeChartPreviewNotice');
    if (notice) {
      notice.textContent = "Sample chart preview only. No sample financial records were saved. Use Refresh reports to return to live data.";
      notice.hidden = false;
    }
    financeDoctorChart = drawChart($('financeDoctorChart'), financeDoctorChart,
      ["Dr. A. Mehta", "Dr. N. Shah", "Dr. P. Iyer"], [18450, 12700, 9300]);
    financeServiceChart = drawChart($('financeServiceChart'), financeServiceChart,
      ["Consultation", "Procedure", "Lab test"], [21800, 14200, 4450], "doughnut");
    financeCompareChart = drawChart($('financeCompareChart'), financeCompareChart,
      ["Jun", "Jul", "Aug", "Sep", "Oct"], [18200, 24700, 21100, 29400, 32450]);
    financeStatusChart = drawChart($('financeStatusChart'), financeStatusChart,
      ["Pending", "Approved", "Paid", "Rejected"], [3, 2, 7, 1], "doughnut");
    financeCollectionsChart = drawChart($('financeCollectionsChart'), financeCollectionsChart,
      ["Collections", "Commission"], [248500, 32450], "bar");
    financeBalancesChart = drawChart($('financeBalancesChart'), financeBalancesChart,
      ["Available", "Reserved", "Approved unpaid"], [18450, 8200, 12300], "doughnut");
    financeDepartmentChart = drawChart($('financeDepartmentChart'), financeDepartmentChart,
      ["Cardiology", "Orthopedics", "General Medicine"], [17500, 12800, 7650]);
    financeReversalsChart = drawChart($('financeReversalsChart'), financeReversalsChart,
      ["Jun", "Jul", "Aug", "Sep", "Oct"], [0, 1200, 0, 650, 900], "line");
    financeLiabilityChart = drawChart($('financeLiabilityChart'), financeLiabilityChart,
      ["Jun", "Jul", "Aug", "Sep", "Oct"], [21000, 27800, 31600, 40200, 38950], "line");
  }

  function renderRules(rows) {
    const body = $('commissionRulesBody');
    if (!body) return;
    body.innerHTML = rows.length ? rows.map(rule => `<tr><td><strong>${esc(rule.name)}</strong><br><small>#${rule.id}</small></td>
      <td>${esc(rule.doctor_id ? `Doctor ${rule.doctor_id}` : "All doctors")}${rule.department ? `<br>${esc(rule.department)}` : ""}${rule.service_type ? `<br>${esc(rule.service_type)}` : ""}</td>
      <td>${rule.calculation_type === "PERCENTAGE" ? `${esc(rule.rate)}%` : `${fmt(rule.fixed_amount)} / unit`}${rule.min_settlement_threshold ? `<br><small class="kpi-sub">Min: ₹${rule.min_settlement_threshold}</small>` : ""}${rule.require_all_patient_bills_paid ? `<br><small class="badge badge-neutral" style="font-size:10px;">Requires Bills Paid</small>` : ""}</td>
      <td>${esc(rule.effective_from)}${rule.effective_to ? ` – ${esc(rule.effective_to)}` : " onward"}</td>
      <td>${rule.active ? "Active" : "Inactive"}</td><td>${rule.active ? `<button class="btn btn-outline btn-sm" onclick="deactivateCommissionRule(${Number(rule.id)})">Deactivate</button>` : "—"}</td></tr>`).join("") : '<tr><td colspan="6">No commission rules. Add a rule to begin accruals.</td></tr>';
  }

  function renderFinanceSettlements(rows) {
    const body = $('financeSettlementsBody');
    if (!body) return;
    body.innerHTML = rows.length ? rows.map(row => {
      let actions = "—";
      if (row.status === "PENDING") actions = `<button class="btn btn-success btn-sm" onclick="decideCommission(${Number(row.id)},'approve')">Approve</button> <button class="btn btn-outline btn-sm" onclick="decideCommission(${Number(row.id)},'reject')">Reject</button>`;
      if (row.status === "APPROVED") actions = `<button class="btn btn-primary btn-sm" onclick="recordCommissionPayout(${Number(row.id)},'${esc(row.amount)}')">Record payout</button> <button class="btn btn-outline btn-sm" onclick="cancelApprovedSettlement(${Number(row.id)})">Cancel approval</button>`;
      return `<tr><td><strong>${esc(row.doctor_name)}</strong><br><small>${esc(row.department || "")} · ${esc(row.period)} · ${esc(row.request_number)}</small></td>
        <td>${fmt(row.amount)}</td><td><span class="badge ${row.status === "PAID" ? "badge-success" : row.status === "REJECTED" ? "badge-danger" : "badge-warning"}">${esc(row.status)}</span></td><td>${actions}${row.payout ? `<br><small>${esc(row.payout.reference)}</small>` : ""}</td></tr>`;
    }).join("") : '<tr><td colspan="4">No settlement requests.</td></tr>';
  }

  function renderPendingPayments(rows) {
    const body = $('pendingPaymentsBody');
    if (!body) return;
    body.innerHTML = rows.length ? rows.map(row => `<tr><td>#${Number(row.invoice_id)}</td><td>${fmt(row.amount)}</td>
      <td>${esc(row.method)}<br><small>${esc(row.reference || "No transaction reference")}</small></td><td>${esc(row.received_at)}</td>
      <td><button class="btn btn-primary btn-sm" onclick="reconcileCommissionPayment(${Number(row.id)})">Reconcile</button></td></tr>`).join("") : '<tr><td colspan="5">No receipts awaiting reconciliation.</td></tr>';
  }

  function renderFinancePaymentHistory(rows) {
    const body = $('financePaymentHistoryBody');
    if (!body) return;
    body.innerHTML = rows.length ? rows.map(row => `<tr><td><strong>${esc(row.invoice_number)}</strong><br><small>${esc(row.method)} · ${esc(row.reference || "No reference")} · ${fmt(row.amount)}</small></td>
      <td>${fmt(row.refunded)}<br><small>${fmt(row.refundable)} refundable</small></td><td>${esc(row.status)}</td>
      <td>${Number(row.refundable) > 0 ? `<button class="btn btn-outline btn-sm" onclick="recordPaymentRefund(${Number(row.id)},'${esc(row.refundable)}')">Record refund</button>` : "—"}</td></tr>`).join("") : '<tr><td colspan="4">No receipts for this reporting month.</td></tr>';
  }

  function renderCommissionAudit(rows) {
    const body = $('commissionAuditBody');
    if (!body) return;
    body.innerHTML = rows.length ? rows.map(row => `<tr><td>${esc(new Date(row.created_at).toLocaleString())}</td><td>${esc(row.actor)} (${esc(row.role)})</td>
      <td>${esc(row.action)}</td><td>${esc(row.resource_type)} ${esc(row.resource_id || "")}</td><td>${esc(row.details || "")}</td></tr>`).join("") : '<tr><td colspan="5">No commission events recorded.</td></tr>';
  }

  async function createCommissionRule(event) {
    event.preventDefault();
    const type = $('ruleType').value;
    const doctor = $('ruleDoctor').value;
    const department = $('ruleDepartment').value.trim();
    const service = $('ruleService').value;
    if (!doctor && !department && !service) { showToast("Set at least one rule scope: doctor, department, or service type.", "warning"); return; }
    const payload = {
      name: $('ruleName').value.trim(),
      doctor_id: doctor ? Number(doctor) : null,
      department: department || null,
      service_type: service || null,
      calculation_type: type,
      rate: type === "PERCENTAGE" ? $('ruleRate').value : null,
      fixed_amount: type === "FIXED_PER_SERVICE" ? $('ruleFixed').value : null,
      require_all_patient_bills_paid: $('ruleRequireAllPaid') ? $('ruleRequireAllPaid').checked : true,
      min_settlement_threshold: $('ruleThreshold') ? parseFloat($('ruleThreshold').value || 0) : 0,
      effective_from: $('ruleStart').value,
      effective_to: null
    };
    if (!confirm(`Create the ${type.toLowerCase().replace(/_/g, " ")} rule “${payload.name}” effective ${payload.effective_from}? This rule affects future reconciliations.`)) return;
    const idem = persistedKey("rule", `${payload.name}_${payload.effective_from}_${doctor || "all"}_${service || "all"}`);
    try {
      await apiFetch("/api/commissions/rules", { method: "POST", body: JSON.stringify({ ...payload, idempotency_key: idem.value }) });
      idem.clear();
      showToast("Commission rule version created.", "success");
      $('commissionRuleForm').reset();
      await loadFinanceCommission();
    } catch (err) {}
  }

  async function createCommissionAdjustment(event) {
    event.preventDefault();
    const amount = $('adjustAmount').value;
    const reason = $('adjustReason').value.trim();
    const doctorId = Number($('adjustDoctor').value);
    const period = $('financeCommissionPeriod').value || currentPeriod();
    if (!confirm(`Record an audited ${fmt(amount)} commission adjustment for doctor ID ${doctorId} in ${period}? Reason: ${reason}`)) return;
    const idem = persistedKey("adjustment", `${doctorId}_${period}_${amount}`);
    try {
      await apiFetch("/api/commissions/adjustments", { method: "POST", body: JSON.stringify({ doctor_id: doctorId,
        period, amount, reason, idempotency_key: idem.value }) });
      idem.clear();
      showToast("Commission adjustment recorded.", "success");
      $('commissionAdjustmentForm').reset();
      await loadFinanceCommission();
    } catch (err) {}
  }

  async function loadCashierReconciliation() {
    const body = $('cashierPaymentReconBody');
    if (!body) return;
    try {
      const result = await apiFetch("/api/billing/payments/pending-reconciliation?page=1&page_size=50");
      body.innerHTML = result.items.length ? result.items.map(row => `<tr><td>Invoice #${Number(row.invoice_id)}</td><td>${fmt(row.amount)}</td>
        <td>${esc(row.method)}<br><small>${esc(row.reference || "No transaction reference")}</small></td><td>${esc(row.received_at)}</td>
        <td><button class="btn btn-primary btn-sm" onclick="reconcileCommissionPayment(${Number(row.id)})">Reconcile receipt</button></td></tr>`).join("") : '<tr><td colspan="5">No receipts awaiting reconciliation.</td></tr>';
    } catch (err) { body.innerHTML = '<tr><td colspan="5">Receipt queue is unavailable.</td></tr>'; }
  }

  async function deactivateCommissionRule(id) {
    if (!confirm(`Deactivate commission rule #${id}? Existing ledger entries remain unchanged.`)) return;
    try { await apiFetch(`/api/commissions/rules/${id}/deactivate`, { method: "POST" }); showToast("Rule deactivated.", "success"); await loadFinanceCommission(); }
    catch (err) {}
  }

  async function decideCommission(id, action) {
    let note = "";
    if (action === "reject") {
      note = prompt("Enter the reason for rejecting this settlement request:") || "";
      if (!note.trim()) { showToast("A rejection reason is required.", "warning"); return; }
    }
    if (!confirm(`${action === "approve" ? "Approve" : "Reject"} settlement request #${id}?`)) return;
    try { await apiFetch(`/api/commissions/settlements/${id}/${action}`, { method: "POST", body: JSON.stringify({ note }) });
      showToast(`Settlement request ${action}d.`, "success"); await loadFinanceCommission(); }
    catch (err) {}
  }

  async function recordCommissionPayout(id, amount) {
    const reference = prompt(`Confirm the actual payout of ${fmt(amount)}. Enter its verified bank / UPI / cheque reference:`);
    if (!reference || !reference.trim()) return;
    const evidence = prompt("Enter brief verification evidence (for example, bank advice date or voucher number):");
    if (!evidence || !evidence.trim()) return;
    if (!confirm(`Record actual payout of ${fmt(amount)} against request #${id}, reference ${reference}?`)) return;
    try { await apiFetch(`/api/commissions/settlements/${id}/payout`, { method: "POST", body: JSON.stringify({
      payment_method: "BANK_TRANSFER", payment_reference: reference.trim(), evidence_note: evidence.trim(), idempotency_key: key("payout") }) });
      showToast("Payout recorded with evidence.", "success"); await loadFinanceCommission(); }
    catch (err) {}
  }

  async function cancelApprovedSettlement(id) {
    const note = prompt("Reason for cancelling this approved, unpaid request:");
    if (!note || !note.trim()) return;
    if (!confirm(`Cancel approved settlement request #${id} and release its reserve?`)) return;
    try {
      await apiFetch(`/api/commissions/settlements/${id}/cancel`, { method: "POST", body: JSON.stringify({ note: note.trim() }) });
      showToast("Approved settlement cancelled and reserve released.", "success");
      await loadFinanceCommission();
    } catch (err) {}
  }

  async function recordPaymentRefund(id, refundable) {
    const amount = prompt(`Unrefunded receipt balance is ${fmt(refundable)}. Enter the amount already refunded to the patient:`);
    if (amount === null || !Number.isFinite(Number(amount)) || Number(amount) <= 0 || Number(amount) > Number(refundable)) return;
    const reason = prompt("Reason for the refund (required):");
    if (!reason || reason.trim().length < 3) return;
    const reference = prompt("Verified refund reference / voucher (optional):") || null;
    if (!confirm(`Record the confirmed refund of ${fmt(amount)}? Any earned commission will receive an audited reversal.`)) return;
    const idem = persistedKey("refund", `${id}_${amount}`);
    try {
      await apiFetch(`/api/billing/payments/${id}/refund`, { method: "POST", body: JSON.stringify({
        amount, reason: reason.trim(), reference, idempotency_key: idem.value }) });
      idem.clear();
      showToast("Refund and related commission reversal recorded.", "success");
      await loadFinanceCommission();
    } catch (err) {}
  }

  async function reconcileCommissionPayment(id) {
    if (!confirm(`Mark payment #${id} as reconciled? This makes its eligible service lines available for commission accrual.`)) return;
    try { const result = await apiFetch(`/api/billing/payments/${id}/reconcile`, { method: "POST" });
      showToast(`Receipt reconciled. ${result.generated_entries} commission entries generated.`, "success");
      await Promise.all([loadFinanceCommission(), loadCashierReconciliation()]);
      if (typeof loadCashierAnalytics === "function") loadCashierAnalytics(); }
    catch (err) {}
  }

  function downloadFinanceCommissionReport() {
    const period = $('financeCommissionPeriod')?.value || currentPeriod();
    window.location.href = `/api/commissions/reports/monthly.pdf?period=${encodeURIComponent(period)}`;
  }

  function toggleElement(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const isHidden = (el.style.display === "none" || !el.style.display);
    el.style.display = isHidden ? "block" : "none";
    if (isHidden) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      const firstInput = el.querySelector("input:not([disabled]), select:not([disabled])");
      if (firstInput) firstInput.focus();
    }
  }

  Object.assign(window, {
    loadDoctorCommission, loadCommissionTransactions, commissionPage,
    previewDoctorCommission,
    submitCommissionRequest, downloadCommissionStatement, loadFinanceCommission,
    previewFinanceCharts, createCommissionRule, deactivateCommissionRule, decideCommission, recordCommissionPayout,
    cancelApprovedSettlement, recordPaymentRefund, createCommissionAdjustment,
    loadCashierReconciliation, reconcileCommissionPayment, downloadFinanceCommissionReport,
    requestInstantPayout, evaluateCommissions, loadDoctorLedger, doctorLedgerPage,
    adminEvaluateRules, adminInstantPayout, loadAdminLedger, adminLedgerPage, toggleElement
  });

  document.addEventListener("DOMContentLoaded", () => {
    if ($("doctorCommissionPanel")) {
      $("commissionPeriod").value = currentPeriod();
      $("commissionPeriod").addEventListener("change", () => { doctorPage = 1; doctorLedgerPageNum = 1; loadDoctorCommission(true); });
      loadDoctorCommission();
      loadDoctorLedger(1);
    }
    if ($("financeCommissionPanel")) {
      $("financeCommissionPeriod").value = currentPeriod();
      $("financeCommissionPeriod").addEventListener("change", () => { loadFinanceCommission(); loadAdminLedger(1); });
      $("ruleStart").value = new Date().toISOString().slice(0, 10);
      $("ruleType").addEventListener("change", () => {
        const fixed = $("ruleType").value === "FIXED_PER_SERVICE";
        $("ruleRate").disabled = fixed;
        $("ruleFixed").disabled = !fixed;
      });
      $("ruleType").dispatchEvent(new Event("change"));
      loadFinanceCommission();
      loadAdminLedger(1);
    }
    if ($("cashierPaymentReconBody")) loadCashierReconciliation();
  });
})();
