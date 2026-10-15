import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pricing import build_quote, normalize_order, to_peti  # noqa: E402

CFG = {
    "currency": "PKR",
    "kg_per_peti": 10,
    "products": {"kinnow": {"A": 2200, "B": 1800, "C": 1400}},
    "delivery": {"default": 1500, "lahore": 800},
}
PRODUCTS = ["kinnow"]


def test_normalize_aliases_and_missing():
    o = normalize_order({"product": "Kinno", "grade": "grade b", "quantity": "20", "unit": "mann"}, PRODUCTS)
    assert o["product"] == "kinnow"
    assert o["grade"] == "B"
    assert o["quantity"] == 20
    assert o["unit"] == "maund"
    assert o["missing_fields"] == ["city", "delivery_date"]


def test_normalize_rejects_unknown_and_nulls():
    o = normalize_order({"product": "apple", "grade": "Z", "quantity": "null", "city": "null"}, PRODUCTS)
    assert o["product"] is None and o["grade"] is None and o["quantity"] is None and o["city"] is None


def test_unit_conversion():
    assert to_peti(50, "peti", 10) == 50
    assert to_peti(500, "kg", 10) == 50
    assert to_peti(20, "maund", 10) == 80
    assert to_peti(2, "ton", 10) == 200
    assert to_peti(25, "kg", 10) == 3  # rounds up


def test_quote_with_known_city():
    o = normalize_order({"product": "kinnow", "grade": "A", "quantity": 50, "unit": "peti", "city": "lahore"}, PRODUCTS)
    q = build_quote(o, CFG)
    assert q["subtotal"] == 110_000
    assert q["delivery"] == 800
    assert q["total"] == 110_800


def test_quote_unknown_city_uses_default_and_missing_city_excluded():
    o = normalize_order({"product": "kinnow", "grade": "C", "quantity": 10, "city": "Multan"}, PRODUCTS)
    assert build_quote(o, CFG)["delivery"] == 1500
    o2 = normalize_order({"product": "kinnow", "grade": "C", "quantity": 10}, PRODUCTS)
    q2 = build_quote(o2, CFG)
    assert q2["delivery"] is None and q2["total"] == 14_000


def test_no_quote_when_details_missing():
    o = normalize_order({"product": "kinnow"}, PRODUCTS)
    assert build_quote(o, CFG) is None


def test_product_fuzzy_match():
    assert normalize_order({"product": "kinno orange"}, PRODUCTS)["product"] == "kinnow"
    assert normalize_order({"product": "Keenu (A grade)"}, PRODUCTS)["product"] == "kinnow"
    assert normalize_order({"product": "apples"}, PRODUCTS)["product"] is None
