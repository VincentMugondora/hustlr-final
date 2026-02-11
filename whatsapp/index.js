/**
 * WhatsApp Integration for Hustlr
 * Uses Baileys library to connect to WhatsApp Web
 * Handles incoming messages and forwards them to FastAPI backend
 */

const {
    default: makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
    makeCacheableSignalKeyStore,
    Browsers
} = require('@adiwajshing/baileys');
const { Boom } = require('@hapi/boom');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');
const axios = require('axios');
require('dotenv').config();

// Configuration
const AUTH_FOLDER = './auth_info';
const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8000';
const RECONNECT_INTERVAL = 5000; // 5 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

// Ensure auth folder exists
if (!fs.existsSync(AUTH_FOLDER)) {
    fs.mkdirSync(AUTH_FOLDER, { recursive: true });
}

/**
 * Logger utility for consistent logging
 */
class Logger {
    static info(message, ...args) {
        console.log(`📱 [${new Date().toISOString()}] INFO: ${message}`, ...args);
    }

    static error(message, ...args) {
        console.error(`❌ [${new Date().toISOString()}] ERROR: ${message}`, ...args);
    }

    static warn(message, ...args) {
        console.warn(`⚠️  [${new Date().toISOString()}] WARN: ${message}`, ...args);
    }

    static success(message, ...args) {
        console.log(`✅ [${new Date().toISOString()}] SUCCESS: ${message}`, ...args);
    }
}

/**
 * WhatsApp connection manager
 */
class WhatsAppManager {
    constructor() {
        this.sock = null;
        this.reconnectAttempts = 0;
        this.isConnected = false;
        this.authState = null;
    }

    /**
     * Initialize WhatsApp connection
     */
    async initialize() {
        try {
            // Load or create authentication state
            const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
            this.authState = state;

            Logger.info('Initializing WhatsApp connection...');

            // Create WhatsApp socket
            this.sock = makeWASocket({
                auth: {
                    creds: state.creds,
                    keys: makeCacheableSignalKeyStore(state.keys, Logger)
                },
                printQRInTerminal: true,
                browser: Browsers.macOS('Desktop'),
                logger: {
                    level: 'silent' // Reduce Baileys logging noise
                }
            });

            // Bind event handlers
            this.bindEventHandlers(saveCreds);

            Logger.success('WhatsApp manager initialized');

        } catch (error) {
            Logger.error('Failed to initialize WhatsApp manager:', error);
            throw error;
        }
    }

    /**
     * Bind all event handlers
     */
    bindEventHandlers(saveCreds) {
        // Connection updates
        this.sock.ev.on('connection.update', async (update) => {
            await this.handleConnectionUpdate(update, saveCreds);
        });

        // Credentials updates
        this.sock.ev.on('creds.update', saveCreds);

        // Incoming messages
        this.sock.ev.on('messages.upsert', async (m) => {
            await this.handleIncomingMessage(m);
        });

        // Message acknowledgements
        this.sock.ev.on('messages.update', (updates) => {
            this.handleMessageUpdates(updates);
        });

        // Handle disconnections
        this.sock.ev.on('connection.update', (update) => {
            if (update.qr) {
                Logger.info('QR Code received, scan with WhatsApp:');
                qrcode.generate(update.qr, { small: true });
            }
        });
    }

    /**
     * Handle connection updates
     */
    async handleConnectionUpdate(update, saveCreds) {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            Logger.info('QR Code received - scan with WhatsApp app');
            // QR code is automatically printed by Baileys
        }

