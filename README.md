# 📸 Instagram AutoPosting Telegram Bot

Автоматизированный Telegram-бот для подготовки медиа, генерации описаний с помощью искусственного интеллекта (Google Gemini) и публикации постов / историй в Instagram через официальный Meta Graph API.

---

## 🏗 Архитектура проекта

```
MemoryNMore/
├── Dockerfile                           # Сборка контейнера Python 3.11-slim
├── docker-compose.yml                   # Конфигурация запуска сервиса с монтированием томов
├── requirements.txt                     # Зависимости проекта
├── .env.example                         # Пример файла конфигурации
├── .dockerignore                        # Исключения сборки Docker
├── Instagram_AutoPosting_Guide.md       # Подробное руководство по концепции и API
└── src/
    ├── __init__.py
    ├── main.py                          # Точка входа, встроенный статический сервер + polling бота
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
        ├── storage_service.py           # Хранилище: Локальная папка (HTTP) ИЛИ Облако (S3 / Cloudflare R2)
        └── instagram_service.py         # Вызовы Meta Graph API (создание контейнера + публикация)
```

---

## 💾 Варианты хранения медиа (`STORAGE_TYPE`)

Instagram Graph API требует публичную ссылку на изображение для его загрузки в Instagram. В боте поддерживается два режима:

### Режим 1: `STORAGE_TYPE=local` (Локальное хранилище)
Изображения сохраняются в локальную папку на сервере (`./data/media`), которая раздается встроенным сервером или внешним веб-сервером (Nginx / Caddy / Cloudflare Tunnel / ngrok):

```env
STORAGE_TYPE=local
LOCAL_STORAGE_DIR=/app/data/media
LOCAL_PUBLIC_BASE_URL=https://media.yourdomain.com
LOCAL_SERVER_ENABLED=true
LOCAL_SERVER_PORT=3018
```

### Режим 2: `STORAGE_TYPE=s3` (Cloudflare R2 / AWS S3)
Изображения автоматически загружаются в S3-совместимый бакет:

```env
STORAGE_TYPE=s3
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=instagram-media
S3_PUBLIC_DOMAIN=https://media.yourdomain.com
```

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
5. Получите бессрочный/долгоживущий **Page Access Token** и ваш **Instagram Business Account ID** (`IG_USER_ID`).

### 3. Google Gemini API (Опционально)
1. Получите бесплатный API-ключ в [Google AI Studio](https://aistudio.google.com/).
2. Укажите его в `GEMINI_API_KEY` для автогенерации текстов постов, вопросов и хэштегов.

---

## 🚀 Запуск через Docker

### Шаг 1: Создание `.env`
```bash
cp .env.example .env
```
Заполните параметры в `.env`.

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
