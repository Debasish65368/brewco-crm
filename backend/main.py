from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import lifespan
from routers import customers, orders, segments, campaigns, receipts, dashboard, ai, root, analytics

app = FastAPI(
    title="BrewCo CRM",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(root.router)
app.include_router(customers.router)
app.include_router(orders.router)
app.include_router(segments.router)
app.include_router(campaigns.router)
app.include_router(receipts.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(analytics.router)
