import json

from fastapi import APIRouter, Depends, HTTPException

from core.auth import verify_clerk_token
from schemas import SegmentSuggestionRequest, DraftMessageRequest
from clients.ai_client import generate_segment_filter, generate_campaign_message

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/suggest-segment")
async def ai_suggest_segment(
    payload: SegmentSuggestionRequest,
    user=Depends(verify_clerk_token)
):
    try:
        filter_json = await generate_segment_filter(payload.prompt)
        return {"filter_json": filter_json}
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Gemini returned invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/draft-message")
async def ai_draft_message(
    payload: DraftMessageRequest,
    user=Depends(verify_clerk_token)
):
    try:
        message = await generate_campaign_message(payload.goal)
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
