/**
 * MemoryNMore WhatsApp Chatbot Connector (TypeScript)
 * Powered by whatsapp-web.js, LocalAuth, Express & Google Gemini AI
 */

import path from 'path';
import fs from 'fs';
import { Client, LocalAuth, MessageMedia, Message } from 'whatsapp-web.js';
import qrcodeTerminal from 'qrcode-terminal';
import QRCode from 'qrcode';
import express, { Request, Response } from 'express';
import cors from 'cors';

import {
    PORT,
    HOST,
    AUTH_DIR,
    MEDIA_DIR,
    ALLOWED_NUMBERS,
    IG_USER_ID,
    STORAGE_TYPE,
    GEMINI_API_KEY,
    R2_PUBLIC_DOMAIN,
    S3_PUBLIC_DOMAIN,
    LOCAL_PUBLIC_BASE_URL,
    PYTHON_BACKEND_URL,
    PUPPETEER_EXECUTABLE_PATH,
    cleanStaleSingletonLocks
} from './config';
import { generateCaption, getBackendStatus } from './backendClient';
import { ClientStatus, UserMediaSession, SendMessagePayload, SendMediaPayload } from './types';

// Clean stale Chromium locks before initialization
cleanStaleSingletonLocks(AUTH_DIR);

let latestQrCode: string | null = null;
let latestQrDataUrl: string | null = null;
let clientStatus: ClientStatus = 'INITIALIZING';
let clientInfo: any = null;

// Track bot-generated message IDs to prevent self-trigger loops
const botSentMessageIds: Set<string> = new Set();
// User conversation state buffer (stores last uploaded media per user)
const userMediaState: Map<string, UserMediaSession> = new Map();

// ============================================================================
// Text Templates (Matching Telegram Bot Experience)
// ============================================================================
const HELP_TEXT = (
    `🌟 *Instagram Auto-Posting Bot Guide*\n\n` +
    `Этот бот помогает подготавливать фото, видео и альбомы (карусели), создавать AI-описания с помощью Google Gemini, ` +
    `накладывать дизайнерские шрифты, применять стильные фильтры, настраивать теги (#) и упоминания (@), и публиковать всё в Instagram!\n\n` +
    `📸 *Поддерживаемые возможности:*\n` +
    `• *Фото, видео и альбомы* (Stories, Feed, Reels, Carousels).\n` +
    `• 🎨 *7 эстетичных фильтров*: Золотой час, Винтаж, Кинематограф, Ч/Б Нуар, Сочный, Мягкий свет.\n` +
    `• 🔤 *5 декоративных шрифтов*: Modern Sans, Рукописный, Элегантный Serif, Ретро Rounded, Акцентный Bold.\n` +
    `• 🤖 *AI-копирайтер*: генерация продающих и душевных описаний с хештегами.\n\n` +
    `🚀 *Как создать публикацию:*\n` +
    `1️⃣ Отправьте фото или видео 📎.\n` +
    `2️⃣ Напишите тему или пожелания к описанию (или отправьте *«готово»* для авто-генерации).\n` +
    `3️⃣ Получите готовый пост и подтвердите публикацию!\n\n` +
    `📋 *Команды:*\n` +
    `• *ping* — проверка связи (ответ: pong)\n` +
    `• */status* — статус подключений и серверов\n` +
    `• */help* — справка и руководство\n` +
    `• */tags* — список предустановленных тегов\n` +
    `• */mentions* — список постоянных упоминаний\n` +
    `• */cancel* — отменить текущую операцию`
);

