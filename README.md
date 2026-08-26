# 📸 Instagram AutoPosting Telegram Bot

An automated Telegram bot for preparing media, generating AI-powered captions with Google Gemini, and publishing posts and stories to Instagram via the official Meta Graph API.

---

## 🏗 Project Architecture

```
MemoryNMore/
├── Dockerfile                           # Python 3.11-slim container build
├── docker-compose.yml                   # Service launch with volume mounts
├── requirements.txt                     # Project dependencies
├── debug.py                             # Automated diagnostics & health check
├── .dockerignore                        # Docker build exclusions
├── .gitignore                           # Git exclusions
├── config/
│   ├── .env                             # Active environment configuration (git ignored)
│   └── .env.example                     # Configuration template
├── data/
│   └── media/                           # Local temporary media cache
└── src/
    ├── __init__.py
    ├── main.py                          # Entry point, bot lifecycle, media server & cleanup worker
    ├── config.py                        # Validation & settings loader (Pydantic Settings)
    ├── bot/
    │   ├── __init__.py
    │   ├── states.py                    # Conversation FSM states
    │   ├── keyboards.py                 # Inline keyboards (formats, actions)
    │   └── handlers.py                  # Photo, command, and callback query handlers
    └── services/
        ├── __init__.py
        ├── image_service.py             # Smart cropping (Stories 9:16, Feed 4:5, 1:1) & auto-enhancement (Pillow)
        ├── ai_service.py                # AI caption & hashtag generation (Gemini 3.7 Flash)
        ├── storage_service.py           # Storage backends: Cloudflare R2, AWS S3, or Local
        ├── media_server.py              # Secured HTTP server for serving local media
        ├── cleanup_service.py           # Background worker for TTL-based media cleanup
        └── instagram_service.py         # Meta Graph API client (container creation & publishing)
```

---

## 💾 Media Storage Options (`STORAGE_TYPE`)

The Instagram Graph API requires a publicly accessible image URL (`image_url`) to ingest media onto Meta servers.

---

### Mode 1: `STORAGE_TYPE=r2` (Cloudflare R2 — Recommended)
Completely isolates your server, requires no open inbound ports, and is free (10 GB storage included, $0 egress fees).

```env
STORAGE_TYPE=r2

# Credentials from Cloudflare Dashboard (R2 -> Manage R2 API Tokens)
R2_ACCOUNT_ID=your_account_id_from_cloudflare_dashboard
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=instagram-media

# Public bucket domain:
# - Custom Domain: https://media.yourdomain.com
# - or R2 dev domain: https://pub-xxxxxxxx.r2.dev
R2_PUBLIC_DOMAIN=https://media.yourdomain.com
```

---

### Mode 2: `STORAGE_TYPE=local` (Secured Local Storage)
Images are saved in `./data/media` and served by an embedded `aiohttp` web server with multi-layered security:

```env
STORAGE_TYPE=local
LOCAL_STORAGE_DIR=/app/data/media
LOCAL_PUBLIC_BASE_URL=https://media.yourdomain.com
LOCAL_SERVER_ENABLED=true
LOCAL_SERVER_PORT=3018
```

#### 🛡 Built-in Local Server Security Features:
1. **Directory Traversal Protection:** Canonical path validation (`os.path.commonpath`), blocking `../` escape attempts outside the allowed directory.
2. **Hidden File Access Prevention:** Blocks access to any dotfiles (`.gitkeep`, `.env`, `.gitignore`).
3. **Extension Whitelisting:** Serves only allowed media file extensions (`.jpg`, `.jpeg`, `.png`, `.webp`, `.mp4`, `.mov`).
4. **HTTP Method Restriction:** Only `GET` and `HEAD` requests are permitted. All other methods (`POST`, `PUT`, `DELETE`, etc.) return `405 Method Not Allowed`.
5. **Security Headers:** Automatically sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Content-Security-Policy`.
6. **Directory Listing Disabled:** Requests to directory paths or root return `404 Not Found`.

---

### ⏱ Automatic Media Cleanup (Configurable TTL)
Since Instagram fetches the image in seconds during publication, the bot includes a background cleanup service:

```env
# Enable/disable background cleanup (true/false)
MEDIA_CLEANUP_ENABLED=true

# Media time-to-live in minutes (e.g., 120 = 2 hours)
MEDIA_TTL_MINUTES=120

# Cleanup check interval (in minutes)
MEDIA_CLEANUP_INTERVAL_MINUTES=30
```
The worker only purges expired generated media files while preserving system files such as `.gitkeep`.

---

## 📖 Step-by-Step Guide: Setting Up Cloudflare R2

Cloudflare R2 is a high-performance, S3-compatible object storage with zero egress fees and a generous free tier (10 GB).

### Step 1: Create an R2 Bucket
1. Log in to your [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **Storage & Databases** ➔ **R2** in the left sidebar.
3. Click **Create bucket**.
4. Enter a bucket name (e.g., `instagram-media`).
5. Under **Location**, keep *Automatic* or select the closest region (e.g., *Western Europe* / *Eastern Europe* / *North America*).
6. Click **Create Bucket**.

### Step 2: Configure Public Bucket Access (Public URL)
Meta's Instagram servers require a public URL to download the media. Choose one of two options:

* **Option A — Quick (R2 Public Development Domain):**
  1. Inside the created bucket, go to the **Settings** tab.
  2. Scroll down to the **Public Development Domain** section.
  3. Click **Enable** and confirm by typing `allow`.
  4. Copy the generated URL (format: `https://pub-xxxxxxxxxxxxxxxxxxxxxxxx.r2.dev`).
  5. Set this value as `R2_PUBLIC_DOMAIN` in your `.env`.

