import inspect
import httpx

from core.config import CHANNEL_SERVICE_URL, CHANNEL_SERVICE_SECRET


async def send_to_channel_service(
    campaign_id: int,
    customer_id: int,
    channel: str,
    message: str
) -> bool:
    """
    Dispatch a single message to the external channel service.

    Returns True if the channel service accepted the request (HTTP 2xx).
    Returns False on HTTP errors (4xx, 5xx), timeouts, connection failures,
    or missing configuration. Never treats failures as success.

    Preserves authentication header 'X-Channel-Service-Key'.
    Does not log secrets, headers, customer message content, or PII.
    """
    if not CHANNEL_SERVICE_SECRET:
        print(f"[CHANNEL CLIENT ERROR] CHANNEL_SERVICE_SECRET is not configured. Refusing dispatch for campaign {campaign_id}.")
        return False

    if not CHANNEL_SERVICE_URL:
        print(f"[CHANNEL CLIENT ERROR] CHANNEL_SERVICE_URL is not configured. Refusing dispatch for campaign {campaign_id}.")
        return False

    payload = {
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "channel": channel,
        "message": message
    }

    headers = {
        "X-Channel-Service-Key": CHANNEL_SERVICE_SECRET
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                CHANNEL_SERVICE_URL,
                json=payload,
                headers=headers,
                timeout=30
            )
            res = response.raise_for_status()
            if inspect.isawaitable(res):
                await res
            return True
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        print(f"[CHANNEL CLIENT ERROR] Dispatch rejected with HTTP {status} for campaign={campaign_id}, customer={customer_id}")
        return False
    except httpx.RequestError as e:
        print(f"[CHANNEL CLIENT ERROR] Network/timeout error ({type(e).__name__}) for campaign={campaign_id}, customer={customer_id}")
        return False
    except Exception as e:
        print(f"[CHANNEL CLIENT ERROR] Unexpected error ({type(e).__name__}) for campaign={campaign_id}, customer={customer_id}")
        return False
