# AI-comp-mvp

Работающий сайт AI Companion: [aicomp.fun](https://aicomp.fun). Пользователь создаёт персонажей и общается с ними текстом и голосом, получает фото и видео, ведёт личную историю переписки. На главной странице открыт каталог из десяти готовых персонажей; общение и копирование образца требуют регистрации.

## Документы, с которых начать

- [Актуальная карта проекта](docs/PROJECT_STATUS.md) — состояние на 24 октября 2026 года, функции, лимиты, модели, архитектура, пути и нерешённые вопросы.
- [Как управлять сайтом](docs/SITE_OPERATIONS.md) ([PDF](output/pdf/AI-comp-mvp_site_operations.pdf)) — PuTTY, ключ, Pageant, сервер, обновления, резервные копии, журналы и типовые проверки.
- [Исходная схема публикации](docs/production-deployment.md) — подробности первоначального развёртывания; для ежедневной работы используйте инструкцию выше.
- [Готовые персонажи](docs/example-characters.md) — каталог и правила создания образцов.

## Основные части

| Часть | Технология | Путь |
| --- | --- | --- |
| Сайт | Next.js, React | `apps/web` |
| API | FastAPI, Python | `apps/api` |
| База | PostgreSQL | контейнер `db` |
| Общие типы | TypeScript | `packages/shared` |
| Публикация | Docker Compose, Caddy | `compose.production.yml`, `deploy/Caddyfile.production` |

Рабочая ветка — `main`. Локальный проект находится в `C:\Users\ASUS\Documents\AI-comp-mvp`; серверная копия — `/home/appadmin/ai-companion`. Секреты хранятся только в локальном `.env` и серверном `.env.production`, оба файла не входят в Git.

## Локальный запуск в Windows

Нужны Docker Desktop, Node.js, Python 3.12 и Git. Из корня проекта:

```powershell
docker compose up -d db
```

В первом окне PowerShell запустите API:

```powershell
cd C:\Users\ASUS\Documents\AI-comp-mvp\apps\api
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Во втором окне запустите сайт:

```powershell
cd C:\Users\ASUS\Documents\AI-comp-mvp
npm run dev:web
```

Откройте `http://localhost:3000`; API отвечает на `http://localhost:8000/health`. Если зависимости ещё не установлены: `npm install` в корне проекта, `python -m venv .venv` и `.venv\Scripts\python.exe -m pip install -r requirements.txt` в `apps/api`. Для локальных ключей и настроек используйте `.env.example` как образец; существующий `.env` не перезаписывайте.

Локальный Compose поднимает базу для разработки. Публичный сайт работает по отдельному `compose.production.yml`; локальные аккаунты и медиа на сервер не переносились.
