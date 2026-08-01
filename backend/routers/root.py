from fastapi import APIRouter

router = APIRouter(tags=["root"])


@router.get("/")
async def root():
    return {"service": "BrewCo CRM", "status": "running", "version": "1.0.0"}
