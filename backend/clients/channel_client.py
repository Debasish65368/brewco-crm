import httpx

from core.config import CHANNEL_SERVICE_URL, CRM_RECEIPT_URL


async def send_to_channel_service(
    campaign_id: int,
    customer_id: int,
    channel: str,
    message: str
):
    payload = {
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "channel": channel,
        "message": message,
        "receipt_url": CRM_RECEIPT_URL
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                CHANNEL_SERVICE_URL,
                json=payload,
                timeout=30
            )
        except Exception as e:
            print(f"Channel Service Error: {str(e)}")
