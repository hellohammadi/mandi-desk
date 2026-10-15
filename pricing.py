"""Deterministic order normalisation and pricing.

The LLM only *reads* the buyer message. All numbers (conversion, price,
delivery, total) are computed here in plain Python so they are never
hallucinated.
"""
from __future__ import annotations

import math

REQUIRED_FIELDS = ["product", "grade", "quantity", "city", "delivery_date"]

UNIT_ALIASES = {
    "peti": "peti", "petti": "peti", "peeti": "peti", "pети": "peti", "پیٹی": "peti",
    "crate": "peti", "crates": "peti", "box": "peti", "boxes": "peti",
    "carton": "peti", "cartons": "peti", "karton": "peti",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "کلو": "kg",
    "maund": "maund", "mann": "maund", "man": "maund", "mun": "maund", "من": "maund",
    "ton": "ton", "tons": "ton", "tonne": "ton",
}

PRODUCT_ALIASES = {
    "kinnow": "kinnow", "kino": "kinnow", "kinno": "kinnow", "kinu": "kinnow",
    "keenu": "kinnow", "kinoo": "kinnow", "کینو": "kinnow", "orange": "kinnow",
    "oranges": "kinnow", "mosambi": "mosambi", "musambi": "mosambi", "موسمی": "mosambi",
}

KG_PER_MAUND = 40
KG_PER_TON = 1000


def _clean_str(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value and value.lower() not in {"null", "none", "n/a", "unknown"} else None


def normalize_order(raw: dict, known_products: list[str]) -> dict:
    """Turn the model's JSON into a clean, predictable order dict."""
    product = _clean_str(raw.get("product"))
    if product:
        product = PRODUCT_ALIASES.get(product.lower(), product.lower())
        if product not in known_products:
            product = None

    grade = _clean_str(raw.get("grade"))
    if grade:
        grade = grade.upper().replace("GRADE", "").strip()[:1] or None
        if grade not in {"A", "B", "C"}:
            grade = None

    quantity = raw.get("quantity")
    try:
        quantity = float(quantity) if quantity not in (None, "") else None
        if quantity is not None and quantity <= 0:
            quantity = None
    except (TypeError, ValueError):
        quantity = None

    unit = _clean_str(raw.get("unit"))
    unit = UNIT_ALIASES.get(unit.lower(), None) if unit else None
    if quantity is not None and unit is None:
        unit = "peti"  # most common way buyers order

    city = _clean_str(raw.get("city"))
    order = {
        "intent": _clean_str(raw.get("intent")) or "order",
        "product": product,
        "grade": grade,
        "quantity": quantity,
        "unit": unit,
        "city": city.title() if city else None,
        "delivery_date": _clean_str(raw.get("delivery_date")),
        "buyer_name": _clean_str(raw.get("buyer_name")),
        "buyer_phone": _clean_str(raw.get("buyer_phone")),
        "language": _clean_str(raw.get("language")) or "roman_urdu",
    }
    order["missing_fields"] = [f for f in REQUIRED_FIELDS if not order[f]]
    return order


def to_peti(quantity: float, unit: str, kg_per_peti: float) -> int:
    if unit == "kg":
        petis = quantity / kg_per_peti
    elif unit == "maund":
        petis = quantity * KG_PER_MAUND / kg_per_peti
    elif unit == "ton":
        petis = quantity * KG_PER_TON / kg_per_peti
    else:
        petis = quantity
    return math.ceil(petis)


def build_quote(order: dict, cfg: dict) -> dict | None:
    """Return a price quote, or None if product/grade/quantity are missing."""
    if not (order.get("product") and order.get("grade") and order.get("quantity")):
        return None
    rate = cfg["products"][order["product"]][order["grade"]]
    petis = to_peti(order["quantity"], order["unit"], cfg["kg_per_peti"])
    city_key = (order.get("city") or "").lower()
    delivery = cfg["delivery"].get(city_key, cfg["delivery"]["default"]) if city_key else None
    subtotal = rate * petis
    return {
        "rate_per_peti": rate,
        "petis": petis,
        "subtotal": subtotal,
        "delivery": delivery,
        "total": subtotal + (delivery or 0),
        "currency": cfg.get("currency", "PKR"),
        "delivery_known": delivery is not None,
    }
