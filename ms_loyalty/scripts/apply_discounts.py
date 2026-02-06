from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from ms_loyalty.app.config import Settings
from ms_loyalty.app.moysklad import MoySkladClient
from ms_loyalty.app.processor import process_document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, dest="doc_type")
    parser.add_argument("--id", required=True, dest="doc_id")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")

    client = MoySkladClient(settings)
    result = process_document(client, settings, args.doc_type, args.doc_id)
    print({
        "doc_type": args.doc_type,
        "doc_id": args.doc_id,
        "updated": result.updated,
        "reason": result.reason,
        "positions": result.updated_positions,
        "loyalty_discount_sum": result.loyalty_discount_sum,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
