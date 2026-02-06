# MoySklad Loyalty Discounts (Python)

Автоматизация применения скидок по программе лояльности и выгрузка отчётности в Excel.

## Быстрый старт
1. Установить зависимости:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r ms_loyalty/requirements.txt
   ```
2. Создать `.env` в `ms_loyalty`.
3. Запустить сервис (из корня репозитория):
   ```bash
   python -m uvicorn ms_loyalty.app.main:app --reload --port 8080
   ```

## Конфигурация (.env)
```
MS_BASE_URL=https://api.moysklad.ru/api/remap/1.2
MS_AUTH_MODE=bearer            # bearer | basic
MS_TOKEN=...                   # для bearer
MS_LOGIN=...                   # для basic
MS_PASSWORD=...                # для basic
DOCUMENT_TYPES=customerorder,demand

LOYALTY_ENABLED_ATTR=LoyaltyEnabled
LOYALTY_DISCOUNT_ATTR=LoyaltyDiscountPercent
PROMO_ATTR=IsPromo
PROMO_TAG=
DISABLE_LOYALTY_ATTR=DisableLoyalty
LOYALTY_DISCOUNT_SUM_ATTR=LoyaltyDiscountSum

RESPECT_EXISTING_DISCOUNT=false
DRY_RUN=false
LOG_LEVEL=INFO
WEBHOOK_BEARER_TOKEN=
```

## Настройка доп.полей в МойСклад
### Контрагент
- `LoyaltyEnabled` (логическое)
- `LoyaltyDiscountPercent` (число)

### Товар
- `IsPromo` (логическое) — если товар участвует в акции
  - альтернативно можно использовать тег, заданный в `PROMO_TAG`

### Документ (Заказ покупателя / Отгрузка)
- `DisableLoyalty` (логическое) — отключает автоскидку
- `LoyaltyDiscountSum` (число) — суммарная скидка по лояльности (заполняется сервисом)

## Вебхуки
Сервис ожидает POST на `/webhook`. Включите вебхуки МойСклад на создание/изменение нужных типов документов.
Если задан `WEBHOOK_BEARER_TOKEN`, запрос должен содержать `Authorization: Bearer <token>`.

## Ручной запуск пересчёта
```
python -m ms_loyalty.scripts.apply_discounts --type customerorder --id <document_id>
```

## Отчётность (Excel)
```
python -m ms_loyalty.scripts.export_report --from 2025-01-01 --to 2025-01-31 --out report.xlsx
```

## Логика
- Если контрагент не участвует в программе — скидка не применяется.
- Если документ помечен `DisableLoyalty=true` — скидка не применяется.
- Для неакционных товаров применяется скидка из `LoyaltyDiscountPercent`.
- Акционные товары (по `IsPromo` или по тегу) исключаются.
- При изменении контрагента/позиций скидки пересчитываются повторно.

## Примечания
- Сервис обновляет только скидку в позициях и доп.поле `LoyaltyDiscountSum`.
- Если `RESPECT_EXISTING_DISCOUNT=true`, то позиции с уже установленной скидкой не будут перезаписаны.
