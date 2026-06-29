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

### 6. Test Sprint 0 Flow

1. Open the frontend URL, usually `http://localhost:3000`.
2. Open `Characters`.
3. Create a character.
4. Open the character chat.
5. Send a message.
6. Confirm that a mock AI response appears.
7. Refresh the chat page.
8. Confirm that message history is still visible.

Sprint 0 uses mock providers only. Real AI APIs are intentionally not connected.

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
- `POST /voice/stt`
- `GET /limits`

## Notes

The backend creates tables automatically on startup for Sprint 0 convenience. A production setup should replace this with migrations.
