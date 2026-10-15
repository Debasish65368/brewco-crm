import asyncio
import hmac
import random
from typing import Optional
import os

import httpx
from dotenv import load_dotenv

from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel

# Load environment variables from a local .env file when present.
# In deployment (Render, Railway, etc.) variables are injected directly.
load_dotenv()

# =====================================================
# CONFIGURATION
# =====================================================

CRM_RECEIPT_URL = os.getenv("CRM_RECEIPT_URL", "http://localhost:8000/receipt")
CHANNEL_SERVICE_SECRET = os.getenv("CHANNEL_SERVICE_SECRET", "")

# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="BrewCo Channel Service",
    version="1.0.0"
)

# NOTE: No CORS middleware. This service is called only by the CRM backend
# (server-to-server). Browser CORS access is not needed or intended.
# The /send endpoint is protected by the shared-secret header check below,
# independent of any CORS policy.


# =====================================================
# REQUEST MODEL
# =====================================================

class SendRequest(BaseModel):
    campaign_id: int
    customer_id: int
    channel: str
    message: str


# =====================================================
# CALLBACK HELPER
# =====================================================

async def send_receipt(
    campaign_id: int,
    customer_id: int,
    status: str
):
    if not CRM_RECEIPT_URL or not CHANNEL_SERVICE_SECRET:
        print("[CALLBACK ERROR] Missing CRM_RECEIPT_URL or CHANNEL_SERVICE_SECRET configuration.")
        return

    payload = {
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "status": status
    }

    headers = {
        "X-Channel-Service-Key": CHANNEL_SERVICE_SECRET
    }

    try:

        async with httpx.AsyncClient() as client:

            response = await client.post(
                CRM_RECEIPT_URL,
                json=payload,
                headers=headers,
                timeout=30
            )

            print(
                f"[CALLBACK] "
                f"customer={customer_id} "
                f"status={status} "
                f"response={response.status_code}"
            )

    except Exception as e:

        print(
            f"[CALLBACK ERROR] "
            f"{str(e)}"
        )


# =====================================================
# MESSAGE DELIVERY SIMULATION
# =====================================================

async def simulate_message_lifecycle(
    campaign_id: int,
    customer_id: int,
    channel: str,
    message: str
):

    print(
        f"[SEND] "
        f"campaign={campaign_id} "
        f"customer={customer_id} "
        f"channel={channel}"
    )

    #
    # Initial delivery delay
    #

    await asyncio.sleep(
        random.randint(2, 5)
    )

    #
    # 80% Delivered
    # 20% Failed
    #

    delivered = random.random() < 0.80

    if not delivered:

        await send_receipt(
            campaign_id=campaign_id,
            customer_id=customer_id,
            status="failed"
        )

        print(
            f"[FAILED] "
            f"customer={customer_id}"
        )

        return

    #
    # Delivered
    #

    await send_receipt(
        campaign_id=campaign_id,
        customer_id=customer_id,
        status="delivered"
    )

    print(
        f"[DELIVERED] "
        f"customer={customer_id}"
    )

    #
    # Open delay
    #

    await asyncio.sleep(
        random.randint(2, 5)
    )

    #
    # 60% of delivered get opened
    #

    opened = random.random() < 0.60

    if not opened:

        print(
            f"[NOT OPENED] "
            f"customer={customer_id}"
        )

        return

    await send_receipt(
        campaign_id=campaign_id,
        customer_id=customer_id,
        status="opened"
    )

    print(
        f"[OPENED] "
        f"customer={customer_id}"
    )

    #
    # Click delay
    #

    await asyncio.sleep(
        random.randint(2, 5)
    )

    #
    # 30% of opened get clicked
    #

    clicked = random.random() < 0.30

    if not clicked:

        print(
            f"[NOT CLICKED] "
            f"customer={customer_id}"
        )

        return

    await send_receipt(
        campaign_id=campaign_id,
        customer_id=customer_id,
        status="clicked"
    )

    print(
        f"[CLICKED] "
        f"customer={customer_id}"
    )


# =====================================================
# POST /send
# =====================================================

def _verify_send_auth(x_channel_service_key: Optional[str]) -> None:
    """
    Validate the shared-secret header on /send requests.
    Fails closed: if CHANNEL_SERVICE_SECRET is not configured the endpoint
    is NOT publicly accessible — it raises 500 rather than accepting any caller.
    Uses hmac.compare_digest for constant-time comparison.
    The supplied header value is never logged.
    """
    if not CHANNEL_SERVICE_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: channel service secret not set"
        )
    if not x_channel_service_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Channel-Service-Key header"
        )
    if not hmac.compare_digest(x_channel_service_key, CHANNEL_SERVICE_SECRET):
        raise HTTPException(
            status_code=403,
            detail="Invalid X-Channel-Service-Key"
        )


@app.post("/send")
async def send_message(
    payload: SendRequest,
    background_tasks: BackgroundTasks,
    x_channel_service_key: Optional[str] = Header(None)
):
    """
    Accept an outbound message dispatch request.

    Returns HTTP 200 with status='queued' to acknowledge that the channel service
    has accepted the dispatch request. This confirms dispatch acceptance only;
    it does not guarantee or confirm delivery to the customer. Delivery confirmation
    occurs asynchronously via receipt callbacks.

    Note on Durability: The delivery lifecycle simulation runs in-process via FastAPI
    BackgroundTasks and is not durable across process restarts.
    """
    _verify_send_auth(x_channel_service_key)

    background_tasks.add_task(
        simulate_message_lifecycle,
        payload.campaign_id,
        payload.customer_id,
        payload.channel,
        payload.message
    )

    return {
        "success": True,
        "campaign_id": payload.campaign_id,
        "customer_id": payload.customer_id,
        "channel": payload.channel,
        "status": "queued"
    }


# =====================================================
# ROOT
# =====================================================

@app.get("/")
async def root():

    return {
        "service": "BrewCo Channel Service",
        "status": "running"
    }


# =====================================================
# LOCAL RUN
# =====================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
