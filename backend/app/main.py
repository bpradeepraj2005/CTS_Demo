import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "ml"),
)

from .config import CORS_ORIGINS  # noqa: E402
from .database import Base, engine  # noqa: E402
from .routers import auth, dashboard, requests, review  # noqa: E402
from .services import ml  # noqa: E402

app = FastAPI(
    title="Prior Authorization Intelligence Platform",
    description=(
        "AI-assisted prior authorization automation with PDF extraction, "
        "medical necessity evaluation, ML scoring, reviewer routing, "
        "appeal prediction and audit trails."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in CORS_ORIGINS
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(requests.router)
app.include_router(review.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def startup():

    Base.metadata.create_all(
        bind=engine
    )

    ready = ml.models_ready()

    print("\n==========================================")
    print(" PRIOR AUTHORIZATION PLATFORM")
    print("==========================================")

    print(
        "Policy-fit model:",
        "READY" if ready["policy_fit"] else "MISSING",
    )

    print(
        "Appeal model:",
        "READY" if ready["appeal_propensity"] else "MISSING",
    )

    if not all(ready.values()):
        print(
            "\nWARNING: ML model files are missing."
        )

    print("==========================================\n")


@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "service": "prior-authorization-platform",
        "models": ml.models_ready(),
    }