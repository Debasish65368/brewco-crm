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


async def generate_analytics_sql(question: str) -> str:
    prompt = f"""
You are an expert SQL assistant. Convert the following natural language question into a PostgreSQL query.

Question:
{question}

Return ONLY a single read-only SQL SELECT statement. No markdown, no explanation, no semicolons.

You are ONLY permitted to reference the following tables and columns:
- customers: id, name, email, phone, city, total_orders, total_spent, last_order_date, churn_score, cluster_id
- orders: id, customer_id, amount, created_at
- segments: id, name, customer_count, created_at
- campaigns: id, name, channel, status, created_at
- communications: campaign_id, customer_id, status

CRITICAL RULE: Never select the `email` or `phone` columns directly. You may ONLY use them inside the COUNT() function (e.g. COUNT(email)) or in WHERE clauses. Do NOT use them in STRING_AGG, ARRAY_AGG, JSON_AGG, or any other aggregate function that returns raw values. They must NEVER be returned as raw columns or strings.
CRITICAL RULE: Never use SELECT *. You must always list every column you want to return explicitly.
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lower().startswith("sql"):
            text = text[3:]
    return text.strip()


async def generate_sql_summary(question: str, data: list) -> str:
    prompt = f"""
You are a data analyst for a coffee shop CRM.

A user asked this question: "{question}"
And the database returned this data:
{json.dumps(data, default=str)}

Provide a very short, plain-English summary of what this data means (under 300 characters). Don't explain how you got it, just give the insight.
"""
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
