import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import option_chain, health, insights, replay, quant, edge_lab, research, signals, manual_decisions, observation_log
from app.db.session import engine, Base
from app.db import models  # Import models to ensure they are registered
from app.engine.crawler import start_crawler_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run database migrations
    from app.db.migrate import run_migrations
    run_migrations()
    
    # Start background options crawler loop
    crawler_task = asyncio.create_task(start_crawler_loop())
    yield
    # Cancel crawler loop on shutdown
    crawler_task.cancel()
    try:
        await crawler_task
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title=settings.APP_NAME,
    description="Option Intelligence Platform API Layer",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration to allow local and production frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://future-market-rouge.vercel.app",
        "http://future-market-rouge.vercel.app",
        "https://january-participation-catalogs-journal.trycloudflare.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, prefix="/api", tags=["System Health"])
app.include_router(option_chain.router, prefix="/api", tags=["Option Chain Data"])
app.include_router(insights.router, prefix="/api", tags=["Market Insights"])
app.include_router(replay.router, prefix="/api", tags=["Quant Replay Engine"])
app.include_router(quant.router, prefix="/api", tags=["Quant Validation Console"])
app.include_router(edge_lab.router, prefix="/api", tags=["Edge Lab Analysis"])
app.include_router(research.router, prefix="/api", tags=["ML Research Store"])
app.include_router(signals.router, prefix="/api", tags=["Trading Signals Advisor"])
app.include_router(manual_decisions.router, prefix="/api", tags=["Manual Trader Decisions"])
app.include_router(observation_log.router, prefix="/api", tags=["Daily Observation Sheet"])

@app.get("/")
def read_root():
    return {
        "status": "active",
        "message": "Option Intelligence Platform backend is running.",
        "docs": "/docs"
    }

