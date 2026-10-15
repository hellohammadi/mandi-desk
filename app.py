import json
from pathlib import Path

import streamlit as st

import db
import llm
import pricing

ROOT = Path(__file__).parent
CFG_PATH = ROOT / "prices.json"
SAMPLES = json.loads((ROOT / "samples.json").read_text(encoding="utf-8"))

st.set_page_config(page_title="Mandi Desk", page_icon="🍊", layout="wide")
db.init()
cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))

st.title("🍊 Mandi Desk")
st.caption(f"AI order desk for farmers who sell direct · model: `{llm.MODEL}`")

# ---------- Sidebar: farmer's own rate list ----------
with st.sidebar:
    st.header("Rate list (PKR / peti)")
    for product, grades in cfg["products"].items():
        st.subheader(product.title())
        for g in grades:
            grades[g] = int(st.number_input(f"Grade {g}", value=int(grades[g]), step=50, key=f"p_{product}_{g}"))
    cfg["kg_per_peti"] = st.number_input("kg per peti", value=float(cfg["kg_per_peti"]), step=0.5)
    if st.button("Save rate list"):
        CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        st.success("Saved")

tab_new, tab_book = st.tabs(["New inquiry", "Order book"])

# ---------- New inquiry ----------
with tab_new:
    options = ["(type your own)"] + [s["message"] for s in SAMPLES]
    pick = st.selectbox("Try a sample message", options)
    message = st.text_area(
        "Paste the buyer's WhatsApp message",
        value="" if pick == options[0] else pick,
        height=110,
        key=f"msg_{options.index(pick)}",
    )

    if st.button("Process message", type="primary", disabled=not message.strip()):
        try:
            with st.spinner("Reading the message..."):
                order = llm.extract_order(message, list(cfg["products"]))
                quote = pricing.build_quote(order, cfg)
            with st.spinner("Drafting a reply..."):
                reply = llm.draft_reply(message, order, quote, cfg["farm_name"])
            st.session_state.result = {"message": message, "order": order, "quote": quote, "reply": reply}
        except Exception as e:  # show the error in the demo instead of crashing
            st.error(f"Model call failed: {e}")

    res = st.session_state.get("result")
    if res:
        left, right = st.columns(2)
        with left:
            st.subheader("Extracted order")
            st.json({k: v for k, v in res["order"].items() if k != "missing_fields"})
            if res["order"]["missing_fields"]:
                st.warning("Missing: " + ", ".join(res["order"]["missing_fields"]))
        with right:
            st.subheader("Quote")
            q = res["quote"]
            if q:
                c1, c2, c3 = st.columns(3)
                c1.metric("Peti", q["petis"])
                c2.metric("Rate", f"{q['rate_per_peti']:,}")
                c3.metric("Total", f"{q['total']:,} {q['currency']}")
                if not q["delivery_known"]:
                    st.info("Delivery city unknown, so delivery is not included yet.")
            else:
                st.info("Not enough details for a quote yet.")
            st.subheader("Reply draft")
            reply = st.text_area("Edit before sending", value=res["reply"], height=150, key=f"reply_{hash(res['reply'])}")
            if st.button("Save to order book"):
                oid = db.save_order(res["message"], res["order"], res["quote"], reply)
                st.success(f"Saved as order #{oid}")
                del st.session_state.result

# ---------- Order book ----------
with tab_book:
    orders = db.list_orders()
    if not orders:
        st.info("No orders yet.")
    else:
        st.dataframe(
            [{k: o[k] for k in ("id", "created_at", "buyer_name", "product", "grade", "petis", "city",
                                "delivery_date", "total_pkr", "status")} for o in orders],
            use_container_width=True, hide_index=True,
        )
        c1, c2, c3 = st.columns([1, 1, 1])
        oid = c1.selectbox("Order #", [o["id"] for o in orders])
        status = c2.selectbox("New status", db.STATUSES)
        if c3.button("Update status"):
            db.update_status(oid, status)
            st.rerun()
