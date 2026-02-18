# Передача проекта: Автоматизация скидок ПЛ в МойСклад

## Статус: ГОТОВО к деплою на продакшен

Вся бизнес-логика реализована, протестирована (25 unit-тестов), проверена end-to-end через реальный МойСклад + вебхуки (ngrok). Код полностью рабочий.

---

## Что уже сделано

### Код
| Файл | Описание |
|------|----------|
| `ms_loyalty/app/config.py` | Настройки (dataclass из .env) |
| `ms_loyalty/app/logic.py` | Бизнес-логика: определение оптовика, расчёт скидки, детект акционных товаров |
| `ms_loyalty/app/moysklad.py` | HTTP-клиент МойСклад API (авторизация, CRUD, пагинация позиций, метаданные) |
| `ms_loyalty/app/processor.py` | Оркестратор: получает документ → считает скидки → обновляет через PUT |
| `ms_loyalty/app/main.py` | FastAPI-сервер: `/webhook` (приём вебхуков), `/health` |
| `ms_loyalty/tests/test_logic.py` | 25 unit-тестов (pytest, без API) |
| `ms_loyalty/scripts/export_report.py` | Скрипт выгрузки отчёта в Excel за период |
| `ms_loyalty/scripts/apply_discounts.py` | Ручной запуск обработки конкретного документа |

### В МойСклад (аккаунт "Yerbol") уже созданы
- Доп. поле контрагента: **Программа лояльности** (тип: Флажок)
- Доп. поле контрагента: **Скидка по ПЛ (%)** (тип: Число)
- Папка товаров: **Акция**
- Тестовые вебхуки (4 шт.) — указывают на ngrok, **нужно пересоздать на продакшен-URL**

### Токен МойСклад
Токен в `.env` (`MS_TOKEN`) — **стабильный**, менять не нужно.

---

## Что осталось сделать (деплой на прод)

### 1. Получить сервер
- Любой VPS/VDS с Linux (Ubuntu 22+ рекомендуется)
- Открытый порт 443 (HTTPS)
- Домен (например `loyalty.company.ru`) с DNS A-записью на IP сервера

### 2. Развернуть сервис

```bash
# Склонировать репо
git clone <repo-url> /opt/ms_loyalty
cd /opt/ms_loyalty/ms_loyalty

# Python 3.11+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Скопировать .env.example → .env, заполнить токен
cp .env.example .env
# В .env вписать:
#   MS_TOKEN=d3697de55102da5fe83adac3364791796ae641fa
#   WEBHOOK_BEARER_TOKEN=<придумать длинный секрет>
```

### 3. Настроить HTTPS (nginx + Let's Encrypt)

```nginx
server {
    listen 443 ssl;
    server_name loyalty.company.ru;

    ssl_certificate /etc/letsencrypt/live/loyalty.company.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/loyalty.company.ru/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8095;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Выпустить сертификат
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d loyalty.company.ru
```

### 4. Запустить как systemd-сервис

Создать `/etc/systemd/system/ms-loyalty.service`:

```ini
[Unit]
Description=MoySklad Loyalty Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/ms_loyalty/ms_loyalty
ExecStart=/opt/ms_loyalty/ms_loyalty/.venv/bin/uvicorn ms_loyalty.app.main:app --host 127.0.0.1 --port 8095
Restart=always
EnvironmentFile=/opt/ms_loyalty/ms_loyalty/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ms-loyalty
sudo systemctl start ms-loyalty
sudo systemctl status ms-loyalty
```

### 5. Пересоздать вебхуки в МойСклад

Удалить старые (ngrok) и создать 4 новых вебхука:

| Тип документа | Событие | URL |
|--------------|---------|-----|
| Заказ покупателя | Создание | `https://loyalty.company.ru/webhook` |
| Заказ покупателя | Изменение | `https://loyalty.company.ru/webhook` |
| Отгрузка | Создание | `https://loyalty.company.ru/webhook` |
| Отгрузка | Изменение | `https://loyalty.company.ru/webhook` |

Можно через API (см. README.md) или через интерфейс МойСклад: **Настройки → Вебхуки**.

---

## Бизнес-логика (кратко)

При создании/изменении заказа покупателя или отгрузки:

1. Проверяем контрагента:
   - Тег **«Оптовик»** есть? (регистронезависимо)
   - Флажок **«Программа лояльности»** = Да?
   - **«Скидка по ПЛ (%)»** > 0?
2. Если все условия — для каждой позиции:
   - Товар в папке **«Акция»**? → скидка **0%**
   - Иначе → скидка = % из карточки контрагента
3. Если контрагент НЕ в ПЛ → все скидки **0%**
4. PUT-запрос со **всеми** позициями (иначе МойСклад удалит неотправленные)

---

## Важные нюансы (грабли, которые уже решены)

- **Accept-заголовок**: МойСклад требует `application/json;charset=utf-8`, не просто `application/json`
- **Теги контрагентов**: МойСклад автоматически приводит к нижнему регистру — сравнение case-insensitive
- **Метаданные**: атрибуты могут приходить как список или как dict (collection reference) — обработаны оба варианта
- **PUT позиций**: отправлять ВСЕ позиции, не только изменённые — иначе МойСклад удалит остальные
- **Вариантные товары**: у вариантов нет pathName, нужно подтягивать от родительского product

---

## Тесты

```bash
cd ms_loyalty
pytest tests/ -v
```

25 тестов, все проходят. Запускаются без API.

---

## Документация

- `README.md` — техническая документация
- `ADMIN_GUIDE.md` — инструкция для администратора МойСклад (настройка контрагентов, товаров, вебхуков)
