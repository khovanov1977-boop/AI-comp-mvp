# AI Companion MVP

Sprint 0 skeleton for an AI Companion web app.

## Stack

- Frontend: Next.js
- Backend: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- AI providers: local mock providers only

## What Works In Sprint 0

- Create a character
- See character cards
- Open a character chat
- Send a text message
- Get a mock AI response
- Store user and assistant messages in PostgreSQL
- Load chat history in the frontend

Real LLM, image, video, voice, auth, payments, realtime voice, live avatar, and LoRA are intentionally not included yet.

## Project Structure

```text
apps/
  api/       FastAPI backend
  web/       Next.js frontend
packages/
  shared/    Shared TypeScript types
docs/
```

## Prerequisites

- Node.js 20+
- Python 3.11+
- Docker Desktop

## Local Run

1. Copy environment variables:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

2. Start PostgreSQL:

```bash
docker compose up -d db
```

3. Start the backend:

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

macOS/Linux activation:

```bash
source .venv/bin/activate
```

4. Start the frontend in a second terminal:

```bash
npm install
npm run dev:web
```

5. Open:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health

## API

- `GET /health`
- `POST /characters`
- `GET /characters`
- `GET /characters/{character_id}`
- `GET /chat/{character_id}`
- `POST /chat`
- `POST /media/image`
- `POST /media/video`
- `GET /media/{character_id}`
- `POST /voice/tts`
- `POST /voice/stt`
- `GET /limits`

## Notes

The backend creates tables automatically on startup for Sprint 0 convenience. A production setup should replace this with migrations.
