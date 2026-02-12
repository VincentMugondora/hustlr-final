/**
 * WhatsApp Integration for Hustlr
 * Uses Baileys to receive WhatsApp messages and round-trip them through FastAPI + Bedrock.
 */

const {
    default: makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
    makeCacheableSignalKeyStore,
    Browsers,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const axios = require('axios');
require('dotenv').config();

const AUTH_FOLDER = './auth_info';
const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8000';
const FASTAPI_TIMEOUT_MS = parseInt(process.env.FASTAPI_TIMEOUT_MS || '15000', 10);
const RECONNECT_INTERVAL = parseInt(process.env.RECONNECT_INTERVAL || '5000', 10);
const MAX_RECONNECT_ATTEMPTS = parseInt(process.env.MAX_RECONNECT_ATTEMPTS || '10', 10);
const FORWARD_RETRY_ATTEMPTS = parseInt(process.env.FORWARD_RETRY_ATTEMPTS || '3', 10);
const FORWARD_RETRY_DELAY_MS = parseInt(process.env.FORWARD_RETRY_DELAY_MS || '1000', 10);

const FALLBACK_REPLY =
    'Sorry, I am having trouble processing your request right now. Please try again in a moment.';

if (!fs.existsSync(AUTH_FOLDER)) {
    fs.mkdirSync(AUTH_FOLDER, { recursive: true });
}

const backendClient = axios.create({
    baseURL: FASTAPI_BASE_URL,
    timeout: FASTAPI_TIMEOUT_MS,
    headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Hustlr-WhatsApp/1.0.0',
    },
});

class Logger {
    static info(message, ...args) {
        console.log(`[${new Date().toISOString()}] INFO: ${message}`, ...args);
    }

    static warn(message, ...args) {
        console.warn(`[${new Date().toISOString()}] WARN: ${message}`, ...args);
    }

    static error(message, ...args) {
        console.error(`[${new Date().toISOString()}] ERROR: ${message}`, ...args);
    }
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

class WhatsAppManager {
    constructor() {
        this.sock = null;
        this.reconnectAttempts = 0;
        this.isConnected = false;
    }

    async initialize() {
        const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);

        Logger.info('Initializing WhatsApp connection');

        this.sock = makeWASocket({
            auth: {
                creds: state.creds,
                keys: makeCacheableSignalKeyStore(state.keys, console),
            },
            printQRInTerminal: true,
            browser: Browsers.macOS('Desktop'),
            logger: { level: 'silent' },
        });

        this.bindEventHandlers(saveCreds);
        Logger.info('WhatsApp manager initialized');
    }

    bindEventHandlers(saveCreds) {
        this.sock.ev.on('connection.update', async (update) => {
            await this.handleConnectionUpdate(update);
            if (update.qr) {
                Logger.info('QR code generated. Scan in WhatsApp app.');
                qrcode.generate(update.qr, { small: true });
            }
        });

        this.sock.ev.on('creds.update', saveCreds);

        this.sock.ev.on('messages.upsert', async (event) => {
            await this.handleIncomingMessage(event);
        });

        this.sock.ev.on('messages.update', (updates) => {
            this.handleMessageUpdates(updates);
        });
    }

    async handleConnectionUpdate(update) {
        const { connection, lastDisconnect } = update;

        if (connection === 'open') {
            this.isConnected = true;
            this.reconnectAttempts = 0;
            Logger.info('WhatsApp connected');
            await this.sock.sendPresenceUpdate('available');
            return;
        }

        if (connection !== 'close') {
            return;
        }

        this.isConnected = false;
        const shouldReconnect = this.shouldReconnect(lastDisconnect?.error);

        if (!shouldReconnect) {
            Logger.error('Connection closed permanently');
            process.exit(1);
            return;
        }

        await this.handleReconnection();
    }

    shouldReconnect(error) {
        if (!error) return true;

        const boom = Boom.isBoom(error) ? error : new Boom(error);
        const disconnectReason = boom?.output?.statusCode;

        const noReconnectCodes = [
            DisconnectReason.loggedOut,
            DisconnectReason.banned,
            DisconnectReason.notAuthorized,
        ];

        if (noReconnectCodes.includes(disconnectReason)) {
            Logger.error(`Not reconnecting due to disconnect reason: ${disconnectReason}`);
            return false;
        }

        return this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS;
    }

    async handleReconnection() {
        this.reconnectAttempts += 1;
        Logger.warn(
            `Reconnect attempt ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS} in ${RECONNECT_INTERVAL}ms`
        );

        await sleep(RECONNECT_INTERVAL);
        await this.initialize();
    }

