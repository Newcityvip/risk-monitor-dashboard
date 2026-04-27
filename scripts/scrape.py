import json
import os
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import requests

DEPOSIT_URL = "https://stg-risk.mcwchat.com/admin/dashboard-summary-deposit"
WITHDRAWAL_URL = "https://stg-risk.mcwchat.com/admin/dashboard-summary-withdrawal"

MCW_CODES = ["M1", "B1", "K1", "M2", "B2", "B4", "B3", "TK", "B5", "JY"]
CX_CODES = ["CX", "MB", "MP", "JBG", "DZP", "SB", "SLB", "JWAY", "BJD", "KVP", "HBJ"]

def to_number(value):
    if value is None:
        return 0
    text = str(value).replace(",", "").strip()
    if text == "":
        return 0
    try:
        return float(text)
    except:
        return 0

def fetch_rows(url):
    res = requests.get(url, timeout=30)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
    rows = []

    for tr in soup.select("table tr"):
        cols = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cols) >= 5:
            rows.append(cols)

    return rows

def parse_page(url, data_type):
    rows = fetch_rows(url)

    result = {
        "type": data_type,
        "brands": {},
        "totals": {
            "MCW": {"count": 0, "amount": 0, "difference": 0},
            "CX": {"count": 0, "amount": 0, "difference": 0}
        }
    }

    for row in rows:
        brand = row[0] if len(row) > 0 else ""
        code = row[1] if len(row) > 1 else ""

        if code not in MCW_CODES and code not in CX_CODES:
            continue

        count = to_number(row[2]) if len(row) > 2 else 0
        amount = to_number(row[3]) if len(row) > 3 else 0
        difference = to_number(row[4]) if len(row) > 4 else 0

        group = "MCW" if code in MCW_CODES else "CX"

        result["brands"][code] = {
            "group": group,
            "count": count,
            "amount": amount,
            "difference": difference
        }

        result["totals"][group]["count"] += count
        result["totals"][group]["amount"] += amount
        result["totals"][group]["difference"] += difference

    return result

def build_latest():
    deposit = parse_page(DEPOSIT_URL, "deposit")
    withdrawal = parse_page(WITHDRAWAL_URL, "withdrawal")

    all_codes = MCW_CODES + CX_CODES
    brands = {}

    for code in all_codes:
        dep = deposit["brands"].get(code, {})
        wd = withdrawal["brands"].get(code, {})
        group = "MCW" if code in MCW_CODES else "CX"

        dep_amount = dep.get("amount", 0)
        wd_amount = wd.get("amount", 0)

        brands[code] = {
            "group": group,
            "deposit_count": dep.get("count", 0),
            "deposit_amount": dep_amount,
            "deposit_difference": dep.get("difference", 0),
            "withdrawal_count": wd.get("count", 0),
            "withdrawal_amount": wd_amount,
            "withdrawal_difference": wd.get("difference", 0),
            "net_flow": dep_amount - wd_amount,
            "withdrawal_pressure": (wd_amount / dep_amount * 100) if dep_amount else 0
        }

    group_totals = {}
    for group in ["MCW", "CX"]:
        dep_total = deposit["totals"][group]
        wd_total = withdrawal["totals"][group]

        group_totals[group] = {
            "deposit_count": dep_total["count"],
            "deposit_amount": dep_total["amount"],
            "deposit_difference": dep_total["difference"],
            "withdrawal_count": wd_total["count"],
            "withdrawal_amount": wd_total["amount"],
            "withdrawal_difference": wd_total["difference"],
            "net_flow": dep_total["amount"] - wd_total["amount"],
            "withdrawal_pressure": (wd_total["amount"] / dep_total["amount"] * 100) if dep_total["amount"] else 0
        }

    latest = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "deposit_url": DEPOSIT_URL,
            "withdrawal_url": WITHDRAWAL_URL
        },
        "brands": brands,
        "group_totals": group_totals,
        "comparison": {
            "m1_vs_cx": {
                "M1": brands.get("M1", {}),
                "CX": brands.get("CX", {})
            },
            "mcw_vs_cx_total": {
                "MCW": group_totals["MCW"],
                "CX": group_totals["CX"]
            }
        }
    }

    return latest

def main():
    os.makedirs("data", exist_ok=True)

    latest = build_latest()

    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)

    history_path = "data/history.json"
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
            if not isinstance(history, list):
                history = []
    except:
        history = []

    history.append(latest)
    history = history[-200:]

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print("Data updated successfully")
    print("Brands found:", len(latest["brands"]))

if __name__ == "__main__":
    main()