* **Option B — Production (Custom Subdomain, e.g., `media.yourdomain.com`):**
  1. Inside the bucket, go to the **Settings** tab.
  2. In the **Custom Domains** section, click **Connect Domain**.
  3. Enter your desired subdomain (e.g., `media.yourdomain.com`).
  4. Cloudflare will automatically configure DNS records and issue an SSL certificate.
  5. Set `https://media.yourdomain.com` as `R2_PUBLIC_DOMAIN` in your `.env`.

### Step 3: Generate API Tokens (Access Key & Secret Key)
1. Return to the main **R2** overview page in Cloudflare.
2. In the right panel, find **Account ID** and copy it — this is your `R2_ACCOUNT_ID`.
3. In the right menu, click **Manage R2 API Tokens**.
4. Click **Create API token**.
5. Configure the token permissions:
   * **Token name:** `instagram-bot-token`
   * **Permissions:** Select **Object Read & Write** (or *Admin Read & Write*).
   * **Specify bucket(s):** Choose *Apply to all buckets* or restrict to `instagram-media`.
   * **TTL:** Select *Forever* (or your desired expiration duration).
6. Click **Create API Token**.
7. Copy the generated credentials:
   * **Access Key ID** ➔ `R2_ACCESS_KEY_ID` in `.env`.
   * **Secret Access Key** ➔ `R2_SECRET_ACCESS_KEY` in `.env`.

---

## ⚙️ Setting Up Other Services

### 1. Telegram Bot Setup
1. Message [@BotFather](https://t.me/BotFather) on Telegram and create a new bot using `/newbot`.
2. Copy the generated **API Token** (`BOT_TOKEN`).

### 2. Instagram Graph API Setup (Meta)
1. Switch your Instagram profile to a **Professional Account** (*Creator* or *Business*).
2. Connect your Instagram account to a public Facebook Business Page.
3. In the [Meta for Developers Console](https://developers.facebook.com/), create an app of type **Business**.
4. Add the **Instagram Graph API** product and request the following permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
   - `pages_show_list`
5. Generate a **Page Access Token** and copy your **Instagram Business Account ID** (`IG_USER_ID`).

### 3. Google Gemini API (Optional)
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Set it in `GEMINI_API_KEY` for automated caption, question, and hashtag generation.

---

## 🚀 Remote Server Deployment (VPS / VDS)

### Step 1: Server Preparation (Ubuntu / Debian)
Connect to your server via SSH and install Docker + Docker Compose:
```bash
# Update packages and install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Verify installation
docker --version
docker compose version
```

---

### Step 2: Clone the Repository & Configure Environment Variables

You can pass environment variables in two convenient ways:

#### Way 1: Using `.env` file (Default & Recommended)
```bash
# Clone the repository to the server
git clone <YOUR_REPOSITORY_URL> /opt/MemoryNMore
cd /opt/MemoryNMore

# Create .env from the template
cp .env.example .env
nano .env  # or vim .env
```
Fill in the parameters in `.env` (Telegram token, Instagram ID/Token, Gemini API Key, Cloudflare R2 or Local settings).

#### Way 2: Directly in `docker-compose.yml` or Shell Environment
The `docker-compose.yml` file includes a full `environment:` block with fallback interpolation (`${VAR:-default}`). You can:
- **Hardcode values directly** in the `environment:` section of `docker-compose.yml`.
- **Pass variables at runtime** without modifying files:
  ```bash
  BOT_TOKEN=123:abc IG_USER_ID=456 IG_ACCESS_TOKEN=xyz docker compose up -d --build
  ```
- **Use `.env` optionally**: `env_file` is set to `required: false`, so the container will start smoothly whether `.env` exists or variables are defined purely in Docker Compose.

---

### Step 3: Run Containers

#### Option A: Standard Run (Recommended with `STORAGE_TYPE=r2`)
```bash
docker compose up -d --build
```

#### Option B: Run with Cloudflare Tunnel (for `STORAGE_TYPE=local`)
If you use local media serving and want secure public HTTPS without opening firewall ports:
1. Provide your tunnel token in `.env`: `CLOUDFLARE_TUNNEL_TOKEN=your_token`
2. Start using the `tunnel` profile:
```bash
docker compose --profile tunnel up -d --build
```

---

### Step 4: Useful Server Management Commands

| Action | Command |
| :--- | :--- |
| **View real-time logs** | `docker compose logs -f instagram-bot` |
| **Restart bot** | `docker compose restart instagram-bot` |
| **Stop bot** | `docker compose down` |
| **Update to latest version** | `git pull && docker compose up -d --build` |
| **Check container status & resources** | `docker stats instagram_autoposting_bot` |
| **Auto-restart on server reboot** | Enabled by default (`restart: unless-stopped`) |
