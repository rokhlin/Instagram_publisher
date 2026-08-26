# Руководство по автоматизации контента и постинга в Instagram через Telegram-бота

---

## 1. Концепция и тематика личного блога

### Направления контента
* **Семья (Family & Warmth):** Искренние совместные моменты, эмоции детей, семейные традиции и прогулки.
* **Путешествия (Travel & Memories):** Панорамные виды, впечатления от новых мест, дорожные заметки.
* **Любовь к природе (Nature & Harmony):** Пейзажи, закаты, море, прогулки на свежем воздухе.
* **Развлечения и досуг (Entertainment & Fun):** Мероприятия, активный отдых, яркие выходные.

### Форматы публикаций
* **Instagram Stories:** Соотношение сторон `9:16` (1080×1920 px). Текст и стикеры располагаются в центральной трети экрана, чтобы не перекрываться интерфейсом Instagram.
* **Посты в ленту (Feed Posts):** Соотношение сторон `4:5` (1080×1350 px) или `1:1` (1080×1080 px).

---

## 2. Скрипт автоматической подготовки медиа (Python / Pillow)

Скрипт автоматически обрезает фото под пропорции Stories (`9:16`) с центрированием и базовой коррекцией контраста и цвета:

```python
from PIL import Image, ImageEnhance, ImageOps

def prepare_story_image(input_path: str, output_path: str):
    """Кадрирование и коррекция фото для Instagram Stories (1080x1920)."""
    img = Image.open(input_path).convert('RGB')
    
    # Целевой размер 9:16
    target_size = (1080, 1920)
    img_cropped = ImageOps.fit(img, target_size, centering=(0.5, 0.5))
    
    # Легкое усиление контраста и цвета
    img_contrast = ImageEnhance.Contrast(img_cropped).enhance(1.08)
    img_final = ImageEnhance.Color(img_contrast).enhance(1.05)
    
    img_final.save(output_path, quality=95)
    print(f"Файл сохранен: {output_path}")
```

---

## 3. Настройка Instagram Graph API для автопостинга

### Шаг 1: Подготовка аккаунтов
1. Переведите профиль Instagram в **Профессиональный аккаунт** (*Автор* или *Бизнес*).
2. Привяжите аккаунт Instagram к бизнес-странице в Facebook.

