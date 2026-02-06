from ms_loyalty.app.config import Settings
from ms_loyalty.app.logic import apply_discounts


def _settings(**kwargs):
    base = Settings.from_env()
    return base.__class__(
        base_url=base.base_url,
        auth_mode=base.auth_mode,
        token=base.token,
        login=base.login,
        password=base.password,
        document_types=base.document_types,
        loyalty_enabled_attr=base.loyalty_enabled_attr,
        loyalty_discount_attr=base.loyalty_discount_attr,
        promo_attr=base.promo_attr,
        promo_tag=base.promo_tag,
        disable_loyalty_attr=base.disable_loyalty_attr,
        loyalty_discount_sum_attr=base.loyalty_discount_sum_attr,
        respect_existing_discount=kwargs.get("respect_existing_discount", base.respect_existing_discount),
        dry_run=base.dry_run,
        log_level=base.log_level,
        webhook_bearer_token=base.webhook_bearer_token,
        request_timeout=base.request_timeout,
    )


def test_apply_discount_to_non_promo():
    settings = _settings()
    document = {
        "agent": {
            "attributes": [
                {"name": settings.loyalty_enabled_attr, "value": True},
                {"name": settings.loyalty_discount_attr, "value": 10},
            ]
        },
        "positions": [
            {
                "id": "p1",
                "price": 10000,
                "quantity": 2,
                "discount": 0,
                "assortment": {"meta": {"href": "x"}, "attributes": []},
            }
        ],
    }
    result = apply_discounts(document, settings)
    assert result.updated_positions
    assert result.updated_positions[0]["discount"] == 10.0
    assert result.loyalty_discount_sum == 2000


def test_promo_item_excluded():
    settings = _settings()
    document = {
        "agent": {
            "attributes": [
                {"name": settings.loyalty_enabled_attr, "value": True},
                {"name": settings.loyalty_discount_attr, "value": 10},
            ]
        },
        "positions": [
            {
                "id": "p1",
                "price": 10000,
                "quantity": 2,
                "discount": 0,
                "assortment": {
                    "meta": {"href": "x"},
                    "attributes": [{"name": settings.promo_attr, "value": True}],
                },
            }
        ],
    }
    result = apply_discounts(document, settings)
    assert not result.updated_positions
    assert result.loyalty_discount_sum == 0


def test_respect_existing_discount():
    settings = _settings(respect_existing_discount=True)
    document = {
        "agent": {
            "attributes": [
                {"name": settings.loyalty_enabled_attr, "value": True},
                {"name": settings.loyalty_discount_attr, "value": 10},
            ]
        },
        "positions": [
            {
                "id": "p1",
                "price": 10000,
                "quantity": 2,
                "discount": 5,
                "assortment": {"meta": {"href": "x"}, "attributes": []},
            }
        ],
    }
    result = apply_discounts(document, settings)
    assert not result.updated_positions
    assert result.loyalty_discount_sum == 1000
