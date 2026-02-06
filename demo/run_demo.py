from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ms_loyalty.app.config import Settings
from ms_loyalty.app.logic import apply_discounts, is_document_disabled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        default="document.json",
        help="JSON file in demo folder (default: document.json)",
    )
    args = parser.parse_args()

    doc_path = Path(__file__).with_name(args.file)
    document = json.loads(doc_path.read_text(encoding="utf-8-sig"))

    settings = Settings.from_env()

    if is_document_disabled(document, settings):
        print("Document has DisableLoyalty=true; discounts will not be applied by processor.")

    result = apply_discounts(document, settings)

    print("Updated positions:")
    for pos in result.updated_positions:
        print(pos)

    print("Loyalty discount sum:", result.loyalty_discount_sum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