function getStatusMessage(): string {
    const aiStatus = GEMINI_API_KEY ? 'Google Gemini AI Active' : 'Шаблоны (Ключ не задан)';
    let storageUrl = '';
    if (STORAGE_TYPE === 'R2') storageUrl = R2_PUBLIC_DOMAIN;
    else if (STORAGE_TYPE === 'S3') storageUrl = S3_PUBLIC_DOMAIN;
    else storageUrl = LOCAL_PUBLIC_BASE_URL;

    return (
        `📊 *Статус системы и подключений*\n\n` +
        `• *Instagram Account ID:* \`${IG_USER_ID || 'Не задан'}\`\n` +
        `• *Хранилище:* \`${STORAGE_TYPE}\` ${storageUrl ? `(${storageUrl})` : ''}\n` +
        `• *AI Копирайтер:* \`${aiStatus}\`\n` +
        `• *WhatsApp Бот:* \`Онлайн и готов к работе\` ✅\n` +
        `• *Подключенный аккаунт:* \`${clientInfo?.pushname || 'User'}\` (+${clientInfo?.wid?.user || 'N/A'})\n` +
        `• *Сессия:* \`LocalAuth (Сохранена)\` ✅\n\n` +
        `Отправьте фото, видео или сообщение с темой для подготовки новой публикации.`
    );
}

// ============================================================================
// Access Control & Helpers
// ============================================================================
export function isSenderAllowed(fromNumber: string | null | undefined): boolean {
    if (!fromNumber) return false;
    // If ALLOWED_NUMBERS is defined and non-empty, strictly enforce whitelist
    if (ALLOWED_NUMBERS.length === 0) return true;

    const cleanNumber = String(fromNumber).replace(/[^0-9]/g, '');
    if (!cleanNumber) return false;

    return ALLOWED_NUMBERS.some(allowed => {
        const cleanAllowed = String(allowed).replace(/[^0-9]/g, '');
        if (!cleanAllowed) return false;
        if (cleanNumber === cleanAllowed) return true;
        // Compare last 10 digits to handle international prefix variations (+7 / 8, +1, etc.)
        if (cleanNumber.length >= 10 && cleanAllowed.length >= 10) {
            return cleanNumber.slice(-10) === cleanAllowed.slice(-10);
        }
        return cleanNumber.endsWith(cleanAllowed) || cleanAllowed.endsWith(cleanNumber);
    });
}

export function formatChatId(numberOrId: string | null | undefined): string {
    if (!numberOrId) return '';
    let clean = String(numberOrId).trim().replace(/[^0-9@c.us@g.us@lid]/g, '');
    if (!clean.includes('@')) {
        clean = `${clean.replace(/[^0-9]/g, '')}@c.us`;
    }
    return clean;
}

async function sendBotResponse(msg: Message, replyText: string): Promise<Message | undefined> {
    try {
        const sentMsg = await msg.reply(replyText);
        if (sentMsg?.id?._serialized) {
            botSentMessageIds.add(sentMsg.id._serialized);
            // Prune set if it grows large
            if (botSentMessageIds.size > 2000) {
                const first = botSentMessageIds.values().next().value;
                if (first) botSentMessageIds.delete(first);
            }
        }
        return sentMsg;
    } catch (err: any) {
        console.error(`[Reply Error] Failed to send reply: ${err.message}`);
        try {
            return await client.sendMessage(msg.from, replyText);
        } catch (e2: any) {
            console.error(`[SendMessage Error] Fallback send failed: ${e2.message}`);
        }
    }
}

