"""Runs every sample message through the real model and checks the extracted
fields. Writes a Markdown table you can paste into the README.

    python run_eval.py
"""
import json
from pathlib import Path

import llm

ROOT = Path(__file__).parent
cfg = json.loads((ROOT / "prices.json").read_text(encoding="utf-8"))
samples = json.loads((ROOT / "samples.json").read_text(encoding="utf-8"))

rows, passed = [], 0
for i, s in enumerate(samples, 1):
    try:
        got = llm.extract_order(s["message"], list(cfg["products"]))
        wrong = []
        for field, exp in s["expected"].items():
            val = got.get(field)
            if field == "city" and val and exp:
                ok = val.lower() == exp.lower()
            elif field == "quantity" and val is not None and exp is not None:
                ok = float(val) == float(exp)
            else:
                ok = val == exp
            if not ok:
                wrong.append(f"{field}: expected {exp}, got {val}")
        status = "PASS" if not wrong else "FAIL"
        notes = "; ".join(wrong) or "-"
    except Exception as e:
        status, notes = "ERROR", str(e)[:80]
    passed += status == "PASS"
    msg = s["message"].replace("|", "/")
    rows.append(f"| {i} | {msg[:60]}{'...' if len(msg) > 60 else ''} | {status} | {notes} |")
    print(rows[-1])

table = "| # | Input | Result | Notes |\n|---|---|---|---|\n" + "\n".join(rows)
summary = f"\n\n**{passed}/{len(samples)} passed** with `{llm.MODEL}`.\n"
(ROOT / "eval_results.md").write_text(table + summary, encoding="utf-8")
print(summary)
