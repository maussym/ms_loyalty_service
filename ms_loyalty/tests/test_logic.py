"""Unit-tests for the loyalty discount logic.

All tests run offline — no API calls.
"""
from decimal import Decimal

from ms_loyalty.app.config import Settings
from ms_loyalty.app.logic import (
    apply_discounts,
    get_loyalty_discount_percent,
    is_promo_product,
    is_wholesaler,
)


# ------------------------------------------------------------------
# helper to build a Settings instance with overrides
# ------------------------------------------------------------------

def _settings(**overrides) -> Settings:
    defaults = dict(
        base_url="https://api.moysklad.ru/api/remap/1.2",
        auth_mode="bearer",
        token="test-token",
        login="",
        password="",
        document_types=["customerorder", "demand"],
        loyalty_enabled_attr="Программа лояльности",
        loyalty_discount_attr="Скидка по ПЛ (%)",
        wholesaler_tag="Оптовик",
        promo_group_name="Акция",
        dry_run=False,
        log_level="DEBUG",
        webhook_bearer_token="",
        request_timeout=20,
    )
    defaults.update(overrides)
    return Settings(**defaults)


# ------------------------------------------------------------------
# counterparty — wholesaler tag
# ------------------------------------------------------------------

def test_is_wholesaler_with_tag():
    s = _settings()
    assert is_wholesaler({"tags": ["Оптовик", "VIP"]}, s) is True


def test_is_wholesaler_lowercase_tag():
    """MoySklad lowercases tags — should still match."""
    s = _settings()
    assert is_wholesaler({"tags": ["оптовик"]}, s) is True


def test_is_wholesaler_without_tag():
    s = _settings()
    assert is_wholesaler({"tags": ["Розница"]}, s) is False


def test_is_wholesaler_no_tags():
    s = _settings()
    assert is_wholesaler({}, s) is False


# ------------------------------------------------------------------
# counterparty — loyalty discount percent
# ------------------------------------------------------------------

def test_loyalty_discount_full_eligible():
    """Checkbox True + tag Оптовик + discount > 0 → returns discount."""
    s = _settings()
    agent = {
        "tags": ["Оптовик"],
        "attributes": [
            {"name": "Программа лояльности", "value": True},
            {"name": "Скидка по ПЛ (%)", "value": 7},
        ],
    }
    assert get_loyalty_discount_percent(agent, s) == Decimal("7")


def test_loyalty_discount_checkbox_false():
    s = _settings()
    agent = {
        "tags": ["Оптовик"],
        "attributes": [
            {"name": "Программа лояльности", "value": False},
            {"name": "Скидка по ПЛ (%)", "value": 7},
        ],
    }
    assert get_loyalty_discount_percent(agent, s) == Decimal("0")


def test_loyalty_discount_no_checkbox():
    s = _settings()
    agent = {
        "tags": ["Оптовик"],
        "attributes": [
            {"name": "Скидка по ПЛ (%)", "value": 7},
        ],
    }
    assert get_loyalty_discount_percent(agent, s) == Decimal("0")


def test_loyalty_discount_not_wholesaler():
    s = _settings()
    agent = {
        "tags": ["Розница"],
        "attributes": [
            {"name": "Программа лояльности", "value": True},
            {"name": "Скидка по ПЛ (%)", "value": 7},
        ],
    }
    assert get_loyalty_discount_percent(agent, s) == Decimal("0")


def test_loyalty_discount_zero_percent():
    s = _settings()
    agent = {
        "tags": ["Оптовик"],
        "attributes": [
            {"name": "Программа лояльности", "value": True},
            {"name": "Скидка по ПЛ (%)", "value": 0},
        ],
    }
    assert get_loyalty_discount_percent(agent, s) == Decimal("0")


def test_loyalty_discount_capped_at_100():
    s = _settings()
    agent = {
        "tags": ["Оптовик"],
        "attributes": [
            {"name": "Программа лояльности", "value": True},
            {"name": "Скидка по ПЛ (%)", "value": 150},
        ],
    }
    assert get_loyalty_discount_percent(agent, s) == Decimal("100")


# ------------------------------------------------------------------
# promo detection — product folder
# ------------------------------------------------------------------

def test_promo_product_in_akciya_folder():
    s = _settings()
    assert is_promo_product({"pathName": "Акция"}, s) is True


def test_promo_product_in_nested_akciya():
    s = _settings()
    assert is_promo_product({"pathName": "Основная/Акция"}, s) is True


def test_promo_product_in_subfolder_of_akciya():
    s = _settings()
    assert is_promo_product({"pathName": "Акция/Зимняя"}, s) is True