// ============================================================================
// WhatsApp Client Setup
// ============================================================================
console.log('====================================================');
console.log('  MemoryNMore - WhatsApp Chatbot Connector (TypeScript)');
console.log('====================================================');
console.log(`[Config] Auth Directory: ${AUTH_DIR}`);
console.log(`[Config] Media Directory: ${MEDIA_DIR}`);
console.log(`[Config] REST API Port: ${PORT}`);
if (ALLOWED_NUMBERS.length > 0) {
    console.log(`[Config] Whitelisted Numbers: ${ALLOWED_NUMBERS.join(', ')}`);
} else {
    console.log(`[Config] Whitelisted Numbers: ALL (Open Access)`);
}

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: AUTH_DIR
    }),
    puppeteer: {
        headless: true,
        executablePath: PUPPETEER_EXECUTABLE_PATH,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// QR Code Event
client.on('qr', async (qr: string) => {
    latestQrCode = qr;
    clientStatus = 'QR_READY';

    console.log('\n====================================================');
    console.log('  SCAN WHATSAPP QR CODE TO CONNECT:');
    console.log('====================================================');
    qrcodeTerminal.generate(qr, { small: true });
    console.log('----------------------------------------------------');
    console.log(`[QR Ready] You can also scan via Web UI: http://localhost:${PORT}/qr`);
    console.log('Open WhatsApp on your DEDICATED phone -> Settings -> Linked Devices -> Link a Device\n');

    try {
        latestQrDataUrl = await QRCode.toDataURL(qr, { margin: 2, scale: 8 });
    } catch (err: any) {
        console.error('[QR Error] Failed to generate QR data URL:', err.message);
    }
});

// Authentication & Ready Events
client.on('authenticated', () => {
    clientStatus = 'AUTHENTICATED';
    latestQrCode = null;
    latestQrDataUrl = null;
    console.log('[WhatsApp] Authentication successful! Loading session...');
});

client.on('auth_failure', (msg: string) => {
    clientStatus = 'DISCONNECTED';
    console.error(`[WhatsApp] Authentication failure: ${msg}`);
});

client.on('ready', async () => {
    clientStatus = 'READY';
    latestQrCode = null;
    latestQrDataUrl = null;
    clientInfo = client.info;

    console.log('\n====================================================');
    console.log('  WHATSAPP BOT CONNECTED SUCCESSFULLY!');
    console.log(`  Connected as: ${clientInfo?.pushname || 'User'} (${clientInfo?.wid?.user || 'Unknown'})`);
    console.log('====================================================\n');
});

client.on('disconnected', (reason: string) => {
    clientStatus = 'DISCONNECTED';
    console.warn(`[WhatsApp] Client was disconnected: ${reason}`);
    console.log('[WhatsApp] Re-initializing client in 5 seconds...');
    setTimeout(() => {
        client.initialize().catch(err => {
            console.error('[WhatsApp] Re-init error:', err.message);
        });
    }, 5000);
});

// ============================================================================
// Incoming & Self Message Handler
// ============================================================================
client.on('message_create', async (msg: Message) => {
    // 1. Filter out system / internal protocol notification types
    const IGNORED_TYPES = ['e2e_notification', 'notification_template', 'call_log', 'protocol', 'gp2', 'ciphertext', 'revoked'];
    if (IGNORED_TYPES.includes(msg.type)) {
        return;
    }

    // 2. Prevent infinite loop on bot's own automated replies
    if (msg.id?._serialized && botSentMessageIds.has(msg.id._serialized)) {
        return;
    }

    // 3. Ignore status broadcasts, channels, and newsletter updates
    if (msg.isStatus || msg.from === 'status@broadcast' || msg.from.includes('broadcast') || msg.from.endsWith('@newsletter')) {
        return;
    }

    // 4. Ignore group chats (@g.us) to prevent triggering bot on group messages/mentions
    if (msg.from.endsWith('@g.us') || (msg.author && msg.author.endsWith('@g.us'))) {
        return;
    }

    // 5. Extract sender / chat target number
    const chatTarget = msg.fromMe ? (msg.to || msg.from) : (msg.author || msg.from);
    const senderNumber = (chatTarget || '').replace('@c.us', '').replace('@g.us', '').replace('@lid', '').replace(/[^0-9]/g, '');

    // 6. Whitelist Validation: Ignore any numbers not present in WHATSAPP_ALLOWED_NUMBERS
    if (!isSenderAllowed(senderNumber)) {
        if (ALLOWED_NUMBERS.length > 0) {
            console.log(`[Access Filter] Ignored message from non-whitelisted number: ${senderNumber}`);
        }
        return;
    }

    const body = (msg.body || '').trim();
    const lowerBody = body.toLowerCase();

    console.log(`[Message Event] From: ${senderNumber} | Type: ${msg.type} | FromMe: ${msg.fromMe} | Text: "${body.substring(0, 80)}"`);

    // If message is from self (msg.fromMe === true), ignore own automated bot prefixes
    if (msg.fromMe) {
        const botPrefixes = ['🌟', '📊', '🏓', '✨', '📸', '🔄', '🏷️', '👥', '💡', '⚠️'];
        if (botPrefixes.some(p => body.startsWith(p))) {
            return;
        }
    }

    // -------------------------------------------------------------------------
    // Command Handlers
    // -------------------------------------------------------------------------

    // 1. Ping Command
    if (['ping', 'пинг'].includes(lowerBody)) {
        await sendBotResponse(msg, '🏓 *Pong!* Бот на связи и готов к работе.');
        return;
    }

    // 2. Start / Help Commands
    if (['/start', '/help', 'help', 'помощь', 'меню', 'привет', 'hi', 'hello', 'start'].includes(lowerBody)) {
        await sendBotResponse(msg, HELP_TEXT);
        return;
    }

    // 3. Status Command
    if (['/status', 'status', 'статус'].includes(lowerBody)) {
        await sendBotResponse(msg, getStatusMessage());
        return;
    }

    // 4. Tags Command
    if (['/tags', 'tags', 'теги', 'хештеги'].includes(lowerBody)) {
        const tagsMsg =
            `🏷️ *Предустановленные хештеги (#):*\n\n` +
            `• #семья #семейныйблог #воспоминания #уют #моменты #дети #любовь #счастье #фотодня\n` +
            `• #travel #family #memories #nature #lifestyle\n\n` +
            `💡 _Теги автоматически прикрепляются к сгенерированным постам._`;
        await sendBotResponse(msg, tagsMsg);
        return;
    }

    // 5. Mentions Command
    if (['/mentions', 'mentions', 'упоминания'].includes(lowerBody)) {
        const mentionsMsg =
            `👥 *Постоянные упоминания (@):*\n\n` +
            `• Упоминания используются для отметки соавторов или семейных аккаунтов в Instagram.\n` +
            `• Настроить постоянный список можно через команду */mentions* в Telegram-боте.`;
        await sendBotResponse(msg, mentionsMsg);
        return;
    }

    // 6. Cancel Command
    if (['/cancel', 'cancel', 'отмена', 'стоп'].includes(lowerBody)) {
        userMediaState.delete(senderNumber);
        await sendBotResponse(msg, '🔄 *Действие отменено.* Отправьте фото или видео для создания новой публикации.');
        return;
    }

    // -------------------------------------------------------------------------
    // Media Message Handler (Photos, Videos, Documents)
    // -------------------------------------------------------------------------
    if (msg.hasMedia) {
        try {
            console.log(`[Media Download] Downloading ${msg.type} from ${senderNumber}...`);
            const media = await msg.downloadMedia();

            if (media && media.data) {
                const ext = media.mimetype ? (media.mimetype.split('/')[1] || 'jpg').split(';')[0] : 'jpg';
                const filename = `wa_${Date.now()}_${senderNumber.slice(-4)}.${ext}`;
                const filepath = path.join(MEDIA_DIR, filename);

                // Save to media cache
                fs.writeFileSync(filepath, Buffer.from(media.data, 'base64'));
                const fileSizeKb = Math.round(Buffer.from(media.data, 'base64').length / 1024);

                console.log(`[Media Saved] Saved ${filename} (${fileSizeKb} KB) to ${filepath}`);

                // Save to user session buffer
                userMediaState.set(senderNumber, {
                    filename,
                    filepath,
                    mimetype: media.mimetype,
                    base64: media.data,
                    timestamp: Date.now()
                });

                // If message had an attached caption/instructions
                if (body && body.length > 0) {
                    await sendBotResponse(
                        msg,
                        `📸 *Медиафайл получен!* (${fileSizeKb} KB)\n` +
                        `Генерирую AI-описание по вашей теме: _«${body}»_... ⏳`
                    );
                    const aiCaption = await generateCaption(body, media.data, media.mimetype);
                    await sendBotResponse(
                        msg,
                        `✨ *Сгенерированное AI-описание для Instagram:*\n\n` +
                        `${aiCaption}\n\n` +
                        `------------------------------------\n` +
                        `💡 _Медиа сохранено в кэше._`
                    );
                } else {
                    await sendBotResponse(
                        msg,
                        `📸 *Медиафайл успешно получен!* (${fileSizeKb} KB)\n\n` +
                        `✍️ *Напишите тему/пожелания к описанию* или отправьте *«готово»* для автоматической генерации AI-описания через Google Gemini.`
                    );
                }
                return;
            }
        } catch (mediaErr: any) {
            console.error('[Media Error] Failed to process media:', mediaErr.message);
            await sendBotResponse(msg, '⚠️ Не удалось загрузить медиафайл. Пожалуйста, попробуйте еще раз.');
            return;
        }
    }

    // -------------------------------------------------------------------------
    // General Text / Guidance Handler
    // -------------------------------------------------------------------------
    if (body.length > 0) {
        const userState = userMediaState.get(senderNumber);
        const hasRecentMedia = userState && (Date.now() - userState.timestamp < 1000 * 60 * 60); // 1 hour TTL

        await sendBotResponse(msg, `✨ Генерирую пост по теме: _«${body}»_... ⏳`);

        const imageBase64 = hasRecentMedia ? userState.base64 : null;
        const mimeType = hasRecentMedia ? userState.mimetype : 'image/jpeg';
        const aiCaption = await generateCaption(body, imageBase64, mimeType);

        await sendBotResponse(
            msg,
            `✨ *Готовое описание для Instagram:*\n\n` +
            `${aiCaption}\n\n` +
            `------------------------------------\n` +
            `📸 _Чтобы опубликовать этот пост, отправьте фото или воспользуйтесь Telegram-ботом @memory_n_more_bot._`
        );
    }
});

// ============================================================================
// Express REST API Server
// ============================================================================
const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Health / Status endpoint
app.get(['/health', '/status', '/api/status'], (_req: Request, res: Response) => {
    res.json({
        success: true,
        status: clientStatus,
        is_ready: clientStatus === 'READY',
        has_qr: clientStatus === 'QR_READY',
        client_info: clientInfo ? {
            name: clientInfo.pushname,
            phone: clientInfo.wid?.user,
            platform: clientInfo.platform
        } : null,
        timestamp: new Date().toISOString()
    });
});

// QR Code View (Web Interface)
app.get('/qr', (_req: Request, res: Response) => {
    if (clientStatus === 'READY' || clientStatus === 'AUTHENTICATED') {
        return res.send(`
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>WhatsApp Bot Connected</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }
                    .card { background: #1e293b; padding: 2.5rem; border-radius: 1rem; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); max-width: 420px; border: 1px solid #334155; }
                    .badge { display: inline-block; background: #22c55e; color: #000; font-weight: bold; padding: 0.4rem 1rem; border-radius: 9999px; margin-bottom: 1.5rem; }
                    h2 { margin: 0 0 0.5rem; }
                    p { color: #94a3b8; line-height: 1.5; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="badge">CONNECTED</div>
                    <h2>WhatsApp Connected!</h2>
                    <p>Logged in as <b>${clientInfo?.pushname || 'Bot Account'}</b> (+${clientInfo?.wid?.user || 'N/A'}).</p>
                    <p>The bot is operational and ready to send and receive messages.</p>
                </div>
            </body>
            </html>
        `);
    }

    if (!latestQrDataUrl) {
        return res.send(`
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta http-equiv="refresh" content="2">
                <title>Generating QR...</title>
                <style>
                    body { font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }
                    .card { background: #1e293b; padding: 2rem; border-radius: 1rem; text-align: center; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Initializing WhatsApp Session...</h2>
                    <p>Waiting for QR code generation. This page will refresh automatically.</p>
                </div>
            </body>
            </html>
        `);
    }

    res.send(`
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="refresh" content="15">
            <title>Scan WhatsApp QR Code</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #0f172a; color: #f8fafc; }
                .card { background: #1e293b; padding: 2.5rem; border-radius: 1.25rem; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.6); max-width: 440px; border: 1px solid #334155; }
                h2 { margin: 0 0 0.5rem; color: #38bdf8; }
                p { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1.5rem; line-height: 1.4; }
                .qr-wrapper { background: #ffffff; padding: 1rem; border-radius: 0.75rem; display: inline-block; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
                .qr-wrapper img { display: block; width: 280px; height: 280px; }
                .steps { text-align: left; background: #0f172a; padding: 1rem 1.25rem; border-radius: 0.75rem; margin-top: 1.5rem; font-size: 0.85rem; color: #cbd5e1; }
                .steps ol { margin: 0; padding-left: 1.2rem; }
                .steps li { margin-bottom: 0.35rem; }
            </style>
        </head>
        <body>
            <div class="card">
                <h2>WhatsApp Web Authorization</h2>
                <p>Scan the QR code below using your dedicated WhatsApp bot phone.</p>
                <div class="qr-wrapper">
                    <img src="${latestQrDataUrl}" alt="WhatsApp QR Code" />
                </div>
                <div class="steps">
                    <ol>
                        <li>Open <b>WhatsApp</b> on your dedicated bot phone</li>
                        <li>Tap <b>Settings (or 3 dots)</b> ➔ <b>Linked Devices</b></li>
                        <li>Tap <b>Link a Device</b> and scan this QR code</li>
                    </ol>
                </div>
            </div>
        </body>
        </html>
    `);
});

// Send Text Message API
app.post(['/send-message', '/api/send-message'], async (req: Request, res: Response) => {
    try {
        const { to, message } = req.body as SendMessagePayload;
        if (!to || !message) {
            return res.status(400).json({ success: false, error: "Missing required fields: 'to' and 'message'" });
        }

        if (clientStatus !== 'READY') {
            return res.status(503).json({ success: false, error: `WhatsApp client is not ready. Current status: ${clientStatus}` });
        }

        const chatId = formatChatId(to);
        const response: any = await client.sendMessage(chatId, message);
        if (response?.id?._serialized) {
            botSentMessageIds.add(response.id._serialized);
        }

        res.json({
            success: true,
            chatId: chatId,
            messageId: response?.id?._serialized,
            timestamp: response?.timestamp
        });
    } catch (err: any) {
        console.error('[API Send Error]', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// Send Media API (from URL or Base64)
app.post(['/send-media', '/api/send-media'], async (req: Request, res: Response) => {
    try {
        const { to, mediaUrl, base64, mimetype, filename, caption } = req.body as SendMediaPayload;
        if (!to || (!mediaUrl && !base64)) {
            return res.status(400).json({ success: false, error: "Missing required fields: 'to' and either 'mediaUrl' or 'base64'" });
        }

        if (clientStatus !== 'READY') {
            return res.status(503).json({ success: false, error: `WhatsApp client is not ready. Current status: ${clientStatus}` });
        }

        const chatId = formatChatId(to);
        let media: MessageMedia;

        if (mediaUrl) {
            media = await MessageMedia.fromUrl(mediaUrl, { unsafeMime: true });
        } else if (base64) {
            media = new MessageMedia(mimetype || 'image/jpeg', base64, filename || 'media.jpg');
        } else {
            return res.status(400).json({ success: false, error: 'No media content provided' });
        }

        const response: any = await client.sendMessage(chatId, media, { caption: caption || '' });
        if (response?.id?._serialized) {
            botSentMessageIds.add(response.id._serialized);
        }

        res.json({
            success: true,
            chatId: chatId,
            messageId: response?.id?._serialized,
            timestamp: response?.timestamp
        });
    } catch (err: any) {
        console.error('[API Send Media Error]', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// Start Express Server
app.listen(PORT, HOST, () => {
    console.log(`[Express] REST API server listening on http://${HOST}:${PORT}`);
});

// Start WhatsApp Client
client.initialize().catch(err => {
    console.error('[WhatsApp Client Error] Initialization failed:', err);
});
