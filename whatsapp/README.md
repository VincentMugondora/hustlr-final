# WhatsApp Integration for Hustlr

This directory contains the WhatsApp integration using Baileys library for the Hustlr platform.

## Files

- `index.js` - Main WhatsApp connection and message handling
- `package.json` - Node.js dependencies and scripts
- `.env.example` - Environment variables template

## Setup

1. **Install Dependencies**:
   ```bash
   cd whatsapp
   npm install
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and configure:
   ```env
   FASTAPI_BASE_URL=http://localhost:8000
   ```

3. **Run the Service**:
   ```bash
   npm start
   ```

   For development with auto-restart:
   ```bash
   npm run dev
   ```

## Features

- **QR Code Authentication**: Scan QR code for initial WhatsApp Web login
- **Persistent Sessions**: Multi-file auth state for session persistence
- **Message Forwarding**: Automatically forwards incoming messages to FastAPI backend
- **Reconnection Handling**: Automatic reconnection on connection loss
- **Error Recovery**: Comprehensive error handling and logging
- **Message Acknowledgements**: Proper message read receipts

## Message Flow

```
WhatsApp → Baileys → index.js → FastAPI (/api/v1/whatsapp/webhook) → Bedrock Agent → Response → WhatsApp
```

## Security Considerations

- **Session Storage**: Auth files are stored locally (add to .gitignore)
- **Rate Limiting**: Implement rate limiting in production
- **Message Validation**: Validate incoming messages before processing
- **Error Handling**: Don't expose internal errors to users

## Production Deployment

- Use PM2 or similar process manager
- Set up proper logging (Winston recommended)
- Configure health checks
- Monitor memory usage (Baileys can be memory-intensive)
- Set up backup/restore for auth state

## Troubleshooting

- **QR Code not appearing**: Check console output, ensure no existing session
- **Connection issues**: Check internet connection, WhatsApp Web status
- **Backend forwarding fails**: Verify FastAPI is running and endpoint exists
- **Memory usage**: Monitor and restart periodically if needed