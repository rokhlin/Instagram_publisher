/**
 * Internationalization (i18n) Engine for WhatsApp Connector.
 */

import ruLocale from './locales/ru.json';
import enLocale from './locales/en.json';

export type SupportedLanguage = 'ru' | 'en';

const LOCALES: Record<SupportedLanguage, any> = {
    ru: ruLocale,
    en: enLocale
};

let currentLanguage: SupportedLanguage = 'ru';

export function setLanguage(lang: string): void {
    currentLanguage = lang.toLowerCase().startsWith('en') ? 'en' : 'ru';
}

export function getLanguage(): SupportedLanguage {
    return currentLanguage;
}

export function t(key: string, params?: Record<string, string | number>, lang?: string): string {
    const targetLang: SupportedLanguage = lang ? (lang.toLowerCase().startsWith('en') ? 'en' : 'ru') : currentLanguage;
    const locale = LOCALES[targetLang] || LOCALES.ru;

    const keys = key.split('.');
    let val: any = locale;

    for (const k of keys) {
        if (val && typeof val === 'object' && k in val) {
            val = val[k];
        } else {
            val = null;
            break;
        }
    }

    // Fallback to Russian if not found
    if (val === null && targetLang !== 'ru') {
        let fallbackVal: any = LOCALES.ru;
        for (const k of keys) {
            if (fallbackVal && typeof fallbackVal === 'object' && k in fallbackVal) {
                fallbackVal = fallbackVal[k];
            } else {
                fallbackVal = null;
                break;
            }
        }
        val = fallbackVal;
    }

    if (val === null || val === undefined) {
        return key;
    }

    let result = String(val);
    if (params) {
        for (const [paramKey, paramVal] of Object.entries(params)) {
            result = result.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), String(paramVal));
        }
    }

    return result;
}
