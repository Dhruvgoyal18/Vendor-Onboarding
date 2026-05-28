import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import get_settings
from app.database import Base, engine, get_db
from app.api.auth import router as auth_router
from app.api.submissions import router as submissions_router
from app.api.dashboard import router as dashboard_router
from app.services.storage_service import ensure_bucket_exists

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Vendor Onboarding API...")
    # Create all tables on startup
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    # Ensure Supabase Storage bucket exists
    ensure_bucket_exists()

    # Recovery: mark orphaned 'processing' vendors as 'error'
    # These are submissions where the background task was lost (server restart).
    try:
        from app.models import Vendor, PipelineStageLog, SubmissionStatus, StageStatus
        from sqlalchemy.orm import Session
        db: Session = next(get_db())
        stuck = db.query(Vendor).filter(Vendor.status == SubmissionStatus.processing).all()
        recovered = 0
        for v in stuck:
            # Check if ANY stage has started running
            running_or_done = (
                db.query(PipelineStageLog)
                .filter(
                    PipelineStageLog.vendor_id == v.id,
                    PipelineStageLog.status.in_([StageStatus.running, StageStatus.completed])
                )
                .count()
            )
            if running_or_done == 0:
                # Fully orphaned — nothing ever started
                v.status = SubmissionStatus.error
                v.updated_at = datetime.utcnow()
                recovered += 1
        if recovered:
            db.commit()
            logger.warning(f"Recovered {recovered} orphaned vendor(s) → marked as error")
        db.close()
    except Exception as e:
        logger.error(f"Startup recovery failed (non-fatal): {e}")

    yield
    logger.info("Shutting down Vendor Onboarding API...")



app = FastAPI(
    title="Vendor Onboarding API",
    description="""
## AI-Powered Vendor Onboarding & Validation

This API orchestrates a **12-stage validation pipeline** for vendor onboarding:

1. **Intake** — receive submission, detect duplicates
2. **Extract Fields** — normalize form data
3. **Format Check (Layer 1)** — deterministic PAN/GSTIN/CIN/IFSC format validation (India)
4. **Extract Docs** — OCR + LLM extraction from PDFs
5. **Cross-Doc Check (Layer 3)** — compare extracted doc data against each other
6. **Merge** — consolidate all data sources
7. **Completeness Check** — ensure all required fields and documents are present
8. **Consistency Analysis** — form vs document data cross-check
9. **Credibility Analysis** — fraud signal detection via LLM
10. **Decision** — deterministic rules engine (approved / pending / rejected)
11. **Output** — generate summary, send emails
12. **Done** — pipeline complete

### Authentication
- **Admin** endpoints require `Authorization: Bearer <admin_access_token>`
- **Vendor** endpoints require `Authorization: Bearer <vendor_access_token>`
- Tokens are obtained via `/api/auth/admin/login` or `/api/auth/vendor/login`
- Access tokens expire in **15 minutes**; refresh via `/api/auth/{role}/refresh`

### Real-time Updates
Subscribe to `GET /api/submissions/{run_id}/events` for Server-Sent Events (SSE)
as each pipeline stage completes.
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "auth", "description": "Authentication — login, token refresh, logout"},
        {"name": "submissions", "description": "Vendor submission lifecycle — create, status, SSE stream"},
        {"name": "admin", "description": "Admin-only operations — dashboard, override, retry"},
        {"name": "dashboard", "description": "Admin dashboard statistics and submission history"},
    ],
)

# CORS configuration
origins = [
    settings.frontend_url,
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(submissions_router)
app.include_router(dashboard_router)


@app.get("/")
def health():
    return {"status": "healthy", "service": "Vendor Onboarding API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    for path in schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
