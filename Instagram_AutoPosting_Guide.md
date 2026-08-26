# Guide: Content Automation and Instagram Auto-Posting via Telegram Bot

---

## 1. Concept and Themes for a Personal Blog

### Content Pillars
* **Family & Warmth:** Sincere family moments, children's emotions, family traditions, and outdoor walks.
* **Travel & Memories:** Panoramic views, impressions from new places, travel notes.
* **Nature & Harmony:** Landscapes, sunsets, sea, open-air walks.
* **Entertainment & Fun:** Events, active leisure, vibrant weekend activities.

### Publication Formats
* **Instagram Stories:** Aspect ratio `9:16` (1080×1920 px). Text and stickers should be positioned within the central third of the screen to avoid overlay issues with Instagram UI elements.
* **Feed Posts:** Aspect ratio `4:5` (1080×1350 px) or `1:1` (1080×1080 px).

---

## 2. Automated Media Preparation Script (Python / Pillow)

The script automatically crops photos to Stories proportions (`9:16`) with center-cropping and basic contrast/color auto-enhancement:

```python
from PIL import Image, ImageEnhance, ImageOps

def prepare_story_image(input_path: str, output_path: str):
    """Crop and enhance photo for Instagram Stories (1080x1920)."""
    img = Image.open(input_path).convert('RGB')
    
    # Target size 9:16
    target_size = (1080, 1920)
    img_cropped = ImageOps.fit(img, target_size, centering=(0.5, 0.5))
    
    # Subtle contrast and color enhancement
    img_contrast = ImageEnhance.Contrast(img_cropped).enhance(1.08)
    img_final = ImageEnhance.Color(img_contrast).enhance(1.05)
    
    img_final.save(output_path, quality=95)
    print(f"File saved: {output_path}")
```

---

## 3. Instagram Graph API Setup for Auto-Posting

### Step 1: Account Preparation
1. Switch your Instagram profile to a **Professional Account** (*Creator* or *Business*).
2. Connect your Instagram account to a Facebook Business Page.

