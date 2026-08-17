# UDS ↔ amoCRM integration

Интеграция: события UDS (новый клиент / заказ / покупка) → контакты и сделки в amoCRM.

## Стек
- Python 3.12 + FastAPI
- PostgreSQL 16
- Docker Compose (app + db). Подключается к внешней сети `edge` (алиас `uds-amocrm-app:8000`).

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
docker network create edge # если еще не создана
cp .env.example .env       # заполнить значения (в т.ч. APP_DOMAIN)
docker compose up -d --build
```

### Первичная настройка
1. **Reverse-proxy:** во внешнем контейнере Caddy/Nginx направьте запрос на `uds-amocrm-app:8000`.
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

## Виджет amoCRM (Чат с клиентом и Заказ в UDS)

В проект включен готовый клиентский виджет для amoCRM, который встраивается в правую панель карточки сделки и контакта:
- **💬 Открыть чат UDS**: открывает диалог с клиентом в UDS во встроенном модальном окне прямо внутри amoCRM (или в новой вкладке).
- **📦 Посмотреть заказ**: открывает карточку заказа в UDS во встроенном модальном окне amoCRM (или в новой вкладке).
- **👤 Профиль клиента**: быстрый переход в профиль клиента в панели UDS.

### Сборка и установка виджета в amoCRM
1. Собрать архив виджета:
   ```bash
   python scripts/build_widget.py
   ```
   Скрипт создаст готовый архив `dist/uds_amocrm_widget.zip`.
2. В amoCRM перейти в **АмоМаркет** (или «Настройки» → «Интеграции»).
3. Нажать **«+ Создать интеграцию»** (или вкладку «Установленные» / «Загрузить виджет»).
4. Загрузить архив `dist/uds_amocrm_widget.zip` и нажать **«Сохранить»**.
5. При открытии любой сделки в правой панели появится блок **«UDS Интеграция»** с кнопками быстрого открытия чата и заказа!

## Проверка
```bash
curl https://<APP_DOMAIN>/health
```

## TODO
- Перед продом заменить `create_all` на Alembic-миграции.

