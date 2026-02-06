from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .config import Settings


def _attr_value(entity: dict[str, Any], name: str) -> Any:
    for attr in entity.get("attributes", []) or []:
        if attr.get("name") == name:
            return attr.get("value")
    return None


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except Exception:
            return None
    return None


def get_loyalty_discount_percent(counterparty: dict[str, Any], settings: Settings) -> Decimal:
    enabled_val = _attr_value(counterparty, settings.loyalty_enabled_attr)
    discount_val = _attr_value(counterparty, settings.loyalty_discount_attr)

    enabled = _to_bool(enabled_val)
    discount = _to_decimal(discount_val) or Decimal("0")

    if enabled is False:
        return Decimal("0")
    if enabled is None and discount <= 0:
        return Decimal("0")

    if discount < 0:
        return Decimal("0")
    if discount > 100:
        return Decimal("100")
    return discount


def is_document_disabled(document: dict[str, Any], settings: Settings) -> bool:
    value = _attr_value(document, settings.disable_loyalty_attr)
    return _to_bool(value) is True


def is_promo_assortment(assortment: dict[str, Any], settings: Settings) -> bool:
    if not assortment:
        return False
    attr_val = _attr_value(assortment, settings.promo_attr)
    if _to_bool(attr_val) is True:
        return True

    if settings.promo_tag:
        tags = assortment.get("tags", []) or []
        if settings.promo_tag in tags:
            return True

    return False


def _calc_discount_amount(price: Any, quantity: Any, discount_percent: Decimal) -> int:
    price_d = _to_decimal(price) or Decimal("0")
    qty_d = _to_decimal(quantity) or Decimal("0")
    amount = price_d * qty_d * discount_percent / Decimal("100")
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class DiscountResult:
    updated_positions: list[dict[str, Any]]
    loyalty_discount_sum: int


def build_position_update(position: dict[str, Any], discount: Decimal) -> dict[str, Any]:
    assortment = position.get("assortment") or {}
    assortment_meta = assortment.get("meta") if isinstance(assortment, dict) else None
    payload = {
        "id": position.get("id"),
        "quantity": position.get("quantity"),
        "price": position.get("price"),
        "discount": float(discount),
        "assortment": assortment_meta or assortment,
    }
    if position.get("vat") is not None:
        payload["vat"] = position.get("vat")
    if position.get("vatEnabled") is not None:
        payload["vatEnabled"] = position.get("vatEnabled")
    if position.get("pack") is not None:
        payload["pack"] = position.get("pack")
    if position.get("reserve") is not None:
        payload["reserve"] = position.get("reserve")
    return payload


def apply_discounts(document: dict[str, Any], settings: Settings) -> DiscountResult:
    positions = document.get("positions", {}).get("rows") if isinstance(document.get("positions"), dict) else document.get("positions")
    positions = positions or []

    counterparty = document.get("agent") or {}
    discount_percent = get_loyalty_discount_percent(counterparty, settings)

    updated: list[dict[str, Any]] = []
    discount_sum = 0

    for pos in positions:
        assortment = pos.get("assortment") or {}
        is_promo = is_promo_assortment(assortment, settings)
        current_discount = _to_decimal(pos.get("discount")) or Decimal("0")

        if discount_percent <= 0:
            target_discount = Decimal("0")
        elif is_promo:
            target_discount = Decimal("0")
        elif settings.respect_existing_discount and current_discount > 0:
            target_discount = current_discount
        else:
            target_discount = discount_percent

        if target_discount > 0 and not is_promo:
            discount_sum += _calc_discount_amount(pos.get("price"), pos.get("quantity"), target_discount)

        if current_discount != target_discount:
            updated.append(build_position_update(pos, target_discount))

    return DiscountResult(updated_positions=updated, loyalty_discount_sum=discount_sum)
