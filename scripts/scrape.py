import json
import os
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import requests

DEPOSIT_URL = "https://stg-risk.mcwchat.com/admin/dashboard-summary-deposit"
WITHDRAWAL_URL = "https://stg-risk.mcwchat.com/admin/dashboard-summary-withdrawal"

MCW_CODES = ["M1", "B1", "K1", "M2", "B2", "B4", "B3", "TK", "B5", "JY"]
CX_CODES = ["CX", "MB", "MP", "JBG", "DZP", "SB", "SLB", "JWAY", "BJD", "KVP", "HBJ"]
ALL_CODES = MCW_CODES + CX_CODES


def to_number(value):
    if value is None:
        return 0
    text = str(value).replace(",", "").strip()
    text = re.sub(r"[^\d.\-]", "", text)
    if text in ["", "-", "."]:
        return 0
    try:
        return float(text)
    except Exception:
        return 0


def fetch_rows(url):
    res = requests.get(url, timeout=30)
    res.raise_for_status()

    # If endpoint returns JSON
    try:
        data = res.json()
        return extract_rows_from_json(data)
    except Exception:
        pass

    soup = BeautifulSoup(res.text, "html.parser")
    rows = []

    for tr in soup.select("tr"):
        cols = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if cols:
            rows.append(cols)

    print(f"Fetched {len(rows)} table rows from {url}")
    for r in rows[:8]:
        print("ROW:", r)

    return rows


def extract_rows_from_json(data):
    rows = []

    def walk(obj):
        if isinstance(obj, dict):
            values = list(obj.values())
            text_values = [str(v) for v in values if isinstance(v, (str, int, float))]
            if any(v.upper() in ALL_CODES for v in text_values):
                rows.append(text_values)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
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
        clean = [str(x).strip() for x in row if str(x).strip() != ""]
        upper = [x.upper() for x in clean]

        code = ""
        for item in upper:
            if item in ALL_CODES:
                code = item
                break

        if not code:
            continue

        group = "MCW" if code in MCW_CODES else "CX"

        code_index = upper.index(code)
        after_code = clean[code_index + 1:]

        numbers = [to_number(x) for x in after_code if re.search(r"\d", str(x))]

        count = numbers[0] if len(numbers) > 0 else 0
        amount = numbers[1] if len(numbers) > 1 else 0
        difference = numbers[2] if len(numbers) > 2 else 0

        result["brands"][code] = {
            "group": group,
            "count": count,
            "amount": amount,
            "difference": difference
        }

        result["totals"][group]["count"] += count
        result["totals"][group]["amount"] += amount
        result["totals"][group]["difference"] += difference

    print(data_type.upper(), "brands parsed:", result["brands"])
    return result


def build_latest():
    deposit = parse_page(DEPOSIT_URL, "deposit")
    withdrawal = parse_page(WITHDRAWAL_URL, "withdrawal")

    brands = {}

    for code in ALL_CODES:
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

    return {
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
    except Exception:
        history = []

    history.append(latest)
    history = history[-200:]

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print("Data updated successfully")
    print("Brands found:", len(latest["brands"]))
    print("Group totals:", latest["group_totals"])


if __name__ == "__main__":
    main()