    async handleIncomingMessage(event) {
        const incoming = event.messages?.[0];
        if (!incoming) return;

        const remoteJid = incoming.key?.remoteJid;
        const messageId = incoming.key?.id || 'unknown';

        if (!remoteJid || remoteJid === 'status@broadcast') return;
        if (remoteJid.includes('@g.us')) return;
        if (incoming.key?.fromMe) return;

        const messageText = this.extractMessageContent(incoming);
        if (!messageText || !messageText.trim()) {
            Logger.warn(`Skipping empty/unsupported message id=${messageId}`);
            return;
        }

        Logger.info(`Incoming message id=${messageId} sender=${remoteJid}`);

        let reply = FALLBACK_REPLY;
        try {
            const backendResult = await this.forwardToBackend({
                sender: remoteJid,
                message: messageText.trim(),
                messageId,
            });

            if (backendResult.replyText && backendResult.replyText.trim()) {
                reply = backendResult.replyText.trim();
            }
        } catch (error) {
            Logger.error(`Backend forwarding failed id=${messageId}: ${error.message}`);
        }

        try {
            await this.sendReply(remoteJid, reply);
            await this.sock.readMessages([incoming.key]);
            Logger.info(`Message acknowledged id=${messageId}`);
        } catch (error) {
            Logger.error(`Failed to send/ack reply id=${messageId}: ${error.message}`);
        }
    }

    extractMessageContent(msg) {
        const message = msg.message;
        if (!message) return null;

        if (message.conversation) return message.conversation;
        if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
        if (message.buttonsResponseMessage?.selectedDisplayText) {
            return message.buttonsResponseMessage.selectedDisplayText;
        }
        if (message.listResponseMessage?.title) return message.listResponseMessage.title;

        Logger.warn(`Unsupported message type: ${Object.keys(message).join(', ')}`);
        return null;
    }

    async forwardToBackend({ sender, message, messageId }) {
        const payload = {
            sender,
            message,
            messageId,
            timestamp: new Date().toISOString(),
            source: 'whatsapp',
        };

        let lastError;

        for (let attempt = 1; attempt <= FORWARD_RETRY_ATTEMPTS; attempt += 1) {
            try {
                const response = await backendClient.post('/api/v1/whatsapp/webhook', payload);
                const data = response.data || {};

                Logger.info(
                    `Backend processed message id=${messageId} status=${response.status} success=${data.success}`
                );

                return {
                    success: Boolean(data.success),
                    replyText: data.reply_text || FALLBACK_REPLY,
                };
            } catch (error) {
                lastError = error;
                const status = error?.response?.status;
                Logger.warn(
                    `Backend attempt ${attempt}/${FORWARD_RETRY_ATTEMPTS} failed id=${messageId} status=${status || 'n/a'}`
                );

                if (attempt < FORWARD_RETRY_ATTEMPTS) {
                    await sleep(FORWARD_RETRY_DELAY_MS * attempt);
                }
            }
        }

        throw lastError || new Error('Backend forwarding failed after retries');
    }

    async sendReply(to, message) {
        if (!this.isConnected) {
            throw new Error('WhatsApp client is not connected');
        }

        await this.sock.sendPresenceUpdate('composing', to);
        await this.sock.sendMessage(to, { text: message });
        await this.sock.sendPresenceUpdate('paused', to);

        Logger.info(`Reply sent to ${to}`);
    }

    handleMessageUpdates(updates) {
        for (const update of updates) {
            if (update?.update?.status) {
                Logger.info(`Message status update id=${update.key?.id || 'unknown'} status=${update.update.status}`);
            }
        }
    }

    async shutdown() {
        Logger.info('Shutting down WhatsApp manager');
        if (this.sock) {
            this.sock.end();
        }
    }
}

async function main() {
    Logger.info('Starting Hustlr WhatsApp service');

    const whatsapp = new WhatsAppManager();

    process.on('SIGINT', async () => {
        await whatsapp.shutdown();
        process.exit(0);
    });

    process.on('SIGTERM', async () => {
        await whatsapp.shutdown();
        process.exit(0);
    });

    try {
        await whatsapp.initialize();
    } catch (error) {
        Logger.error(`Failed to start WhatsApp service: ${error.message}`);
        process.exit(1);
    }
}

if (require.main === module) {
    main().catch((error) => {
        Logger.error(`Unhandled error: ${error.message}`);
        process.exit(1);
    });
}

module.exports = { WhatsAppManager, Logger };