        if (connection === 'close') {
            this.isConnected = false;
            const shouldReconnect = this.shouldReconnect(lastDisconnect?.error);

            if (shouldReconnect) {
                await this.handleReconnection();
            } else {
                Logger.error('Connection closed permanently');
                process.exit(1);
            }
        } else if (connection === 'open') {
            this.isConnected = true;
            this.reconnectAttempts = 0;
            Logger.success('WhatsApp connected successfully!');

            // Send presence to indicate online status
            await this.sock.sendPresenceUpdate('available');
        }
    }

    /**
     * Determine if reconnection should be attempted
     */
    shouldReconnect(error) {
        if (!error) return true;

        const boom = Boom.isBoom(error) ? error : new Boom(error);
        const disconnectReason = boom?.output?.statusCode;

        // Don't reconnect on logout or banned accounts
        const noReconnectCodes = [
            DisconnectReason.loggedOut,
            DisconnectReason.banned,
            DisconnectReason.notAuthorized
        ];

        if (noReconnectCodes.includes(disconnectReason)) {
            Logger.error(`Not reconnecting due to reason: ${disconnectReason}`);
            return false;
        }

        return this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS;
    }

    /**
     * Handle reconnection logic
     */
    async handleReconnection() {
        this.reconnectAttempts++;
        Logger.warn(`Attempting reconnection ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}...`);

        setTimeout(async () => {
            try {
                await this.initialize();
            } catch (error) {
                Logger.error('Reconnection failed:', error);
                if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                    Logger.error('Max reconnection attempts reached. Exiting...');
                    process.exit(1);
                }
            }
        }, RECONNECT_INTERVAL);
    }

    /**
     * Handle incoming messages
     */
    async handleIncomingMessage(m) {
        try {
            const msg = m.messages[0];
            if (!msg) return;

            // Skip messages from status updates or groups (for now)
            if (msg.key.remoteJid === 'status@broadcast') return;
            if (msg.key.remoteJid.includes('@g.us')) {
                Logger.info('Ignoring group message');
                return;
            }

            // Skip own messages
            if (msg.key.fromMe) return;

            // Extract message content
            const messageContent = this.extractMessageContent(msg);
            if (!messageContent) return;

            const sender = msg.key.remoteJid;
            const messageId = msg.key.id;

            Logger.info(`📨 Message from ${sender}: ${messageContent.substring(0, 100)}...`);

            // Forward to FastAPI backend
            await this.forwardToBackend(sender, messageContent, messageId);

            // Send message acknowledgement
            await this.sock.readMessages([msg.key]);

        } catch (error) {
            Logger.error('Error handling incoming message:', error);
        }
    }

    /**
     * Extract message content from various message types
     */
    extractMessageContent(msg) {
        try {
            const message = msg.message;
            if (!message) return null;

            // Text message
            if (message.conversation) {
                return message.conversation;
            }

            // Extended text message
            if (message.extendedTextMessage) {
                return message.extendedTextMessage.text;
            }

            // Button response
            if (message.buttonsResponseMessage) {
                return message.buttonsResponseMessage.selectedDisplayText;
            }

            // List response
            if (message.listResponseMessage) {
                return message.listResponseMessage.title;
            }

            Logger.warn('Unsupported message type:', Object.keys(message));
            return null;

        } catch (error) {
            Logger.error('Error extracting message content:', error);
            return null;
        }
    }

    /**
     * Forward message to FastAPI backend
     */
    async forwardToBackend(sender, message, messageId) {
        try {
            const payload = {
                sender: sender,
                message: message,
                messageId: messageId,
                timestamp: new Date().toISOString(),
                source: 'whatsapp'
            };

            const response = await axios.post(
                `${FASTAPI_BASE_URL}/api/v1/whatsapp/webhook`,
                payload,
                {
                    timeout: 10000, // 10 second timeout
                    headers: {
                        'Content-Type': 'application/json',
                        'User-Agent': 'Hustlr-WhatsApp/1.0.0'
                    }
                }
            );

            Logger.success(`✅ Message forwarded to backend: ${response.status}`);

        } catch (error) {
            Logger.error('Failed to forward message to backend:', error.message);

            // Could implement retry logic here
            // For now, just log the error
        }
    }

    /**
     * Handle message updates (acknowledgements, etc.)
     */
    handleMessageUpdates(updates) {
        for (const update of updates) {
            if (update.update.messageStubType) {
                Logger.info(`Message update: ${update.update.messageStubType}`);
            }
        }
    }

    /**
     * Send a message (for responses)
     */
    async sendMessage(to, message) {
        try {
            if (!this.isConnected) {
                throw new Error('WhatsApp not connected');
            }

            const result = await this.sock.sendMessage(to, { text: message });
            Logger.success(`📤 Message sent to ${to}`);
            return result;

        } catch (error) {
            Logger.error('Failed to send message:', error);
            throw error;
        }
    }

    /**
     * Graceful shutdown
     */
    async shutdown() {
        Logger.info('Shutting down WhatsApp manager...');

        if (this.sock) {
            this.sock.end();
        }

        Logger.success('WhatsApp manager shut down');
    }
}

/**
 * Main application entry point
 */
async function main() {
    Logger.info('🚀 Starting Hustlr WhatsApp Service...');

    const whatsapp = new WhatsAppManager();

    // Handle graceful shutdown
    process.on('SIGINT', async () => {
        Logger.info('Received SIGINT, shutting down gracefully...');
        await whatsapp.shutdown();
        process.exit(0);
    });

    process.on('SIGTERM', async () => {
        Logger.info('Received SIGTERM, shutting down gracefully...');
        await whatsapp.shutdown();
        process.exit(0);
    });

    try {
        await whatsapp.initialize();
    } catch (error) {
        Logger.error('Failed to start WhatsApp service:', error);
        process.exit(1);
    }
}

// Start the application
if (require.main === module) {
    main().catch((error) => {
        Logger.error('Unhandled error:', error);
        process.exit(1);
    });
}

module.exports = { WhatsAppManager, Logger };