def test_non_promo_product():
    s = _settings()
    assert is_promo_product({"pathName": "Основная/Электроника"}, s) is False


def test_promo_empty_path():
    s = _settings()
    assert is_promo_product({"pathName": ""}, s) is False


def test_promo_no_path():
    s = _settings()
    assert is_promo_product({}, s) is False


def test_promo_partial_name_no_match():
    """«Неакция» should NOT match «Акция»."""
    s = _settings()
    assert is_promo_product({"pathName": "Неакция"}, s) is False


# ------------------------------------------------------------------
# apply_discounts — full document
# ------------------------------------------------------------------

def _make_document(agent, positions):
    return {"agent": agent, "positions": positions}


def _make_agent(enabled=True, discount=10, tags=None):
    if tags is None:
        tags = ["Оптовик"]
    attrs = []
    if enabled is not None:
        attrs.append({"name": "Программа лояльности", "value": enabled})
    attrs.append({"name": "Скидка по ПЛ (%)", "value": discount})
    return {"tags": tags, "attributes": attrs}


def _make_position(pos_id, price, quantity, discount=0, path_name="Основная"):
    return {
        "id": pos_id,
        "price": price,
        "quantity": quantity,
        "discount": discount,
        "assortment": {
            "meta": {"href": f"https://x/{pos_id}", "type": "product"},
            "pathName": path_name,
        },
    }


def test_apply_discount_to_regular_products():
    """10% discount applied to 2 items @ 10000 → discount_sum = 2000."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=10),
        positions=[_make_position("p1", 10000, 2)],
    )
    result = apply_discounts(doc, s)
    assert result.changed_count == 1
    assert result.all_positions[0]["discount"] == 10.0
    assert result.loyalty_discount_sum == 2000


def test_promo_product_gets_zero_discount():
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=10),
        positions=[_make_position("p1", 10000, 2, path_name="Акция")],
    )
    result = apply_discounts(doc, s)
    assert result.all_positions[0]["discount"] == 0.0
    assert result.loyalty_discount_sum == 0


def test_mixed_positions():
    """One regular + one promo → only the regular one gets the discount."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=7),
        positions=[
            _make_position("p1", 10000, 1, path_name="Основная"),
            _make_position("p2", 20000, 1, path_name="Акция"),
        ],
    )
    result = apply_discounts(doc, s)
    assert result.all_positions[0]["discount"] == 7.0
    assert result.all_positions[1]["discount"] == 0.0
    assert result.loyalty_discount_sum == 700  # 10000*1*7/100


def test_non_eligible_counterparty_zeroes_discounts():
    """If counterparty not in ПЛ, all discounts should be 0."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=False, discount=10),
        positions=[_make_position("p1", 10000, 2, discount=5)],
    )
    result = apply_discounts(doc, s)
    assert result.all_positions[0]["discount"] == 0.0
    assert result.changed_count == 1  # was 5, now 0
    assert result.loyalty_discount_sum == 0


def test_no_changes_when_already_correct():
    """If discount already equals target, changed_count should be 0."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=10),
        positions=[_make_position("p1", 10000, 2, discount=10)],
    )
    result = apply_discounts(doc, s)
    assert result.changed_count == 0
    assert result.all_positions[0]["discount"] == 10.0
    assert result.loyalty_discount_sum == 2000


def test_overwrite_manual_discount():
    """System always re-applies — overwrites manager's manual discount."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=7),
        positions=[_make_position("p1", 10000, 2, discount=15)],
    )
    result = apply_discounts(doc, s)
    assert result.changed_count == 1
    assert result.all_positions[0]["discount"] == 7.0


def test_all_positions_returned():
    """Even unchanged positions are in all_positions (to avoid deletion on PUT)."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=10),
        positions=[
            _make_position("p1", 10000, 1, discount=10),  # already correct
            _make_position("p2", 20000, 1, discount=0),   # needs change
        ],
    )
    result = apply_discounts(doc, s)
    assert len(result.all_positions) == 2
    assert result.changed_count == 1


def test_assortment_meta_wrapped():
    """Position payload should wrap assortment as {"meta": {...}}."""
    s = _settings()
    doc = _make_document(
        agent=_make_agent(enabled=True, discount=5),
        positions=[_make_position("p1", 10000, 1)],
    )
    result = apply_discounts(doc, s)
    pos = result.all_positions[0]
    assert "meta" in pos["assortment"]
    assert pos["assortment"]["meta"]["href"] == "https://x/p1"