### Шаг 2: Создание приложения в Meta for Developers
1. Создайте приложение с типом **Business** на [developers.facebook.com](https://developers.facebook.com/).
2. Добавьте продукт **Instagram Graph API**.
3. Назначьте необходимые разрешения (**Permissions**):
   * `instagram_basic`
   * `instagram_content_publish`
   * `pages_read_engagement`
   * `pages_show_list`

### Шаг 3: Получение токенов и ID
1. В **Graph API Explorer** сгенерируйте *User Access Token* и обменяйте его на долгоживущий *Page Access Token* (или бессрочный токен системного пользователя в Meta Business Manager).
2. Получите ваш `INSTAGRAM_ACCOUNT_ID`:
   ```http
   GET https://graph.facebook.com/v20.0/me/accounts?fields=instagram_business_account
   ```

### Шаг 4: Вызовы API для публикации

#### Создание медиа-контейнера:
```http
POST https://graph.facebook.com/v20.0/{INSTAGRAM_ACCOUNT_ID}/media
```
**Параметры:**
* `image_url`: `"https://your-public-storage.com/photo.jpg"`
* `caption`: `"Текст поста #хэштеги"`
* `access_token`: `"{ACCESS_TOKEN}"`
* *Для Stories добавьте параметр:* `"media_type": "STORIES"`

**Ответ:**
```json
{
  "id": "CREATION_ID"
}
```

#### Публикация контейнера:
```http
POST https://graph.facebook.com/v20.0/{INSTAGRAM_ACCOUNT_ID}/media_publish
```
**Параметры:**
* `creation_id`: `"{CREATION_ID}"`
* `access_token`: `"{ACCESS_TOKEN}"`

---

## 4. Архитектура и реализация Telegram-бота

### Сценарий работы (FSM)
1. Пользователь отправляет в Telegram фото/видео и указывает тему/пожелания.
2. Бот обрабатывает изображение и генерирует текст, стикеры и хэштеги (через LLM/Gemini API).
3. Бот присылает превью с Inline-кнопками: `[✅ Опубликовать]`, `[✏️ Внести правки]`, `[❌ Отменить]`.
4. При подтверждении бот отправляет запрос в Instagram Graph API и сообщает об успешной публикации.

### Пример реализации Telegram-бота (aiogram 3 + aiohttp)

```python
import os
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

class PostFlow(StatesGroup):
    waiting_for_media = State()
    waiting_for_approval = State()
    waiting_for_edit = State()

def get_approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="post_publish")],
        [InlineKeyboardButton(text="✏️ Внести правки", callback_data="post_edit")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="post_cancel")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(PostFlow.waiting_for_media)
    await message.answer("Отправьте фото/видео и напишите тему или пожелания.")

@dp.message(PostFlow.waiting_for_media, F.photo)
async def handle_media(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    
    # Пример структуры сформированного поста
    caption = (
        "Заново открываем мир вместе 🌍✨\n\n"
        "📍 Интерактив: Опрос (Да / Нет)\n"
        "#travel #family #nature"
    )
    
    await state.update_data(file_id=photo.file_id, caption=caption)
    await state.set_state(PostFlow.waiting_for_approval)
    
    await message.answer_photo(
        photo=photo.file_id,
        caption=f"📋 *Предварительный просмотр:*\n\n{caption}",
        parse_mode="Markdown",
        reply_markup=get_approval_keyboard()
    )

@dp.callback_query(PostFlow.waiting_for_approval, F.data == "post_publish")
async def process_publish(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("⏳ Публикую в Instagram...")
    
    # Вызов Instagram Graph API (контейнер + публикация)
    # publish_result = await publish_to_instagram(...)
    
    await callback.message.answer("🎉 Пост успешно опубликован!")
    await state.clear()

@dp.callback_query(PostFlow.waiting_for_approval, F.data == "post_edit")
async def process_edit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostFlow.waiting_for_edit)
    await callback.message.answer("Напишите, какие правки внести в текст:")

@dp.message(PostFlow.waiting_for_edit)
async def apply_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    updated_caption = f"{data['caption']}\n\n_Правка:_ {message.text}"
    await state.update_data(caption=updated_caption)
    await state.set_state(PostFlow.waiting_for_approval)
    
    await message.answer_photo(
        photo=data['file_id'],
        caption=f"📋 *Обновлённое превью:*\n\n{updated_caption}",
        parse_mode="Markdown",
        reply_markup=get_approval_keyboard()
    )

@dp.callback_query(PostFlow.waiting_for_approval, F.data == "post_cancel")
async def process_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🚫 Публикация отменена.")
```

---

## 5. Развертывание и безопасность

### Конфигурационный файл `.env`
Размещается в корне проекта на сервере (рядом с `main.py`):
```env
BOT_TOKEN=your_telegram_bot_token
IG_USER_ID=your_instagram_account_id
IG_ACCESS_TOKEN=your_long_lived_token
GEMINI_API_KEY=your_gemini_api_key
```

### Рекомендации:
1. **Безопасность:** Добавьте `.env` в `.gitignore`. Никогда не публикуйте ключи в открытых репозиториях.
2. **Хранение медиа:** Для передачи картинок в Instagram API они должны быть доступны по публичному HTTPS URL (Cloudflare R2, AWS S3, Supabase Storage или статический Nginx-каталог вашего сервера).
3. **Автономность:** Бот запускается в фоновом режиме (через `systemd` или `docker compose`) и работает 24/7.