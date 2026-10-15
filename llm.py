"""Model calls. Works with Groq (default) or a local Ollama server, because
both expose an OpenAI-compatible API. Switch with environment variables."""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import BadRequestError, OpenAI

from pricing import normalize_order

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
API_KEY = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or "ollama"
MODEL = os.getenv("MODEL_NAME", "allam-2-7b")

_client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

EXTRACT_SYSTEM = """You read messages that fruit buyers in Pakistan send to a farm.
Messages may be in Roman Urdu, Urdu script, English, or a mix.
Return ONLY a JSON object with these keys:
- intent: "order", "price_inquiry", or "other"
- product: fruit name in lowercase English (e.g. "kinnow", "mosambi") or null
- grade: "A", "B", "C" or null
- quantity: number or null (convert words like "pachas" to 50)
- unit: one of "peti", "kg", "maund", "ton" or null ("mann/man" = maund, "crate/box/carton" = peti)
- city: delivery city or null
- delivery_date: delivery time exactly as the buyer said it (e.g. "next week", "Friday") or null
- buyer_name: string or null
- buyer_phone: string or null
- language: "roman_urdu", "urdu", "english", or "mixed"
Never invent values. If something is not in the message, use null.

Example
Message: "AoA bhai 50 peti kinnow chahiye A grade, Lahore delivery agle hafte. Ahmed 0300-1234567"
JSON: {"intent":"order","product":"kinnow","grade":"A","quantity":50,"unit":"peti","city":"Lahore","delivery_date":"agle hafte","buyer_name":"Ahmed","buyer_phone":"0300-1234567","language":"roman_urdu"}
"""

REPLY_SYSTEM = """You are the polite order assistant for the fruit farm "{farm}".
Write a short WhatsApp reply to the buyer.
Rules:
- Reply in the SAME language and script the buyer used (Roman Urdu -> Roman Urdu, Urdu script -> Urdu script, English -> English).
- Use ONLY the numbers given in QUOTE. Never invent or change prices.
- If MISSING lists fields, politely ask the buyer for them.
- If there is no quote, do not mention any price; ask for the missing details instead.
- Maximum 5 short lines. No markdown."""


def _parse_json(text: str) -> dict:
    """Parse the model output as JSON, tolerating code fences or extra text."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError(f"Model did not return JSON: {text[:120]}")
        return json.loads(text[start:end + 1])


def extract_order(message: str, known_products: list[str]) -> dict:
    messages = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": f"Message: {message}\nJSON:"},
    ]
    try:  # JSON mode where the provider supports it for this model
        resp = _client.chat.completions.create(
            model=MODEL, temperature=0, response_format={"type": "json_object"}, messages=messages,
        )
    except BadRequestError:  # model without JSON mode: plain call, parse defensively
        resp = _client.chat.completions.create(model=MODEL, temperature=0, messages=messages)
    raw = _parse_json(resp.choices[0].message.content)
    return normalize_order(raw, known_products)


def draft_reply(message: str, order: dict, quote: dict | None, farm: str) -> str:
    facts = {
        "ORDER": {k: v for k, v in order.items() if k != "missing_fields"},
        "MISSING": order["missing_fields"],
        "QUOTE": quote,
    }
    resp = _client.chat.completions.create(
        model=MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": REPLY_SYSTEM.format(farm=farm)},
            {"role": "user", "content": f"Buyer message: {message}\n\nFacts:\n{json.dumps(facts, ensure_ascii=False)}"},
        ],
    )
    return resp.choices[0].message.content.strip()
