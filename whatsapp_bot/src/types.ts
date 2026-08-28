/**
 * Type definitions for MemoryNMore WhatsApp Connector.
 */

export type ClientStatus =
    | 'INITIALIZING'
    | 'QR_READY'
    | 'AUTHENTICATED'
    | 'READY'
    | 'DISCONNECTED';

export interface UserMediaSession {
    filename: string;
    filepath: string;
    mimetype: string;
    base64: string;
    timestamp: number;
}

export interface ClientInfoData {
    name?: string;
    phone?: string;
    platform?: string;
}

export interface StatusResponse {
    success: boolean;
    status: ClientStatus;
    is_ready: boolean;
    has_qr: boolean;
    client_info: ClientInfoData | null;
    timestamp: string;
}

export interface SendMessagePayload {
    to: string;
    message: string;
}

export interface SendMediaPayload {
    to: string;
    mediaUrl?: string;
    base64?: string;
    mimetype?: string;
    filename?: string;
    caption?: string;
}
