import json
import os
from datetime import datetime, timezone
import requests

BASE = "https://stg-risk.mcwchat.com"
DEPOSIT_PAGE = f"{BASE}/admin/dashboard-summary-deposit"
WITHDRAWAL_PAGE = f"{BASE}/admin/dashboard-summary-withdrawal"
DEPOSIT_API = f"{DEPOSIT_PAGE}/filter"
WITHDRAWAL_API = f"{WITHDRAWAL_PAGE}/filter"

MCW_CODES = ["M1", "B1", "K1", "M2", "B2", "B4", "B3", "TK", "B5", "JY"]
CX_CODES = ["CX", "MB", "MP", "JBG", "DZP", "SB", "SLB", "JWAY", "BJD", "KVP", "HBJ"]
ALL_CODES = MCW_CODES + CX_CODES

PAYLOAD = {"currency": "BDT", "mainBrand": None, "brand": None}


def to_number(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return 0


def fetch_api(page_url, api_url):
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": BASE,
        "Referer": page_url,
        "User-Agent": "Mozilla/5.0"
    })

    s.get(page_url, timeout=30)
    r = s.post(api_url, json=PAYLOAD, timeout=30)
    print(api_url, r.status_code)
    r.raise_for_status()
    return r.json().get("data", {})


def latest_non_zero_point(date_hour_data, prefix):
    best = None

    for date, hours in date_hour_data.items():
        for hour, values in hours.items():
            amount = to_number(values.get(f"{prefix}_amount"))
            count = to_number(values.get(f"{prefix}_count"))
            diff = to_number(values.get(f"{prefix}_difference"))

            if amount <= 0 and count <= 0:
                continue

            key = f"{date} {hour}"
            if best is None or key > best["key"]:
                best = {
                    "key": key,
                    "date": date,
                    "hour": hour,
                    "count": count,
                    "amount": amount,
                    "difference": diff
                }

    return best or {"count": 0, "amount": 0, "difference": 0, "date": None, "hour": None}


def build_latest():
    deposit_data = fetch_api(DEPOSIT_PAGE, DEPOSIT_API)
    withdrawal_data = fetch_api(WITHDRAWAL_PAGE, WITHDRAWAL_API)

    brands = {}

    for code in ALL_CODES:
        group = "MCW" if code in MCW_CODES else "CX"

        dep = latest_non_zero_point(deposit_data.get(code, {}), "deposit")
        wd = latest_non_zero_point(withdrawal_data.get(code, {}), "withdrawal")

        dep_amount = dep["amount"]
        wd_amount = wd["amount"]

        brands[code] = {
            "group": group,
            "deposit_count": dep["count"],
            "deposit_amount": dep_amount,
            "deposit_difference": dep["difference"],
            "deposit_time": dep["hour"],
            "withdrawal_count": wd["count"],
            "withdrawal_amount": wd_amount,
            "withdrawal_difference": wd["difference"],
            "withdrawal_time": wd["hour"],
            "net_flow": dep_amount - wd_amount,
            "withdrawal_pressure": (wd_amount / dep_amount * 100) if dep_amount else 0
        }

    group_totals = {}
    for group in ["MCW", "CX"]:
        rows = [v for v in brands.values() if v["group"] == group]
        dep_amount = sum(x["deposit_amount"] for x in rows)
        wd_amount = sum(x["withdrawal_amount"] for x in rows)

        group_totals[group] = {
            "deposit_count": sum(x["deposit_count"] for x in rows),
            "deposit_amount": dep_amount,
            "deposit_difference": sum(x["deposit_difference"] for x in rows),
            "withdrawal_count": sum(x["withdrawal_count"] for x in rows),
            "withdrawal_amount": wd_amount,
            "withdrawal_difference": sum(x["withdrawal_difference"] for x in rows),
            "net_flow": dep_amount - wd_amount,
            "withdrawal_pressure": (wd_amount / dep_amount * 100) if dep_amount else 0
        }

    return {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "deposit_url": DEPOSIT_API,
            "withdrawal_url": WITHDRAWAL_API
        },
        "brands": brands,
        "group_totals": group_totals,
        "comparison": {
            "m1_vs_cx": {"M1": brands["M1"], "CX": brands["CX"]},
            "mcw_vs_cx_total": {"MCW": group_totals["MCW"], "CX": group_totals["CX"]}
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
    print("M1:", latest["brands"]["M1"])
    print("CX:", latest["brands"]["CX"])
    print("Group totals:", latest["group_totals"])


if __name__ == "__main__":
    main()