### Step 2: Create an App in Meta for Developers
1. Create an app with the **Business** type at [developers.facebook.com](https://developers.facebook.com/).
2. Add the **Instagram Graph API** product.
3. Add the required permissions (**Permissions**):
   * `instagram_basic`
   * `instagram_content_publish`
   * `pages_read_engagement`
   * `pages_show_list`

### Step 3: Generating Tokens and IDs
1. In **Graph API Explorer**, generate a *User Access Token* and exchange it for a long-lived *Page Access Token* (or a permanent system user token in Meta Business Manager).
2. Retrieve your `INSTAGRAM_ACCOUNT_ID`:
   ```http
   GET https://graph.facebook.com/v21.0/me/accounts?fields=instagram_business_account
   ```

### Step 4: API Publishing Calls

#### Creating a Media Container:
```http
POST https://graph.facebook.com/v21.0/{INSTAGRAM_ACCOUNT_ID}/media
```
**Parameters:**
* `image_url`: `"https://your-public-storage.com/photo.jpg"`
* `caption`: `"Post caption #hashtags"`
* `access_token`: `"{ACCESS_TOKEN}"`
* *For Stories, include the parameter:* `"media_type": "STORIES"`

**Response:**
```json
{
  "id": "CREATION_ID"
}
```

#### Publishing the Container:
```http
POST https://graph.facebook.com/v21.0/{INSTAGRAM_ACCOUNT_ID}/media_publish
```
**Parameters:**
* `creation_id`: `"{CREATION_ID}"`
* `access_token`: `"{ACCESS_TOKEN}"`

---

## 4. Telegram Bot Architecture and Implementation

### User Flow (FSM)
1. The user sends a photo/video in Telegram along with a topic or notes in the caption.
2. The bot processes the image and generates the text, interactive question, and hashtags (via LLM/Gemini API).
3. The bot sends a preview with inline buttons: `[🚀 Publish to Instagram]`, `[✏️ Edit Text]`, `[🔄 Regenerate]`, `[❌ Cancel]`.
4. Upon confirmation, the bot sends requests to the Instagram Graph API and reports successful publication.

### Telegram Bot Implementation Example (aiogram 3 + aiohttp)

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
        [InlineKeyboardButton(text="🚀 Publish to Instagram", callback_data="post_publish")],
        [InlineKeyboardButton(text="✏️ Edit Text", callback_data="post_edit")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="post_cancel")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_state(PostFlow.waiting_for_media)
    await message.answer("Send a photo/video and optionally include topic or instructions.")

@dp.message(PostFlow.waiting_for_media, F.photo)
async def handle_media(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    
    # Generated post caption structure
    caption = (
        "Rediscovering the world together 🌍✨\n\n"
        "📍 Question of the day: Where is your favorite weekend getaway?\n\n"
        "#travel #family #nature #lifestyle"
    )
    
    await state.update_data(file_id=photo.file_id, caption=caption)
    await state.set_state(PostFlow.waiting_for_approval)
    
    await message.answer_photo(
        photo=photo.file_id,
        caption=f"📋 *Preview:*\n\n{caption}",
        parse_mode="Markdown",
        reply_markup=get_approval_keyboard()
    )

@dp.callback_query(PostFlow.waiting_for_approval, F.data == "post_publish")
async def process_publish(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("⏳ Publishing to Instagram...")
    
    # Instagram Graph API call (container + publish)
    # publish_result = await publish_to_instagram(...)
    
    await callback.message.answer("🎉 Post published successfully!")
    await state.clear()

@dp.callback_query(PostFlow.waiting_for_approval, F.data == "post_edit")
async def process_edit(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PostFlow.waiting_for_edit)
    await callback.message.answer("Send the updated caption text:")

@dp.message(PostFlow.waiting_for_edit)
async def apply_edit(message: types.Message, state: FSMContext):
    data = await state.get_data()
    updated_caption = message.text.strip()
    await state.update_data(caption=updated_caption)
    await state.set_state(PostFlow.waiting_for_approval)
    
    await message.answer_photo(
        photo=data['file_id'],
        caption=f"📋 *Updated Preview:*\n\n{updated_caption}",
        parse_mode="Markdown",
        reply_markup=get_approval_keyboard()
    )

@dp.callback_query(PostFlow.waiting_for_approval, F.data == "post_cancel")
async def process_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🚫 Publication cancelled.")
```

---

## 5. Deployment and Security

### Configuration File `.env`
Place in the project root on your server (alongside `main.py`):
```env
BOT_TOKEN=your_telegram_bot_token
IG_USER_ID=your_instagram_account_id
IG_ACCESS_TOKEN=your_long_lived_token
GEMINI_API_KEY=your_gemini_api_key
```

### Recommendations:
1. **Security:** Add `.env` to `.gitignore`. Never commit keys to public repositories.
2. **Media Storage (Cloudflare R2):**
   * **Bucket Creation:** In [Cloudflare Dashboard](https://dash.cloudflare.com/) ➔ **Storage & Databases** ➔ **R2** ➔ **Create bucket** (`instagram-media`).
   * **Public Access:** In bucket ➔ **Settings** ➔ enable **Public Development Domain** (`https://pub-xxx.r2.dev`) or connect a **Custom Domain** (`https://media.yourdomain.com`).
   * **API Keys:** In **R2** ➔ **Manage R2 API Tokens** ➔ **Create API token** (permissions: *Object Read & Write*) ➔ copy `Account ID`, `Access Key ID`, `Secret Access Key`.
   * **Configuration in `.env`:** Set `STORAGE_TYPE=r2`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_DOMAIN`.
3. **Autonomy:** The bot runs in background mode (via `docker compose` or `systemd`) and operates 24/7.