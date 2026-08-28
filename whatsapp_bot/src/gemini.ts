/**
 * Google Gemini AI caption generation for WhatsApp connector.
 */

import axios from 'axios';
import { GEMINI_API_KEY } from './config';

const SYSTEM_PROMPT = `Вы — профессиональный SMM-копирайтер и контент-мейкер для теплого, эстетичного личного блога в Instagram.
Темы блога:
1. Семья и душевность: искренние моменты, детские эмоции, семейные традиции и уют.
2. Путешествия и воспоминания: красивые виды, впечатления от новых мест, путевые заметки.
3. Природа и гармония: пейзажи, закаты, море, прогулки, спокойствие.
4. Отдых и развлечения: яркие выходные, активности, досуг.

Ваша задача — создать вовлекающий, эстетичный пост для Instagram на основе переданной темы/пожеланий и прикрепленного изображения.
Формат поста:
- Яркий заголовок с эмодзи.
- Основной текст (1-2 коротких абзаца, живой, теплый, атмосферный стиль).
- Интерактивный вопрос или призыв к действию в конце.
- Блок хештегов (5-10 релевантных хештегов на русском и английском языках).
Общая длина текста: лаконично, в пределах 600 символов. Язык: РУССКИЙ.`;

const MODELS_TO_TRY = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash'];

export async function generateGeminiCaption(
    instructions: string,
    imageBase64: string | null = null,
    mimeType: string = 'image/jpeg'
): Promise<string> {
    if (!GEMINI_API_KEY) {
        return (
            `✨ *Новый день — новые воспоминания!* 🌿\n\n` +
            `${instructions ? `Тема: ${instructions}\n\n` : ''}` +
            `Сохраняем самые яркие и душевные моменты, которые остаются в сердце навсегда. ` +
            `Каждый кадр — это маленькая история, наполненная теплом и вдохновением. ✨\n\n` +
            `А какие моменты этой недели запомнились вам больше всего? Делитесь в комментариях! 👇\n\n` +
            `#семья #воспоминания #уют #моменты #фотодня #вдохновение #счастье #family #memories #lifestyle`
        );
    }

    for (const model of MODELS_TO_TRY) {
        try {
            const parts: any[] = [];
            if (imageBase64) {
                parts.push({
                    inline_data: {
                        mime_type: mimeType,
                        data: imageBase64
                    }
                });
            }
            parts.push({
                text: `System Prompt: ${SYSTEM_PROMPT}\n\nUser Instructions/Theme: ${instructions || 'Создай душевный пост для публикации'}\n\nСгенерируй готовый пост:`
            });

            const res = await axios.post(
                `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`,
                { contents: [{ parts }] },
                { timeout: 15000 }
            );

            const caption = res.data?.candidates?.[0]?.content?.parts?.[0]?.text;
            if (caption && typeof caption === 'string') {
                return caption.trim();
            }
        } catch (err: any) {
            console.warn(`[Gemini API] Model ${model} failed (${err.message}), trying next fallback...`);
        }
    }

    return (
        `✨ *Новый день — новые воспоминания!* 🌿\n\n` +
        `${instructions ? `Тема: ${instructions}\n\n` : ''}` +
        `Каждый кадр хранит теплоту и радость настоящего момента. ✨\n\n` +
        `#семья #воспоминания #моменты #фотодня #family #memories`
    );
}
