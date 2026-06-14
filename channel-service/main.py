
import asyncio
import random
from typing import Optional

import httpx

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# =====================================================
# FASTAPI APP
# =====================================================

app = FastAPI(
    title="BrewCo Channel Service",
    version="1.0.0"
)


# =====================================================
# CORS
# =====================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# REQUEST MODEL
# =====================================================

class SendRequest(BaseModel):
    campaign_id: int
    customer_id: int
    channel: str
    message: str
    receipt_url: str


# =====================================================
# CALLBACK HELPER
# =====================================================

async def send_receipt(
    receipt_url: str,
    campaign_id: int,
    customer_id: int,
    status: str
):

    payload = {
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "status": status
    }

    try:

        async with httpx.AsyncClient() as client:

            response = await client.post(
                receipt_url,
                json=payload,
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
    message: str,
    receipt_url: str
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
            receipt_url=receipt_url,
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
        receipt_url=receipt_url,
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
        receipt_url=receipt_url,
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
        receipt_url=receipt_url,
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

@app.post("/send")
async def send_message(
    payload: SendRequest,
    background_tasks: BackgroundTasks
):

    background_tasks.add_task(
        simulate_message_lifecycle,
        payload.campaign_id,
        payload.customer_id,
        payload.channel,
        payload.message,
        payload.receipt_url
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
# HEALTH
# =====================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy"
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
