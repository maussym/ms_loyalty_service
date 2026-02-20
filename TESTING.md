# Тестирование сервиса МойСклад Loyalty

## Сервер
- IP: `65.109.160.34`
- URL: `https://65-109-160-34.nip.io`
- SSH: `ssh -i C:\Users\imaus\.ssh\hetzner_key root@65.109.160.34`

---

## 1. Health check

```bash
curl -s https://65-109-160-34.nip.io/health
```

Ожидание: `{"status":"ok"}`

---

## 2. Статус сервиса (на сервере)

```bash
systemctl status ms-loyalty
```

---

## 3. Логи в реальном времени (на сервере)

```bash
journalctl -u ms-loyalty -f
```

---

## 4. Unit-тесты (на сервере)

```bash
cd /opt && source /opt/ms_loyalty/.venv/bin/activate && python -m pytest ms_loyalty/tests/ -v
```

---

## 5. Создать заказ — обычный товар + контрагент с ПЛ (скидка станет 10%)

```bash
curl -s -X POST https://api.moysklad.ru/api/remap/1.2/entity/customerorder \
  -H "Authorization: Bearer ba8bc093bce64d639441e686546b0f27e4fbc7d6" \
  -H "Accept: application/json;charset=utf-8" \
  -H "Content-Type: application/json;charset=utf-8" \
  -d '{
    "organization": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/6c3851b6-defb-11ef-0a80-08b20020fb0f", "type": "organization", "mediaType": "application/json"}},
    "agent": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/02da3ff0-9ada-11f0-0a80-1624000f5c93", "type": "counterparty", "mediaType": "application/json"}},
    "positions": [{"quantity": 1, "price": 150000, "discount": 0, "assortment": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/product/000f0572-ea18-11ef-0a80-162600776814", "type": "product", "mediaType": "application/json"}}}]
  }'
```

Ожидание: заказ создается, через 3-5 секунд вебхук срабатывает, скидка на позиции становится **10%**.

---

## 6. Создать заказ — акционный товар SSD (скидка останется 0%)

```bash
curl -s -X POST https://api.moysklad.ru/api/remap/1.2/entity/customerorder \
  -H "Authorization: Bearer ba8bc093bce64d639441e686546b0f27e4fbc7d6" \
  -H "Accept: application/json;charset=utf-8" \
  -H "Content-Type: application/json;charset=utf-8" \
  -d '{
    "organization": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/6c3851b6-defb-11ef-0a80-08b20020fb0f", "type": "organization", "mediaType": "application/json"}},
    "agent": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/02da3ff0-9ada-11f0-0a80-1624000f5c93", "type": "counterparty", "mediaType": "application/json"}},
    "positions": [{"quantity": 1, "price": 80000, "discount": 0, "assortment": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/product/005c79bb-ec47-11f0-0a80-1a22008b4e95", "type": "product", "mediaType": "application/json"}}}]
  }'
```

Ожидание: скидка остается **0%** (товар в папке "Акция").

---

## 7. Создать заказ — контрагент без ПЛ (скидка сбросится в 0%)

```bash
curl -s -X POST https://api.moysklad.ru/api/remap/1.2/entity/customerorder \
  -H "Authorization: Bearer ba8bc093bce64d639441e686546b0f27e4fbc7d6" \
  -H "Accept: application/json;charset=utf-8" \
  -H "Content-Type: application/json;charset=utf-8" \
  -d '{
    "organization": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/organization/6c3851b6-defb-11ef-0a80-08b20020fb0f", "type": "organization", "mediaType": "application/json"}},
    "agent": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/counterparty/6c7ecdf2-defb-11ef-0a80-00e1001e9135", "type": "counterparty", "mediaType": "application/json"}},
    "positions": [{"quantity": 1, "price": 200000, "discount": 5, "assortment": {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/product/000f0572-ea18-11ef-0a80-162600776814", "type": "product", "mediaType": "application/json"}}}]
  }'
```

Ожидание: скидка сбрасывается в **0%** (контрагент "rolan" не в программе лояльности).

---

## 8. Проверить позиции заказа

Вставить ID заказа из ответа предыдущих команд:

```bash
curl -s "https://api.moysklad.ru/api/remap/1.2/entity/customerorder/ВСТАВЬ_ID_ЗАКАЗА/positions" \
  -H "Authorization: Bearer ba8bc093bce64d639441e686546b0f27e4fbc7d6" \
  -H "Accept: application/json;charset=utf-8" | python3 -m json.tool
```

Смотреть поле `"discount"` в каждой позиции.

---

## 9. Список вебхуков

```bash
curl -s "https://api.moysklad.ru/api/remap/1.2/entity/webhook" \
  -H "Authorization: Bearer ba8bc093bce64d639441e686546b0f27e4fbc7d6" \
  -H "Accept: application/json;charset=utf-8" \
  -H "Content-Type: application/json;charset=utf-8" | python3 -m json.tool
```

---

## 10. Перезапуск сервиса (на сервере)

```bash
systemctl restart ms-loyalty
```

---

## 11. Обновление кода (с локального компьютера)

```bash
scp -i C:\Users\imaus\.ssh\hetzner_key -r C:\moysklad_loyalty_service\ms_loyalty\app root@65.109.160.34:/opt/ms_loyalty/
```

Потом на сервере:
```bash
systemctl restart ms-loyalty
```

---

## Порядок демонстрации заказчику

1. Открыть SSH → запустить `journalctl -u ms-loyalty -f` (логи)
2. В другом терминале выполнить команду 5 (обычный товар) → показать что скидка стала 10%
3. Выполнить команду 6 (акционный товар) → показать что скидка 0%
4. Выполнить команду 7 (контрагент без ПЛ) → показать что скидка 0%
5. Открыть МойСклад → показать заказы с примененными скидками

## Тестовые данные

| Сущность | Имя | ID |
|----------|-----|----|
| Организация | siriuslabt | `6c3851b6-defb-11ef-0a80-08b20020fb0f` |
| Контрагент с ПЛ | АЛЬТАИР20211 | `02da3ff0-9ada-11f0-0a80-1624000f5c93` |
| Контрагент без ПЛ | rolan | `6c7ecdf2-defb-11ef-0a80-00e1001e9135` |
| Обычный товар | CR1001T | `000f0572-ea18-11ef-0a80-162600776814` |
| Акционный товар | SSD 256 | `005c79bb-ec47-11f0-0a80-1a22008b4e95` |
