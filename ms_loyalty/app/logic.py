from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .config import Settings


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# counterparty checks
# ---------------------------------------------------------------------------

def is_wholesaler(counterparty: dict[str, Any], settings: Settings) -> bool:
    """Counterparty has the 'Оптовик' tag (группа контрагентов).

    MoySklad lowercases tags, so the comparison is case-insensitive.
    """
    tags = counterparty.get("tags", []) or []
    target = settings.wholesaler_tag.lower()
    return any(t.lower() == target for t in tags)


def get_loyalty_discount_percent(counterparty: dict[str, Any], settings: Settings) -> Decimal:
    """Return loyalty discount % for a counterparty.

    Conditions (ALL must be true):
      1. Custom-field checkbox  «Программа лояльности» == True
      2. Counterparty tag «Оптовик» present
      3. Custom-field «Скидка по ПЛ (%)» > 0
    """
    enabled = _to_bool(_attr_value(counterparty, settings.loyalty_enabled_attr))
    if enabled is not True:
        return Decimal("0")

    if not is_wholesaler(counterparty, settings):
        return Decimal("0")

    discount = _to_decimal(_attr_value(counterparty, settings.loyalty_discount_attr)) or Decimal("0")
    if discount <= 0:
        return Decimal("0")
    if discount > 100:
        return Decimal("100")
    return discount


# ---------------------------------------------------------------------------
# promo detection — by product folder (группа товаров «Акция»)
# ---------------------------------------------------------------------------

def is_promo_product(assortment: dict[str, Any], settings: Settings) -> bool:
    """Product is promotional if it sits in the «Акция» product-folder.

    We use the ``pathName`` field that MoySklad returns on every product /
    variant.  ``pathName`` looks like ``"Основная/Акция"`` — a ``/``-separated
    list of folder names from root to the product's direct parent folder.
    """
    if not assortment or not settings.promo_group_name:
        return False

    path_name = assortment.get("pathName", "")
    if not path_name:
        return False

    segments = [s.strip() for s in path_name.split("/") if s.strip()]
    return settings.promo_group_name in segments


# ---------------------------------------------------------------------------
# position payload builder
# ---------------------------------------------------------------------------

def _calc_discount_amount(price: Any, quantity: Any, discount_percent: Decimal) -> int:
    """Discount amount in the same units as *price* (kopecks)."""
    price_d = _to_decimal(price) or Decimal("0")
    qty_d = _to_decimal(quantity) or Decimal("0")
    amount = price_d * qty_d * discount_percent / Decimal("100")
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def build_position_update(position: dict[str, Any], discount: Decimal) -> dict[str, Any]:
    """Build a minimal position payload suitable for a document PUT.

    Includes ``id`` so MoySklad matches it to the existing position,
    and wraps ``assortment`` as ``{"meta": ...}`` as the API requires.
    """
    assortment = position.get("assortment") or {}
    assortment_meta = assortment.get("meta") if isinstance(assortment, dict) else None

    payload: dict[str, Any] = {
        "id": position.get("id"),
        "quantity": position.get("quantity"),
        "price": position.get("price"),
        "discount": float(discount),
    }

    if assortment_meta:
        payload["assortment"] = {"meta": assortment_meta}

    for field in ("vat", "vatEnabled", "pack", "reserve"):
        if position.get(field) is not None:
            payload[field] = position[field]

    return payload


# ---------------------------------------------------------------------------
# main entry-point
# ---------------------------------------------------------------------------

@dataclass
class DiscountResult:
    all_positions: list[dict[str, Any]]   # payloads for ALL positions (for PUT)
    changed_count: int                     # how many actually changed
    loyalty_discount_sum: int              # total discount in kopecks


def apply_discounts(document: dict[str, Any], settings: Settings) -> DiscountResult:
    """Calculate loyalty discounts for every position in *document*.

    Returns payloads for **all** positions (not only changed ones) because
    MoySklad replaces the entire positions list on PUT — omitting a position
    would delete it.
    """
    # positions may already be a flat list (set by processor) or nested
    raw = document.get("positions")
    if isinstance(raw, dict):
        positions = raw.get("rows") or []
    elif isinstance(raw, list):
        positions = raw
    else:
        positions = []

    counterparty = document.get("agent") or {}
    discount_percent = get_loyalty_discount_percent(counterparty, settings)

    all_positions: list[dict[str, Any]] = []
    changed_count = 0
    discount_sum = 0

    for pos in positions:
        assortment = pos.get("assortment") or {}
        is_promo = is_promo_product(assortment, settings)
        current_discount = _to_decimal(pos.get("discount")) or Decimal("0")

        if discount_percent <= 0 or is_promo:
            target_discount = Decimal("0")
        else:
            target_discount = discount_percent

        if target_discount > 0:
            discount_sum += _calc_discount_amount(
                pos.get("price"), pos.get("quantity"), target_discount,
            )

        if current_discount != target_discount:
            changed_count += 1

        all_positions.append(build_position_update(pos, target_discount))

    return DiscountResult(
        all_positions=all_positions,
        changed_count=changed_count,
        loyalty_discount_sum=discount_sum,
    )
