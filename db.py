from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "orders.db"
STATUSES = ["new", "quoted", "confirmed", "delivered", "cancelled"]


def _conn():
    return sqlite3.connect(DB_PATH)


def init():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                raw_message TEXT NOT NULL,
                product TEXT, grade TEXT, quantity REAL, unit TEXT,
                petis INTEGER, city TEXT, delivery_date TEXT,
                buyer_name TEXT, buyer_phone TEXT,
                total_pkr INTEGER, reply TEXT,
                status TEXT NOT NULL DEFAULT 'new'
            )"""
        )


def save_order(message: str, order: dict, quote: dict | None, reply: str) -> int:
    status = "quoted" if quote else "new"
    with _conn() as c:
        cur = c.execute(
            """INSERT INTO orders (created_at, raw_message, product, grade, quantity, unit,
               petis, city, delivery_date, buyer_name, buyer_phone, total_pkr, reply, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now().isoformat(timespec="seconds"), message,
                order["product"], order["grade"], order["quantity"], order["unit"],
                quote["petis"] if quote else None, order["city"], order["delivery_date"],
                order["buyer_name"], order["buyer_phone"],
                quote["total"] if quote else None, reply, status,
            ),
        )
        return cur.lastrowid


def list_orders():
    with _conn() as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM orders ORDER BY id DESC")]


def update_status(order_id: int, status: str):
    with _conn() as c:
        c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
