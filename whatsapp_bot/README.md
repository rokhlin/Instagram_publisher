# 📱 MemoryNMore WhatsApp Chatbot Connector

WhatsApp bot connector for the **MemoryNMore** Instagram AutoPosting ecosystem, powered by [`whatsapp-web.js`](https://github.com/pedroslopez/whatsapp-web.js), `LocalAuth`, and Express REST API.

---

> [!CAUTION]
> ### ⚠️ DO NOT USE YOUR PERSONAL / MAIN PHONE NUMBER!
> **Always use a dedicated separate SIM / phone number for this bot.**
> 
> Because this connector acts as a linked WhatsApp Web client, **every incoming message, mention, or media posted in your subscribed personal and group chats will be received by the bot and may automatically trigger bot reactions and AI processing.**
>
> To avoid accidental auto-replies, privacy leaks, or spamming your contacts and groups:
> 1. Use a **dedicated bot phone number / virtual SIM**.
> 2. Configure `WHATSAPP_ALLOWED_NUMBERS` in `.env` to strictly restrict access to authorized phone numbers only.

---

## ⚡ Quick Start

### 1. Local Run (TypeScript / Node.js)

```bash
cd whatsapp_bot
npm install

# For development with live reload:
npm run dev

# Or build and run production bundle:
npm run build
npm start
```

1. Once started, a **QR code** will print directly in your terminal.
2. You can also view and scan the QR code via browser at: **`http://localhost:3019/qr`**
3. **Open WhatsApp on your DEDICATED bot phone** *(DO NOT USE YOUR PERSONAL NUMBER)*: **Settings (or ⋮)** ➔ **Linked Devices** ➔ **Link a Device**.
4. Scan the QR code. The session is saved in `data/whatsapp_auth/` so you won't need to scan again on restarts!

---

### 2. Docker Run (Docker Compose)

The WhatsApp bot runs independently or alongside the Telegram bot. To run only WhatsApp bot:

```bash
docker compose up -d --build whatsapp-bot
```

To run both Telegram and WhatsApp bots together:

```bash
docker compose up -d --build
```

To view the QR code from the container logs:
```bash
docker compose logs -f whatsapp-bot
```
Or simply open: `http://localhost:3019/qr`

> [!WARNING]
> **Reminder:** Scan the QR code using a **dedicated bot number**, never your primary personal WhatsApp account.

---

## 🌐 REST API Reference

The connector provides a built-in HTTP server on port `3019`:

### `GET /status` (or `/health`)
Returns client readiness and connection status.
```json
{
  "success": true,
  "status": "READY",
  "is_ready": true,
  "client_info": {
    "name": "Bot Account",
    "phone": "79991234567",
    "platform": "whatsapp"
  }
}
```

### `GET /qr`
Renders an auto-refreshing web page with the WhatsApp QR code.

### `POST /send-message`
Sends a text message to a specific number.
```json
{
  "to": "79991234567",
  "message": "📸 Instagram post successfully published!"
}
```

### `POST /send-media`
Sends an image or video from URL or Base64.
```json
{
  "to": "79991234567",
  "mediaUrl": "https://pub-xxx.r2.dev/media.jpg",
  "caption": "Check out this photo!"
}
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `WHATSAPP_PORT` | `3019` | Express HTTP API port |
| `WHATSAPP_HOST` | `0.0.0.0` | HTTP listen address |
| `WHATSAPP_AUTH_DIR` | `../data/whatsapp_auth` | Local session persistence directory |
| `WHATSAPP_ALLOWED_NUMBERS` | `""` | **Recommended:** Comma-separated allowed numbers (e.g. `79991234567,12025550123`). Restricts bot interactions to authorized users only. Empty = allow all. |
| `PYTHON_BACKEND_URL` | `""` | Optional Python backend webhook relay URL |
| `PUPPETEER_EXECUTABLE_PATH` | `undefined` | Path to system Chromium executable (in Docker: `/usr/bin/chromium`) |
