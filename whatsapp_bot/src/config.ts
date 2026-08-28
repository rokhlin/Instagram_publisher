/**
 * Configuration & Environment loader for WhatsApp Connector.
 */

import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';

// Load from root config/.env and local .env fallbacks
dotenv.config({ path: path.resolve(__dirname, '../../config/.env') });
dotenv.config();

export const PORT = parseInt(process.env.WHATSAPP_PORT || process.env.PORT || '3019', 10);
export const HOST = process.env.WHATSAPP_HOST || '0.0.0.0';

// Directories
export const DEFAULT_AUTH_DIR = path.resolve(__dirname, '../../data/whatsapp_auth');
export const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || DEFAULT_AUTH_DIR;

export const DEFAULT_MEDIA_DIR = path.resolve(__dirname, '../../data/media');
export const MEDIA_DIR = process.env.LOCAL_STORAGE_DIR || DEFAULT_MEDIA_DIR;

// Allowed WhatsApp numbers (format: comma-separated international numbers without +)
export const ALLOWED_NUMBERS: string[] = (process.env.WHATSAPP_ALLOWED_NUMBERS || '')
    .split(',')
    .map(n => n.trim().replace(/[^0-9]/g, ''))
    .filter(Boolean);

// App & Service configs
export const IG_USER_ID = process.env.IG_USER_ID || '';
export const STORAGE_TYPE = (process.env.STORAGE_TYPE || 'r2').toUpperCase();
export const GEMINI_API_KEY = process.env.GEMINI_API_KEY || '';
export const R2_PUBLIC_DOMAIN = process.env.R2_PUBLIC_DOMAIN || '';
export const S3_PUBLIC_DOMAIN = process.env.S3_PUBLIC_DOMAIN || '';
export const LOCAL_PUBLIC_BASE_URL = process.env.LOCAL_PUBLIC_BASE_URL || '';
export const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || '';
export const PUPPETEER_EXECUTABLE_PATH = process.env.PUPPETEER_EXECUTABLE_PATH || undefined;

// Ensure directories exist
if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
}
if (!fs.existsSync(MEDIA_DIR)) {
    fs.mkdirSync(MEDIA_DIR, { recursive: true });
}

// Remove stale Chromium SingletonLock files left by container recreations/restarts
export function cleanStaleSingletonLocks(dir: string): void {
    try {
        if (!fs.existsSync(dir)) return;
        const entries = fs.readdirSync(dir, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
                cleanStaleSingletonLocks(fullPath);
            } else if (
                entry.name.startsWith('SingletonLock') ||
                entry.name.startsWith('SingletonSocket') ||
                entry.name.startsWith('SingletonCookie')
            ) {
                try {
                    fs.unlinkSync(fullPath);
                    console.log(`[Auth Cleanup] Removed stale lock: ${fullPath}`);
                } catch {
                    // Ignore deletion errors on locked files
                }
            }
        }
    } catch {
        // Ignore read errors
    }
}
