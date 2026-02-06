from __future__ import annotations

from dataclasses import dataclass
import os


def _env(key: str, default: str = "") -> str:
    value = os.getenv(key)
    return default if value is None else value


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_list(key: str, default: list[str]) -> list[str]:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    base_url: str
    auth_mode: str
    token: str
    login: str
    password: str
    document_types: list[str]

    loyalty_enabled_attr: str
    loyalty_discount_attr: str
    promo_attr: str
    promo_tag: str
    disable_loyalty_attr: str
    loyalty_discount_sum_attr: str

    respect_existing_discount: bool
    dry_run: bool
    log_level: str
    webhook_bearer_token: str
    request_timeout: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=_env("MS_BASE_URL", "https://api.moysklad.ru/api/remap/1.2").rstrip("/"),
            auth_mode=_env("MS_AUTH_MODE", "bearer").strip().lower(),
            token=_env("MS_TOKEN", ""),
            login=_env("MS_LOGIN", ""),
            password=_env("MS_PASSWORD", ""),
            document_types=_env_list("DOCUMENT_TYPES", ["customerorder", "demand"]),
            loyalty_enabled_attr=_env("LOYALTY_ENABLED_ATTR", "LoyaltyEnabled"),
            loyalty_discount_attr=_env("LOYALTY_DISCOUNT_ATTR", "LoyaltyDiscountPercent"),
            promo_attr=_env("PROMO_ATTR", "IsPromo"),
            promo_tag=_env("PROMO_TAG", ""),
            disable_loyalty_attr=_env("DISABLE_LOYALTY_ATTR", "DisableLoyalty"),
            loyalty_discount_sum_attr=_env("LOYALTY_DISCOUNT_SUM_ATTR", "LoyaltyDiscountSum"),
            respect_existing_discount=_env_bool("RESPECT_EXISTING_DISCOUNT", False),
            dry_run=_env_bool("DRY_RUN", False),
            log_level=_env("LOG_LEVEL", "INFO"),
            webhook_bearer_token=_env("WEBHOOK_BEARER_TOKEN", ""),
            request_timeout=float(_env("REQUEST_TIMEOUT", "20")),
        )
