from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .logic import apply_discounts, is_document_disabled, _attr_value
from .moysklad import MoySkladClient


@dataclass
class ProcessResult:
    updated: bool
    reason: str
    updated_positions: int
    loyalty_discount_sum: int


def _get_attr_value(entity: dict[str, Any], name: str) -> Any:
    return _attr_value(entity, name)


def _positions_from_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    positions = document.get("positions", {}).get("rows") if isinstance(document.get("positions"), dict) else document.get("positions")
    return positions or []


def _enrich_assortments(client: MoySkladClient, positions: list[dict[str, Any]]) -> None:
    cache: dict[str, dict[str, Any]] = {}
    for pos in positions:
        assortment = pos.get("assortment") or {}
        if not isinstance(assortment, dict):
            continue
        meta = assortment.get("meta")
        href = meta.get("href") if isinstance(meta, dict) else None
        if not href:
            continue
        if assortment.get("attributes") is not None or assortment.get("tags") is not None:
            continue
        if href in cache:
            pos["assortment"] = cache[href]
            continue
        try:
            full = client.get_by_href(href)
            cache[href] = full
            pos["assortment"] = full
        except Exception as exc:
            logging.warning("Failed to enrich assortment %s: %s", href, exc)


def process_document(client: MoySkladClient, settings: Settings, doc_type: str, doc_id: str) -> ProcessResult:
    document = client.get_document(doc_type, doc_id, expand="agent,positions.assortment")

    if is_document_disabled(document, settings):
        return ProcessResult(updated=False, reason="disabled", updated_positions=0, loyalty_discount_sum=0)

    positions = _positions_from_document(document)
    if (settings.promo_attr or settings.promo_tag) and positions:
        _enrich_assortments(client, positions)

    result = apply_discounts(document, settings)

    payload: dict[str, Any] = {}
    if result.updated_positions:
        payload["positions"] = result.updated_positions

    current_sum = _get_attr_value(document, settings.loyalty_discount_sum_attr)
    if current_sum is None or int(current_sum) != int(result.loyalty_discount_sum):
        try:
            attr = client.make_attribute(doc_type, settings.loyalty_discount_sum_attr, result.loyalty_discount_sum)
            payload.setdefault("attributes", []).append(attr)
        except Exception as exc:
            logging.warning("Cannot update attribute '%s' on %s: %s", settings.loyalty_discount_sum_attr, doc_type, exc)

    if not payload:
        return ProcessResult(updated=False, reason="no_changes", updated_positions=0, loyalty_discount_sum=result.loyalty_discount_sum)

    if settings.dry_run:
        logging.info("Dry run: would update %s %s with %s", doc_type, doc_id, payload)
        return ProcessResult(updated=False, reason="dry_run", updated_positions=len(result.updated_positions), loyalty_discount_sum=result.loyalty_discount_sum)

    client.update_document(doc_type, doc_id, payload)
    return ProcessResult(updated=True, reason="updated", updated_positions=len(result.updated_positions), loyalty_discount_sum=result.loyalty_discount_sum)
