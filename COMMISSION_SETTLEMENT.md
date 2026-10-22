# Commission and settlement implementation

## Repository audit

- The application is FastAPI, SQLAlchemy and SQLite with server-rendered Jinja pages, vanilla JavaScript, and an existing local Chart.js asset. Schema startup uses `Base.metadata.create_all`; there is no migration framework, background worker, tenant key, refund table, or external bank/payment-settlement connector.
- Patient invoices already contain line items and an aggregate `paid_amount` / `payment_status`. Cashier collection previously updated the invoice totals and overwrote its most recent transaction reference. It did not retain individual payment events or record a separate reconciliation.
- OPD invoices link to an `Encounter`, which links to its doctor. Discharge invoices link to an inpatient record and attending doctor. Invoice line types include consultation, pharmacy, lab, and bed charges. There is no provider foreign key on each invoice line.
- The doctor commission/payroll and payout workflow did not exist. Existing billing, doctor, admin, cashier, role-permission, page, and Chart.js components were reused.
- `Invoice` and `InvoiceItem` authoritative source fields still use SQL floating-point columns. New payment, allocation, commission, refund, settlement, and payout amounts use SQL fixed-precision `Numeric`; calculations convert source values to `Decimal` and round to cents.

## Implemented flow

Cashier records a receipt → receipt allocations are recorded → authorized cashier/finance staff reconciles it → matching effective rule creates immutable commission ledger rows → doctor requests an amount against available ledger balance → finance approves or rejects → finance records actual payout evidence → reports and statements reconcile to the ledger.

Receipt, refund, rule, adjustment, settlement, approval/rejection, and payout events are retained separately with idempotency keys and audit records. SQLite financial writes use `BEGIN IMMEDIATE` to serialize concurrent payment and reservation changes. Unique keys prevent a repeated payment reference, commission generation, settlement request, refund, or payout from being counted twice.

## Explicit defaults and scope

- There is **no default commission rule**. Finance must add and authorize an effective-dated rule before any commission accrues.
- A rule can scope by doctor, department, and/or invoice service type. The most specific matching rule wins; if specificity ties, the latest effective start date and rule ID win.
- Commission is calculated only after reconciliation. Receipts still awaiting reconciliation appear as an estimate and are not available for settlement. An existing aggregate invoice balance is not treated as proof of a verified payment and is not backfilled into the commission ledger.
- Discounts are distributed proportionally across an invoice's line totals. A partial receipt is distributed proportionally across the remaining discounted line balances. Percentage commission uses that collected net line amount. Fixed-per-service commission accrues proportionally as the line is collected.
- Invoice lines are attributed to the linked encounter doctor or inpatient attending doctor. If the hospital later needs multiple providers on one invoice, the billing schema needs explicit provider allocations first.
- The current invoice schema has no tax field, so there is no separate tax exclusion calculation. Rule scopes explicitly control whether consultation, lab, bed, pharmacy, or procedure lines qualify.
- Refunds create negative ledger entries in the refund month. Finance adjustments can be positive or negative and require a reason. Payout recording is manual: an authorized finance user records the confirmed payment method, unique reference, and verification evidence. Approval alone never marks a request paid.
- Reporting periods use `HMS_TIMEZONE`, defaulting to `Asia/Kolkata`. Collection rules use the local date of the recorded receipt; payouts and refunds retain their local reporting period.
- The existing application is single-hospital, so this implementation follows its single SQLite database boundary. It does not add cross-hospital data.

## Screens and API

- Doctors use the commission panel on `/doctor` for monthly earned, pending-reconciliation estimate, available, reserved, approved/unpaid, paid, reversals, transaction drill-down, charting, settlement requests, request history, and CSV statements. Doctor APIs always scope financial rows to the signed-in doctor.
- Finance administrators use the commission panel on `/admin` to create/deactivate rule versions, reconcile cashier receipts, review/approve/reject requests, record payouts, add audited adjustments, view charts and audit history, and download a monthly CSV report.
- Cashiers can reconcile receipts from the queue on `/billing` after verifying receipt evidence.
- API routes are under `/api/commissions`; cashier payment receipts, reconciliation, and authorized refunds are under `/api/billing`.

## Data preservation and verification

The schema change adds tables and indexes without altering or rewriting existing invoice/patient tables. Before implementation, the existing `hospital.db` was copied to `hospital.db.before_commissions.bak`. Application startup creates missing finance tables and leaves existing rows intact. The automated test suite points to a unique temporary SQLite database through `HMS_DATABASE_URL`, so tests do not drop the operational database.

Checks run during implementation:

- `python3 -m pytest -q` — all tests passed (14 tests at the time of the combined run).
- `python3 -m compileall -q app tests` — passed using a temporary bytecode cache.
- `node --check static/js/commission.js` — passed.

The tests cover partial receipts, discount allocation, pending versus reconciled eligibility, duplicate retries, effective-dated rules, refund reversals, available-balance enforcement, doctor isolation, concurrent reservations, rejection release, approval versus actual payout, payout retry protection, adjustments, exports, and rendered commission screens.
