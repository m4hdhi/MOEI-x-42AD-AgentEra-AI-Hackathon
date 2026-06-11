from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "agent": "Agent42"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}
