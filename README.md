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

## 📋 Configuration Reference (Environment Variables)

All variables can be supplied either via **`config/.env`** or directly as **Docker Compose / container environment variables**. Variables are validated conditionally based on the active `STORAGE_TYPE`, so you only need to configure parameters relevant to your setup.

---

### 1. Telegram Bot (Core)
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `BOT_TOKEN` | **Yes** | — | Telegram Bot API token from [@BotFather](https://t.me/BotFather). |
| `ALLOWED_USER_IDS` | *Optional* | `""` | Comma-separated list of allowed Telegram user IDs (e.g. `123456789,987654321`). Leave empty to allow any user. |

---

### 2. Instagram Graph API (Publishing)
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `IG_USER_ID` | **Yes** | — | Instagram Business or Creator Account ID linked to your Meta App. |
| `IG_ACCESS_TOKEN` | **Yes** | — | Long-lived Page Access Token or System User Token with publishing permissions. |
| `IG_GRAPH_API_VERSION` | *Optional* | `v21.0` | Meta Graph API version to target. |

---

### 3. Google Gemini AI (AI Content Generation)
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `GEMINI_API_KEY` | *Optional* | `""` | Google AI Studio API key for generating captions, hooks, and hashtags (Gemini 3.7 Flash). If empty, built-in template captions are used. |

---

### 4. Storage Mode Selection
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `STORAGE_TYPE` | **Yes** | `r2` | Storage backend to store publicly accessible media files. Allowed values: `r2`, `s3`, or `local`. |

---

### 5. Cloudflare R2 Storage (Active when `STORAGE_TYPE=r2`)
> [!TIP]
> **Recommended**: Cloudflare R2 includes 10 GB free storage, zero egress bandwidth fees, and requires no open ports on your host.

| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `R2_ACCOUNT_ID` | **Yes** | — | Cloudflare Account ID from the Cloudflare R2 dashboard. |
| `R2_ACCESS_KEY_ID` | **Yes** | — | R2 API Token Access Key ID with Read & Write permissions. |
| `R2_SECRET_ACCESS_KEY` | **Yes** | — | R2 API Token Secret Access Key. |
| `R2_BUCKET_NAME` | **Yes** | `instagram-media` | Target R2 bucket name. |
| `R2_PUBLIC_DOMAIN` | **Yes** | — | Public HTTPS URL for the bucket (e.g. `https://pub-xxxx.r2.dev` or custom subdomain `https://media.yourdomain.com`). |

---

### 6. Generic S3 / AWS S3 Storage (Active when `STORAGE_TYPE=s3`)
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `S3_ENDPOINT_URL` | *Optional* | `""` | Custom S3 endpoint URL (e.g. `https://s3.eu-central-1.amazonaws.com` or MinIO `https://minio.yourdomain.com`). Leave empty for AWS default. |
| `S3_ACCESS_KEY_ID` | **Yes** | — | AWS / S3 Access Key ID. |
| `S3_SECRET_ACCESS_KEY` | **Yes** | — | AWS / S3 Secret Access Key. |
| `S3_BUCKET_NAME` | **Yes** | `instagram-media` | S3 bucket name. |
| `S3_PUBLIC_DOMAIN` | *Optional* | `""` | Public CDN / domain prefix for uploaded objects (e.g. `https://media.yourdomain.com`). |

---

### 7. Local Media Storage & Web Server (Active when `STORAGE_TYPE=local`)
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `LOCAL_STORAGE_DIR` | *Optional* | `/app/data/media` | Directory inside container where local media is saved (mounted to `./data/media`). |
| `LOCAL_PUBLIC_BASE_URL` | **Yes** | — | Public HTTPS base URL where Instagram API can download local media (e.g. `https://media.yourdomain.com`, Cloudflare Tunnel, or Ngrok). |
| `LOCAL_SERVER_ENABLED` | *Optional* | `false` | Enable built-in secure static HTTP media server on the specified port. |
| `LOCAL_SERVER_HOST` | *Optional* | `0.0.0.0` | Host/bind address for built-in media server. |
| `LOCAL_SERVER_PORT` | *Optional* | `3018` | Port exposed by built-in media server (mapped in `docker-compose.yml`). |

---

### 8. Automatic Media Cleanup / TTL
| Variable | Required | Default | Description |
| :--- | :---: | :---: | :--- |
| `MEDIA_CLEANUP_ENABLED` | *Optional* | `true` | Enable background worker that automatically deletes temporary local media files after expiration. |
| `MEDIA_TTL_MINUTES` | *Optional* | `120` | Time-to-Live (TTL) in minutes before generated media files are deleted (120 = 2 hours). |
| `MEDIA_CLEANUP_INTERVAL_MINUTES` | *Optional* | `30` | Frequency (in minutes) of background cleanup scans. |


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
  5. Set this value as `R2_PUBLIC_DOMAIN` in `config/.env` or Docker Compose.

* **Option B — Production (Custom Subdomain, e.g., `media.yourdomain.com`):**
  1. Inside the bucket, go to the **Settings** tab.
  2. In the **Custom Domains** section, click **Connect Domain**.
  3. Enter your desired subdomain (e.g., `media.yourdomain.com`).
  4. Cloudflare will automatically configure DNS records and issue an SSL certificate.
  5. Set `https://media.yourdomain.com` as `R2_PUBLIC_DOMAIN` in `config/.env` or Docker Compose.

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
   * **Access Key ID** ➔ `R2_ACCESS_KEY_ID` in `config/.env` or Docker Compose.
   * **Secret Access Key** ➔ `R2_SECRET_ACCESS_KEY` in `config/.env` or Docker Compose.

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

### 4. Cloudflare Tunnel Setup (When using `STORAGE_TYPE=local`)

#### Why a Public Tunnel is Required:
When running in `STORAGE_TYPE=local` on a home server, NAS (ZimaOS, Synology, Unraid, CasaOS), or private network behind NAT/firewall:
- The local media server (port `3018`) is private and unreachable from the internet.
- The Meta Instagram Graph API requires a publicly reachable HTTPS URL with valid SSL to fetch the media during publishing.
- A **Cloudflare Tunnel** (or Ngrok / Reverse Proxy) provides an encrypted outbound connection that exposes your local port `3018` to a public domain (e.g., `https://media.yourdomain.com`) without opening router ports or exposing a public IP.

#### Connecting an Existing Cloudflare Tunnel:
1. In the [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/) ➔ **Networks** ➔ **Tunnels**, select your tunnel.
2. Go to **Public Hostnames** ➔ **Add a public hostname**.
3. Configure the route:
   * **Public Hostname:** `media.yourdomain.com` (or your subdomain)
   * **Service Type:** `HTTP`
   * **URL:** `localhost:3018` *(or host LAN IP `192.168.x.x:3018` / container hostname)*
4. Save the hostname.
5. In `config/.env` or Docker Compose, set:
   ```env
   STORAGE_TYPE=local
   LOCAL_SERVER_ENABLED=true
   LOCAL_SERVER_PORT=3018
   LOCAL_PUBLIC_BASE_URL=https://media.yourdomain.com
   ```

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
cp config/.env.example config/.env
nano config/.env  # or vim config/.env
```
Fill in the parameters in `config/.env` (Telegram token, Instagram ID/Token, Gemini API Key, Cloudflare R2 or Local settings).

#### Way 2: Directly in `docker-compose.yml` or Shell Environment
The `docker-compose.yml` file includes a full `environment:` block with fallback interpolation (`${VAR:-default}`). You can:
- **Hardcode values directly** in the `environment:` section of `docker-compose.yml`.
- **Pass variables at runtime** without modifying files:
  ```bash
  BOT_TOKEN=123:abc IG_USER_ID=456 IG_ACCESS_TOKEN=xyz docker compose up -d --build
  ```
- **Use `.env` optionally**: `env_file` is set to `required: false`, so the container will start smoothly whether `.env` exists or variables are defined purely in Docker Compose.

---

### Step 3: Run Container

Start the bot container in detached mode:
```bash
docker compose up -d --build
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
