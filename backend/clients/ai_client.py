import json

from groq import Groq

from core.config import GROQ_API_KEY

groq_client = Groq(api_key=GROQ_API_KEY)


async def generate_segment_filter(prompt: str):
    full_prompt = f"""
You are a CRM segmentation engine.

Convert this description into JSON.

Description:
{prompt}

Return ONLY valid JSON. No markdown. No explanation.

Example:
{{"min_spent": 500, "city": "Delhi"}}

Supported fields: min_spent, max_spent, min_orders, city, last_order_before
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": full_prompt}]
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)


async def generate_campaign_message(goal: str):
    prompt = f"""
You are a marketing expert for BrewCo coffee shop.

Create a short campaign message.

Campaign Goal:
{goal}

Requirements:
- Friendly and warm
- Coffee shop tone
- Under 200 characters
- Include a call to action
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
