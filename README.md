# 📸 Instagram AutoPosting Telegram Bot

Автоматизированный Telegram-бот для подготовки медиа, генерации описаний с помощью искусственного интеллекта (Google Gemini) и публикации постов / историй в Instagram через официальный Meta Graph API.

---

## 🏗 Архитектура проекта

```
MemoryNMore/
├── Dockerfile                           # Сборка контейнера Python 3.11-slim
├── docker-compose.yml                   # Запуск сервиса с монтированием томов
├── requirements.txt                     # Зависимости проекта
├── .env.example                         # Шаблон конфигурации
├── .dockerignore                        # Исключения сборки Docker
├── Instagram_AutoPosting_Guide.md       # Подробное руководство по концепции и API
└── src/
    ├── __init__.py
    ├── main.py                          # Точка входа, жизненный цикл бота, сервера и воркера очистки
    ├── config.py                        # Валидация и загрузка настроек (Pydantic Settings)
    ├── bot/
    │   ├── __init__.py
    │   ├── states.py                    # FSM-состояния диалога
    │   ├── keyboards.py                 # Inline-кнопки (форматы, действия)
    │   └── handlers.py                  # Обработчики фото, команд и кнопок
    └── services/
        ├── __init__.py
        ├── image_service.py             # Кадрирование (Stories 9:16, Feed 4:5, 1:1) и автокоррекция (Pillow)
        ├── ai_service.py                # Генерация текстов и хэштегов (Gemini 2.5 Flash)
        ├── storage_service.py           # Хранилище: Cloudflare R2, AWS S3 или Локальное хранилище
        ├── media_server.py              # Защищенный веб-сервер для раздачи локальных медиа
        ├── cleanup_service.py           # Фоновый воркер автоочистки файлов по TTL
        └── instagram_service.py         # Вызовы Meta Graph API (создание контейнера + публикация)
```

---

## 💾 Варианты хранения медиа (`STORAGE_TYPE`)

Instagram Graph API требует публичную ссылку на изображение (`image_url`) для загрузки контента на серверы Meta.

---

### Режим 1: `STORAGE_TYPE=r2` (Cloudflare R2 — Рекомендуется)
Полностью изолирует ваш сервер, не требует открытия портов и бесплатен (10 ГБ хранилища, 0$ за исходящий трафик).

```env
STORAGE_TYPE=r2

# Данные из панели Cloudflare (R2 -> Manage R2 API Tokens)
R2_ACCOUNT_ID=ваш_account_id_из_панели_cloudflare
R2_ACCESS_KEY_ID=ваш_r2_access_key_id
R2_SECRET_ACCESS_KEY=ваш_r2_secret_access_key
R2_BUCKET_NAME=instagram-media

# Публичный домен бакета:
# - Custom Domain: https://media.yourdomain.com
# - или R2 dev domain: https://pub-xxxxxxxx.r2.dev
R2_PUBLIC_DOMAIN=https://media.yourdomain.com
```

---

### Режим 2: `STORAGE_TYPE=local` (Локальное защищенное хранилище)
Изображения сохраняются в папку `./data/media` и отдаются встроенным сервером `aiohttp` с многоуровневой защитой:

```env
STORAGE_TYPE=local
LOCAL_STORAGE_DIR=/app/data/media
LOCAL_PUBLIC_BASE_URL=https://media.yourdomain.com
LOCAL_SERVER_ENABLED=true
LOCAL_SERVER_PORT=3018
```

#### 🛡 Встроенные механизмы защиты локального сервера:
1. **Защита от Directory Traversal:** Проверка канонических путей (`os.path.commonpath`), блокировка попыток перехода `../` за пределы разрешенной папки.
2. **Блокировка скрытых файлов:** Запрет доступа к любым файлам, начинающимся с точки (`.gitkeep`, `.env`, `.gitignore`).
3. **Белый список расширений (Whitelist):** Разрешена отдача только медиафайлов (`.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.mov`).
4. **Ограничение HTTP-методов:** Разрешены только `GET` и `HEAD`. Все остальные методы (`POST`, `PUT`, `DELETE` и др.) блокируются со статусом `405 Method Not Allowed`.
5. **Заголовки безопасности:** Автоматическая отправка `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`.
6. **Отключение листинга директорий:** Запрос к корню или папкам возвращает `404 Not Found`.

---

### ⏱ Автоматическая очистка файлов (Конфигурируемый TTL)
Так как Instagram скачивает файл за несколько секунд при публикации, бот оснащен фоновым сервисом очистки:

```env
# Включение/отключение фоновой очистки (true/false)
MEDIA_CLEANUP_ENABLED=true

# Время жизни медиафайлов в минутах (например, 120 = 2 часа)
MEDIA_TTL_MINUTES=120

# Интервал проверки устаревших файлов (в минутах)
MEDIA_CLEANUP_INTERVAL_MINUTES=30
```
Воркер удаляет только устаревшие сгенерированные файлы, сохраняя системные файлы вроде `.gitkeep`.

---

## ⚙️ Пошаговая настройка

### 1. Подготовка Telegram-бота
1. Напишите [@BotFather](https://t.me/BotFather) в Telegram и создайте нового бота (`/newbot`).
2. Скопируйте полученный **API Token** (`BOT_TOKEN`).

### 2. Настройка Instagram Graph API (Meta)
1. Переведите профиль Instagram в **Профессиональный аккаунт** (*Автор* или *Бизнес*).
2. Привяжите аккаунт Instagram к публичной бизнес-странице Facebook.
3. На [developers.facebook.com](https://developers.facebook.com/) создайте приложение типа **Business**.
4. Добавьте продукт **Instagram Graph API** и назначьте разрешения:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
   - `pages_show_list`
5. Получите **Page Access Token** и **Instagram Business Account ID** (`IG_USER_ID`).

### 3. Google Gemini API (Опционально)
1. Получите бесплатный API-ключ в [Google AI Studio](https://aistudio.google.com/).
2. Укажите его в `GEMINI_API_KEY` для автогенерации текстов постов, вопросов и хэштегов.

---

## 🚀 Запуск через Docker

### Шаг 1: Создание `.env`
```bash
cp .env.example .env
```
Заполните необходимые параметры в `.env`.

### Шаг 2: Сборка и запуск контейнера
```bash
docker compose up -d --build
```

### Шаг 3: Просмотр логов
```bash
docker compose logs -f instagram-bot
```

### Остановка сервиса
```bash
docker compose down
```
