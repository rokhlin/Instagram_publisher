/**
 * Backend Client for WhatsApp Connector.
 * Communicates with the central Python backend (Business Logic & AI Engine layers).
 * Delegates AI caption generation, refinements, and prompts to the shared backend.
 */

import axios from 'axios';
import { PYTHON_BACKEND_URL } from './config';

export interface BackendStatus {
    success: boolean;
    service?: string;
    ai_provider?: string;
    storage_type?: string;
    instagram_account_id?: string | null;
}

export async function getBackendStatus(): Promise<BackendStatus | null> {
    if (!PYTHON_BACKEND_URL) return null;
    try {
        const res = await axios.get<BackendStatus>(`${PYTHON_BACKEND_URL}/api/status`, {
            timeout: 5000
        });
        return res.data;
    } catch {
        return null;
    }
}

export async function generateCaption(
    instructions: string,
    imageBase64: string | null = null,
    mimeType: string = 'image/jpeg',
    postFormat: string = 'FEED_PORTRAIT',
    language: string = 'ru'
): Promise<string> {
    // 1. Delegate to shared Python AI Engine & Business Logic layer
    if (PYTHON_BACKEND_URL) {
        try {
            const res = await axios.post<{ success: boolean; caption: string; provider?: string }>(
                `${PYTHON_BACKEND_URL}/api/ai/generate-caption`,
                {
                    instructions,
                    imageBase64,
                    mimeType,
                    postFormat,
                    language
                },
                { timeout: 30000 }
            );

            if (res.data && res.data.caption) {
                return res.data.caption.trim();
            }
        } catch (err: any) {
            console.warn(`[Backend AI API] Failed to reach Python AI Engine at ${PYTHON_BACKEND_URL}: ${err.message}. Using fallback.`);
        }
    }

    // 2. Local fallback if Python backend is temporarily unreachable
    return (
        `✨ *Новый день — новые воспоминания!* 🌿\n\n` +
        `${instructions ? `Тема: ${instructions}\n\n` : ''}` +
        `Сохраняем самые яркие и душевные моменты, которые остаются в сердце навсегда. ` +
        `Каждый кадр — это маленькая история, наполненная теплом и вдохновением. ✨\n\n` +
        `А какие моменты этой недели запомнились вам больше всего? Делитесь в комментариях! 👇\n\n` +
        `#семья #воспоминания #уют #моменты #фотодня #вдохновение #счастье #family #memories #lifestyle`
    );
}

export async function refineCaption(
    currentCaption: string,
    correctionInstructions: string,
    postFormat: string = 'FEED_PORTRAIT',
    language: string = 'ru'
): Promise<string> {
    if (PYTHON_BACKEND_URL) {
        try {
            const res = await axios.post<{ success: boolean; caption: string }>(
                `${PYTHON_BACKEND_URL}/api/ai/refine-caption`,
                {
                    currentCaption,
                    correctionInstructions,
                    postFormat,
                    language
                },
                { timeout: 30000 }
            );

            if (res.data && res.data.caption) {
                return res.data.caption.trim();
            }
        } catch (err: any) {
            console.warn(`[Backend AI API] Failed to refine caption via backend: ${err.message}`);
        }
    }

    return `${currentCaption}\n\n[Дополнение: ${correctionInstructions}]`;
}
