# WhatsApp Integration for Hustlr

This directory contains the WhatsApp integration using Baileys for the Hustlr platform.

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
   FASTAPI_TIMEOUT_MS=15000
   FORWARD_RETRY_ATTEMPTS=3
   FORWARD_RETRY_DELAY_MS=1000
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

- QR code authentication for initial WhatsApp Web login
- Persistent sessions using multi-file auth state
- Automatic forwarding of user messages to FastAPI backend
- FastAPI webhook invokes Bedrock agent and returns `reply_text`
- Baileys sends agent reply back to the user
- Retry, timeout, acknowledgement, and structured logging
- Automatic reconnection on transient disconnects

## Message Flow

```
WhatsApp User
  -> Baileys (`whatsapp/index.js`)
  -> FastAPI (`POST /api/v1/whatsapp/webhook`)
  -> Bedrock (`invoke_agent`)
  -> FastAPI returns `reply_text`
  -> Baileys sends response to WhatsApp user
```

## Production Notes

- Store auth state securely and never commit auth files.
- Keep timeout and retry settings conservative to avoid duplicate sends.
- Monitor logs for backend latency spikes and repeated forward failures.
- Consider adding external monitoring and process supervision (PM2/systemd).

## Troubleshooting

- **QR code not appearing**: Ensure no stale auth session and check console output.
- **No WhatsApp reply**: Verify FastAPI webhook response includes `reply_text`.
- **Backend forwarding fails**: Check FastAPI URL, service health, and network path.
- **Frequent reconnects**: Check WhatsApp session validity and network stability.
