from __future__ import annotations

import argparse
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from ms_loyalty.app.config import Settings
from ms_loyalty.app.moysklad import MoySkladClient
from ms_loyalty.app.logic import apply_discounts, _attr_value


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _format_filter(dt_from: datetime, dt_to: datetime) -> str:
    from_str = dt_from.strftime("%Y-%m-%d %H:%M:%S")
    to_str = dt_to.strftime("%Y-%m-%d %H:%M:%S")
    return f"moment>={from_str};moment<={to_str}"


def _fetch_documents(client: MoySkladClient, doc_type: str, dt_from: datetime, dt_to: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 1000
    params = {
        "filter": _format_filter(dt_from, dt_to),
        "limit": limit,
        "offset": offset,
        "expand": "agent",
    }
    while True:
        params["offset"] = offset
        data = client.request("GET", f"/entity/{doc_type}", params=params)
        chunk = data.get("rows", []) or []
        rows.extend(chunk)
        if len(chunk) < limit:
            break
        offset += limit
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", required=True)
    parser.add_argument("--to", dest="date_to", required=True)
    parser.add_argument("--out", dest="out", required=True)
    parser.add_argument("--recalc", action="store_true", help="recalculate loyalty discount from positions")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")

    dt_from = datetime.combine(_parse_date(args.date_from).date(), time.min)
    dt_to = datetime.combine(_parse_date(args.date_to).date(), time.max)

    client = MoySkladClient(settings)

    report_rows: list[dict[str, Any]] = []
    for doc_type in settings.document_types:
        documents = _fetch_documents(client, doc_type, dt_from, dt_to)
        for doc in documents:
            counterparty = (doc.get("agent") or {}).get("name", "")
            total_sum = doc.get("sum", 0)
            loyalty_sum = _attr_value(doc, settings.loyalty_discount_sum_attr)
            if loyalty_sum is None and args.recalc:
                full_doc = client.get_document(doc_type, doc.get("id"), expand="agent,positions.assortment")
                res = apply_discounts(full_doc, settings)
                loyalty_sum = res.loyalty_discount_sum
            if loyalty_sum is None:
                loyalty_sum = 0

            report_rows.append({
                "documentType": doc_type,
                "documentId": doc.get("id"),
                "moment": doc.get("moment"),
                "counterparty": counterparty,
                "sum": total_sum,
                "loyaltyDiscountSum": int(loyalty_sum),
            })

    df = pd.DataFrame(report_rows)
    df.to_excel(args.out, index=False)
    print(f"Saved {len(df)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
