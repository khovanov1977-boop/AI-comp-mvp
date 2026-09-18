# AI Companion MVP

An AI Companion web app with persistent characters, structured roleplay, memory, emotional state, and text and voice conversations.

## Stack

- Frontend: Next.js
- Backend: FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- AI providers: mock or OpenAI-compatible LLM, OpenRouter STT, and OpenRouter TTS

## Current MVP Capabilities

- Create a character
- See character cards
- Open a character chat
- Send a text message
- Record, store, and play user voice messages
- Transcribe user voice messages through OpenRouter and send them to the character
- Get a structured character response from a mock or configured real LLM
- Generate character voice replies and retry failed transcription or voice generation
- Store user and assistant messages in PostgreSQL
- Load chat history in the frontend

Auth, payments, realtime voice, live avatar, and LoRA are not included yet.

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

- Docker Desktop
- Node.js 20+
- Python 3.12
- Git

## Windows Local Run

Run the project from:

```powershell
C:\Users\ASUS\Documents\AI-comp-mvp
```

### 1. Copy Environment Variables

From the project root:

```powershell
Copy-Item .env.example .env
```

Skip this command if `.env` already exists.

For the currently recommended hosted LLM baseline, set:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your_openrouter_key
LLM_MODEL=mistralai/mistral-small-2603
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=500
```

When `STT_BASE_URL`, `STT_API_KEY`, `TTS_BASE_URL`, and `TTS_API_KEY` are empty, the speech providers reuse the OpenRouter URL and API key above.

### 2. Start PostgreSQL

Open Docker Desktop first and wait until Docker Engine is running.

From the project root:

```powershell
docker compose up -d db
```

Check the database container:

```powershell
docker compose ps db
```

Expected status: `Up ... (healthy)` with port `5432` exposed.

### 3. Start Backend

Open a PowerShell window for the backend:

```powershell
cd C:\Users\ASUS\Documents\AI-comp-mvp\apps\api
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Keep this PowerShell window open while using the app.

The backend uses `.venv\Scripts\python.exe` directly. You do not need to activate the virtual environment.

### 4. Check Backend Health

Open this URL in a browser:

```text
http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### 5. Start Frontend

Open a second PowerShell window for the frontend:

```powershell
cd C:\Users\ASUS\Documents\AI-comp-mvp
npm install
npm run dev:web
```

Keep this PowerShell window open while using the app.

Next.js usually starts on:

```text
http://localhost:3000
```

If port `3000` is already occupied, Next.js may start on:

```text
http://localhost:3001
```

Use the URL shown in the frontend PowerShell output.

### 6. Test The Basic Flow

1. Open the frontend URL, usually `http://localhost:3000`.
2. Open `Characters`.
3. Create a character.
4. Open the character chat.
5. Send a message.
6. Confirm that a character response appears.
7. Refresh the chat page.
8. Confirm that message history is still visible.

The default example configuration uses the mock LLM. Configure the hosted baseline above to test the real LLM and speech providers.

## Troubleshooting

### PowerShell Blocks Activate.ps1

You do not need to run:

```powershell
.venv\Scripts\activate
```

Use the virtual environment Python directly:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Port 3000 Is Occupied

If Next.js says:

```text
Port 3000 is in use, trying 3001 instead.
```

Open the URL shown by Next.js, for example:

```text
http://localhost:3001
```

To find a process using port `3000`:

```powershell
netstat -ano | findstr :3000
```

To stop a known process:

```powershell
taskkill /PID <PID> /F
```

### Docker Desktop Is Not Running

If Docker commands fail with a message about the Docker API or Docker Engine, open Docker Desktop and wait until it is running.

Then retry:

```powershell
docker compose up -d db
docker compose ps db
```

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
- `POST /voice/messages/{character_id}`
- `POST /voice/messages/{message_id}/retry`
- `GET /limits`

## Notes

The backend creates tables automatically on startup for Sprint 0 convenience. A production setup should replace this with migrations.
Recorded voice files are stored locally under `apps/api/data/voice` and are excluded from Git. Voice transcription and character voice generation use the configured OpenRouter credentials.
