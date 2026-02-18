from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .logic import apply_discounts
from .moysklad import MoySkladClient


@dataclass
class ProcessResult:
    updated: bool
    reason: str
    updated_positions: int
    loyalty_discount_sum: int


# ------------------------------------------------------------------
# enrichment — resolve pathName for promo-folder detection
# ------------------------------------------------------------------

def _enrich_assortments(client: MoySkladClient, positions: list[dict[str, Any]]) -> None:
    """Ensure every position's assortment has ``pathName``.

    If the expanded assortment already contains ``pathName`` we skip it.
    For variants whose response lacks ``pathName`` we resolve it via the
    parent product.
    """
    cache: dict[str, dict[str, Any]] = {}

    for pos in positions:
        assortment = pos.get("assortment") or {}
        if not isinstance(assortment, dict):
            continue
        if assortment.get("pathName") is not None:
            continue

        meta = assortment.get("meta")
        href = meta.get("href") if isinstance(meta, dict) else None
        if not href:
            continue

        if href in cache:
            pos["assortment"] = cache[href]
            continue

        try:
            full = client.get_by_href(href)

            # variants don't carry pathName — resolve through parent product
            assortment_type = (meta.get("type") or "").lower()
            if assortment_type == "variant" and not full.get("pathName"):
                product_href = ((full.get("product") or {}).get("meta") or {}).get("href")
                if product_href:
                    product_data = client.get_by_href(product_href)
                    full["pathName"] = product_data.get("pathName", "")

            cache[href] = full
            pos["assortment"] = full
        except Exception as exc:
            logging.warning("Failed to enrich assortment %s: %s", href, exc)


# ------------------------------------------------------------------
# main processor
# ------------------------------------------------------------------

def process_document(
    client: MoySkladClient,
    settings: Settings,
    doc_type: str,
    doc_id: str,
) -> ProcessResult:
    logging.info("Processing %s %s", doc_type, doc_id)

    # 1. fetch document (with counterparty expanded)
    document = client.get_document(doc_type, doc_id, expand="agent")

    # 2. fetch ALL positions with assortment expanded (handles pagination)
    positions = client.get_all_positions(doc_type, doc_id, expand="assortment")

    # 3. enrich positions that lack pathName (needed for promo detection)
    if positions:
        _enrich_assortments(client, positions)

    # inject flat list into document so apply_discounts can read it
    document["positions"] = positions

    # 4. calculate discounts
    result = apply_discounts(document, settings)

    if result.changed_count == 0:
        logging.info("No discount changes needed for %s %s", doc_type, doc_id)
        return ProcessResult(
            updated=False,
            reason="no_changes",
            updated_positions=0,
            loyalty_discount_sum=result.loyalty_discount_sum,
        )

    if settings.dry_run:
        logging.info(
            "Dry run: would update %d positions in %s %s (discount sum: %d)",
            result.changed_count, doc_type, doc_id, result.loyalty_discount_sum,
        )
        return ProcessResult(
            updated=False,
            reason="dry_run",
            updated_positions=result.changed_count,
            loyalty_discount_sum=result.loyalty_discount_sum,
        )

    # 5. PUT document with ALL positions to avoid deleting unchanged ones
    payload: dict[str, Any] = {"positions": result.all_positions}
    client.update_document(doc_type, doc_id, payload)

    logging.info(
        "Updated %d positions in %s %s (discount sum: %d)",
        result.changed_count, doc_type, doc_id, result.loyalty_discount_sum,
    )
    return ProcessResult(
        updated=True,
        reason="updated",
        updated_positions=result.changed_count,
        loyalty_discount_sum=result.loyalty_discount_sum,
    )
