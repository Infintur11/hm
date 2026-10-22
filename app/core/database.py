from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """FastAPI Dependency for database session management."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize tables and apply additive migrations for existing databases."""
    Base.metadata.create_all(bind=engine)
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    # create_all does not add columns to tables already present. These finance
    # columns were added after the initial commission release, so migrate them
    # in place and backfill from their existing timestamps/identities.
    additions = {
        "payments": {"received_period": "VARCHAR(7)"},
        "patients": {"referred_by_doctor_id": "INTEGER"},
        "commission_rules": {
            "idempotency_key": "VARCHAR(120)",
            "require_all_patient_bills_paid": "BOOLEAN DEFAULT 1",
            "min_settlement_threshold": "FLOAT DEFAULT 0.0",
            "is_active": "BOOLEAN DEFAULT 1"
        },
        "commission_ledger": {
            "patient_id": "INTEGER",
            "invoice_id": "INTEGER",
            "invoice_item_id": "INTEGER",
            "base_amount": "FLOAT",
            "calculated_commission": "FLOAT",
            "accrued_at": "DATETIME",
            "released_at": "DATETIME",
            "governing_rule_id": "INTEGER",
            "execution_audit_log": "TEXT"
        },
        "invoices": {
            "billing_type": "VARCHAR(30) DEFAULT 'WALK_IN'",
            "corporate_client_id": "INTEGER",
            "corporate_policy_id": "VARCHAR(100)",
            "corporate_claim_amount": "FLOAT DEFAULT 0.0",
            "corporate_claim_status": "VARCHAR(30) DEFAULT 'NOT_APPLICABLE'"
        },
        "patients": {
            "billing_category": "VARCHAR(30) DEFAULT 'WALK_IN'",
            "corporate_client_id": "INTEGER",
            "corporate_policy_id": "VARCHAR(100)"
        }
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'))

        if inspector.has_table("payments"):
            rows = connection.execute(text(
                "SELECT id, received_at FROM payments WHERE received_period IS NULL OR received_period = ''"
            )).all()
            zone = ZoneInfo(settings.TIMEZONE)
            for payment_id, received_at in rows:
                stamp = received_at
                if isinstance(stamp, str):
                    stamp = datetime.fromisoformat(stamp)
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                period = stamp.astimezone(zone).strftime("%Y-%m")
                connection.execute(text(
                    "UPDATE payments SET received_period = :period WHERE id = :id"
                ), {"period": period, "id": payment_id})
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_payments_received_period ON payments (received_period)"
            ))

        if inspector.has_table("commission_rules"):
            connection.execute(text(
                "UPDATE commission_rules SET idempotency_key = 'legacy-rule-' || id "
                "WHERE idempotency_key IS NULL OR idempotency_key = ''"
            ))
            connection.execute(text(
                "UPDATE commission_rules SET is_active = active WHERE is_active IS NULL"
            ))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_commission_rule_idempotency "
                "ON commission_rules (idempotency_key)"
            ))

        if inspector.has_table("commission_ledger"):
            connection.execute(text(
                "UPDATE commission_ledger SET accrued_at = created_at WHERE accrued_at IS NULL"
            ))
            connection.execute(text(
                "UPDATE commission_ledger SET governing_rule_id = rule_id WHERE governing_rule_id IS NULL AND rule_id IS NOT NULL"
            ))
            connection.execute(text(
                "UPDATE commission_ledger SET base_amount = calculation_base WHERE base_amount IS NULL AND calculation_base IS NOT NULL"
            ))
            connection.execute(text(
                "UPDATE commission_ledger SET calculated_commission = amount WHERE calculated_commission IS NULL AND amount IS NOT NULL"
            ))
            connection.execute(text(
                "UPDATE commission_ledger SET invoice_id = (SELECT invoice_id FROM payments WHERE payments.id = commission_ledger.payment_id) "
                "WHERE invoice_id IS NULL AND payment_id IS NOT NULL"
            ))
            connection.execute(text(
                "UPDATE commission_ledger SET patient_id = (SELECT patient_id FROM invoices WHERE invoices.id = commission_ledger.invoice_id) "
                "WHERE patient_id IS NULL AND invoice_id IS NOT NULL"
            ))
            connection.execute(text(
                "UPDATE commission_ledger SET status = 'RELEASED' WHERE status = 'AVAILABLE'"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_commission_patient_id ON commission_ledger (patient_id)"
            ))
