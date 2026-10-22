from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
from app.core.config import settings
from app.seed import seed_database
from app.api import auth, patients, appointments, clinical, inpatient, lab, pharmacy, billing, commissions, corporate
from app.web import routes
from app.models import commission as commission_models  # register additive finance tables
from app.models import corporate as corporate_models    # register corporate & kpi tables

BASE_DIR = Path(__file__).resolve().parent.parent

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes tables and seeds master data if empty."""
    seed_database()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise Hospital Management System with Closed-Loop Pharmacy, SOAP EHR, and Minimalist HCI Design",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Mount Static Assets
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Mount API Routers
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(clinical.router)
app.include_router(inpatient.router)
app.include_router(lab.router)
app.include_router(pharmacy.router)
app.include_router(billing.router)
app.include_router(commissions.router)
app.include_router(corporate.router)

# Mount Web View Router
app.include_router(routes.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Clean error handler providing clear feedback without leaking stack traces."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc) if settings.DEBUG else "An unexpected error occurred. Please contact hospital IT."}
        )
    raise exc
