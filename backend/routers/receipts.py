from fastapi import APIRouter, HTTPException, Header
import hmac

from core.database import get_connection, release_connection
from core.config import CHANNEL_SERVICE_SECRET
from schemas import CommunicationReceipt

router = APIRouter(tags=["receipts"])


@router.post("/receipt")
async def receive_receipt(
    payload: CommunicationReceipt,
    x_channel_service_key: str = Header(None)
):
    if not CHANNEL_SERVICE_SECRET:
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing secret")
    if not x_channel_service_key:
        raise HTTPException(status_code=401, detail="Missing credential")
    if not hmac.compare_digest(x_channel_service_key, CHANNEL_SERVICE_SECRET):
        raise HTTPException(status_code=403, detail="Invalid credential")

    conn = await get_connection()
    try:
        status = payload.status.lower()
        if status == "delivered":
            await conn.execute(
                "UPDATE communications SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        elif status == "failed":
            await conn.execute(
                "UPDATE communications SET status = 'failed' WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        elif status == "opened":
            await conn.execute(
                "UPDATE communications SET status = 'opened', opened_at = CURRENT_TIMESTAMP WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        elif status == "clicked":
            await conn.execute(
                "UPDATE communications SET status = 'clicked', clicked_at = CURRENT_TIMESTAMP WHERE campaign_id = $1 AND customer_id = $2",
                payload.campaign_id, payload.customer_id
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid status")

        return {"success": True, "campaign_id": payload.campaign_id, "customer_id": payload.customer_id, "status": status}
    finally:
        await release_connection(conn)
