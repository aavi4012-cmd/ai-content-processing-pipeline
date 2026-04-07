import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api import routes
from app.db.database import engine, Base
import time
import uuid

# ── Structured Logging ───────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Application Lifespan ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup. In production, use Alembic migrations."""
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("🚀 AI Content Processing Pipeline is ready.")
    yield
    logger.info("Shutting down gracefully.")


# ── FastAPI Application ──────────────────────────────────────
app = FastAPI(
    title="AI Content Processing Pipeline",
    description=(
        "A production-grade backend service that processes raw text through an "
        "asynchronous AI/LLM enrichment pipeline using Celery, Redis, and PostgreSQL."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ──────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Tracing Middleware ───────────────────────────────
@app.middleware("http")
async def add_request_tracing(request: Request, call_next):
    """Assigns a unique request ID and logs request duration for observability."""
    request_id = str(uuid.uuid4())[:8]
    start = time.time()

    response = await call_next(request)

    duration = (time.time() - start) * 1000  # ms
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} → {response.status_code} ({duration:.1f}ms)"
    )
    response.headers["X-Request-ID"] = request_id
    return response


# ── API Routes ───────────────────────────────────────────────
app.include_router(routes.router, tags=["Pipeline"])


# ── Health Check ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint for load balancers and monitoring systems."""
    return {"status": "ok", "service": "AI Content Processing Pipeline", "version": "1.0.0"}