# Hustlr

A WhatsApp-based service marketplace platform built with FastAPI, MongoDB, and AWS Bedrock AI.

## Overview

Hustlr connects customers with local service providers through WhatsApp messaging, using AI-powered conversational assistance for seamless booking and management.

## Features

- **WhatsApp Integration**: Baileys library for messaging
- **AI-Powered Conversations**: AWS Bedrock Agent for intent recognition
- **User Management**: JWT-based authentication with role-based access
- **Service Providers**: Registration, verification, and management
- **Booking System**: Create, manage, and track service bookings
- **Admin Dashboard**: Provider verification and system oversight

## Project Structure

```
hustlr/
├── backend/           # FastAPI application
│   ├── routes/        # API route handlers
│   ├── models.py      # Pydantic data models
│   ├── auth.py        # JWT authentication utilities
│   ├── db.py          # MongoDB connection and setup
│   └── main.py        # FastAPI app entry point
├── whatsapp/          # Baileys WhatsApp integration
├── bedrock/           # AWS Bedrock agent configurations
├── tests/             # Unit and integration tests
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Setup

1. **Prerequisites**:
   - Python 3.11+
   - MongoDB (local or cloud)
   - Node.js 18+ (for WhatsApp integration)
   - AWS account (for Bedrock)

2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up WhatsApp Integration** (Optional):
   ```bash
   cd whatsapp
   npm install
   cp .env.example .env
   # Edit .env with your FastAPI URL
   npm start
   ```

4. **Environment Variables**:
   Create a `.env` file in the root directory with:
   ```
   MONGO_URI=mongodb://localhost:27017
   SECRET_KEY=your-secret-key-here
   AWS_REGION=us-east-1
   HUSTLR_AGENT_ID=your-bedrock-agent-id
   HUSTLR_AGENT_ALIAS_ID=TSTALIASID
   ```

5. **Run the Application**:
   ```bash
   cd backend
   python main.py
   ```

   The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - User login

### Service Providers
- `POST /api/v1/providers/register` - Register as provider
- `GET /api/v1/providers/search` - Search providers
- `GET /api/v1/providers/{id}` - Get provider details

### Bookings
- `POST /api/v1/bookings` - Create booking
- `GET /api/v1/bookings` - Get user bookings
- `PUT /api/v1/bookings/{id}/status` - Update booking status

### WhatsApp Integration
- `POST /api/v1/whatsapp/webhook` - Receive WhatsApp messages
- `GET /api/v1/whatsapp/health` - WhatsApp integration health check

### Admin
- `GET /api/v1/admin/providers/pending` - Get pending verifications
- `PUT /api/v1/admin/providers/{id}/verify` - Verify provider
- `GET /api/v1/admin/stats` - System statistics

### General
- `GET /health` - API health check
- `GET /` - API information

## Development

- Run tests: `pytest`
- Format code: Follow PEP8 guidelines
- Use async/await for database operations
- Ensure all endpoints are secured with JWT

## Security

- Passwords are hashed using bcrypt
- JWT tokens for authentication
- Role-based access control
- Input validation with Pydantic

## License

This project is part of the Hustlr platform development.