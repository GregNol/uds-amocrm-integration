# UDS ↔ amoCRM integration

Интеграция: события UDS (новый клиент / заказ / покупка) → контакты и сделки в amoCRM.

## Стек
- Python 3.12 + FastAPI
- PostgreSQL 16
- Docker Compose (app + db + Caddy с авто-HTTPS)

Домен задаётся переменной `APP_DOMAIN` в `.env` (в репозиторий не попадает).

## Сценарии
1. **Новый клиент в UDS** → контакт в amoCRM (если ещё нет).
2. **Покупка в UDS** → контакт (если нет) + сделка + перевод в «Успешно реализовано».
3. **Заказ в UDS** → контакт (если нет) + сделка в стартовом статусе.

Дедупликация контактов: своя БД → поиск в amoCRM по телефону, затем email.
Сделки переиспользуются по `uds_order_id` (заказ → покупка закрывает ту же сделку).

## Структура
```
app/
  main.py            FastAPI: /health, /amocrm/*, /api/v2/events/* (вебхуки UDS), /uds/events
  config.py          настройки из .env
  db.py / models.py  Postgres (токены, маппинги, журнал событий)
  amocrm/            OAuth + REST-клиент amoCRM
  uds/               парсинг вебхука + клиент UDS API
  services/sync.py   бизнес-логика 3 сценариев
scripts/
  dump_amocrm_meta.py  вывод ID воронки/статусов/полей
```

## Запуск
```bash
cp .env.example .env       # заполнить значения (в т.ч. APP_DOMAIN)
docker compose up -d --build
```

### Первичная настройка
1. **DNS:** A-запись поддомена (значение `APP_DOMAIN`) → IP VPS. Открыть порты 80/443.
2. **OAuth amoCRM:** открыть `https://<APP_DOMAIN>/amocrm/auth`, выдать права.
   Токены сохранятся в БД. (Либо вставить одноразовый «код авторизации» из интеграции.)
3. **ID воронки/статусов/полей:**
   ```bash
   docker compose exec app python -m scripts.dump_amocrm_meta
   ```
   Скопировать значения в `.env`, затем `docker compose up -d` (перезапуск).
4. **Вебхуки UDS:** в кабинете UDS указать базовый URL `https://<APP_DOMAIN>`.
   UDS сам шлёт на три пути:
   - `POST /api/v2/events/operation`   — транзакция (покупка)
   - `POST /api/v2/events/participant` — новый клиент
   - `POST /api/v2/events/order`       — заказ
   Подпись `X-Signature` = md5(X-RequestId + X-Timestamp + company_id + api_key),
   проверяется при `UDS_VERIFY_SIGNATURE=true`.

## Проверка
```bash
curl https://<APP_DOMAIN>/health
```

## TODO
- Перед продом заменить `create_all` на Alembic-миграции.
