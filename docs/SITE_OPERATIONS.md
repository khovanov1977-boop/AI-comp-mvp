# Как управлять сайтом aicomp.fun

Практическая памятка для владельца. Состояние доступа проверено **24 октября 2026 года**. Архитектура и параметры продукта собраны в [карте проекта](PROJECT_STATUS.md). Пароли и ключи здесь не записаны.

## Где что находится

| Объект | Значение |
| --- | --- |
| Сайт | `https://aicomp.fun` |
| Проверка API | `https://aicomp.fun/api/health` → `{"status":"ok"}` |
| VPS | REG.RU, IP `194.226.112.63` |
| Вход по SSH | Пользователь `appadmin`, порт `22` |
| Сохранённая сессия PuTTY на этом ПК | `regcloud-appadmin` |
| Личный ключ PuTTY на этом ПК | `C:\Users\ASUS\Documents\Эксперименты с ИИ\puttykeyaicomp.ppk` |
| Программа командного входа | `C:\Program Files\PuTTY\plink.exe` |
| Проект на сервере | `/home/appadmin/ai-companion` |
| Резервные копии на сервере | `/home/appadmin/ai-companion-backups` |

Ключевой файл **лежит на вашем компьютере**, а не в репозитории. На сервере у `appadmin` записан соответствующий публичный ключ. Парольная фраза защищает локальный PPK; она не должна попадать в документацию или сообщения. Если компьютер или ключ заменятся, потребуется восстановить ключ из вашей защищённой копии либо настроить новый публичный ключ через доступ REG.RU.

## Как войти на сервер с этого компьютера

1. Запустите **Pageant** из набора PuTTY (значок в области уведомлений Windows). Через **Add Key** выберите `C:\Users\ASUS\Documents\Эксперименты с ИИ\puttykeyaicomp.ppk` и введите парольную фразу в локальном окне. Пока Pageant работает, он держит расшифрованный ключ в памяти для подключений.
2. Откройте **PuTTY**, выберите сохранённую сессию **`regcloud-appadmin`**, нажмите **Load**, затем **Open**. Сессия настроена на `appadmin@194.226.112.63:22` и тот же PPK. При первом подключении на новом компьютере сверяйте отпечаток сервера с доверенной записью, а не принимайте неизвестный ключ автоматически.
3. Появится терминал Linux. Обычная работа выполняется от `appadmin`; у него есть права `sudo` и доступ к Docker. `root` для повседневных действий не нужен.

**PuTTY** открывает терминал. **Pageant** загружает ключ и спрашивает его парольную фразу. **PuTTYgen** нужен для создания или преобразования ключей, не для ежедневного входа. `plink.exe` запускает разовые SSH-команды из PowerShell и также может пользоваться Pageant. Если Pageant не запущен или ключ не загружен, автоматическая команда `-batch` не сможет интерактивно спросить парольную фразу.

На 24.10.2026 у сервера был отпечаток SSH ED25519 `SHA256:4A2Di/plolfzbq8neXGIs4rHMEa7nbO3Naq5EQMYyrU`. Перед доверием к изменившемуся отпечатку проверьте сервер в панели REG.RU: он может поменяться при переустановке VPS, но неожиданная смена требует проверки.

### Быстрая проверка из PowerShell

После загрузки ключа в Pageant:

```powershell
& 'C:\Program Files\PuTTY\plink.exe' -batch -load regcloud-appadmin 'cd /home/appadmin/ai-companion && docker compose --env-file .env.production -f compose.production.yml ps'
```

Проверить сайт без SSH:

```powershell
Invoke-WebRequest https://aicomp.fun/api/health
```

Если вход не проходит, проверьте выбранную сессию PuTTY, имя `appadmin`, загруженный PPK в Pageant и доступность VPS в REG.RU. Секреты никому не пересылайте. Команды ниже выполняются **в терминале PuTTY на сервере**, если не сказано иное.

## Повседневная проверка

```bash
cd /home/appadmin/ai-companion
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 api web proxy
```

Ожидается, что `db`, `api`, `web`, `proxy` запущены; для `db` и `api` есть healthcheck. Если контейнер падает, изучите его журнал:

```bash
docker compose --env-file .env.production -f compose.production.yml logs --tail=200 api
```

Проверяйте публичный адрес и `/api/health`. Если сайт недоступен, последовательно проверьте статус VPS в REG.RU, DNS домена, контейнеры и журнал `proxy`. Сайт обслуживает Caddy, который принимает HTTPS и направляет `/api/*` в API, остальные запросы — в Next.js. Сертификат HTTPS Caddy получает и продлевает автоматически при рабочем DNS и доступных портах 80/443.

## Как обновляется сайт

Код меняют в локальной папке `C:\Users\ASUS\Documents\AI-comp-mvp`, затем создают коммит и отправляют его в `origin/main`. **Один только push не обновляет работающие контейнеры.** На VPS нужно получить коммит и пересобрать нужные сервисы. Перед релизом сделайте резервную копию и проверьте, что на сервере нет ручных изменений:

```bash
cd /home/appadmin/ai-companion
bash deploy/backup-production.sh
git status --short
git pull --ff-only origin main
docker compose --env-file .env.production -f compose.production.yml up -d --build api web proxy
docker compose --env-file .env.production -f compose.production.yml ps
```

После этого откройте сайт и проверьте `https://aicomp.fun/api/health`, основной сценарий входа и журналы. `docker compose restart` перезапускает существующие контейнеры и **не устанавливает новый код**. Не применяйте команды удаления томов (`down -v`) к рабочему сайту.

Если меняется только документация, пересборка и перезапуск сайта не нужны. Если меняется `.env.production`, его редактируют непосредственно на сервере с сохранением прав `600`, затем пересоздают затронутый сервис; значения ключей не выводят в чат или Git. Исходный образец настроек — `.env.production.example`. Домен управляется в DNS/панели REG.RU, баланс и автопополнение — в аккаунте Venice.

## Данные и резервные копии

Данные пользователей живут в именованных томах Docker: PostgreSQL — `postgres_data`, медиа — `app_data`. Ещё два тома, `caddy_data` и `caddy_config`, принадлежат Caddy. Файлы `.env.production` и сам PPK не включаются в обычную копию БД и медиа; их резервное хранение организуйте отдельно и защищённо.

Ручная копия:

```bash
cd /home/appadmin/ai-companion
bash deploy/backup-production.sh
```

Скрипт создаёт закрытую папку вида `/home/appadmin/ai-companion-backups/20261024T120522Z` с `database.dump`, `app_data.tar.gz`, `commit.txt` и `SHA256SUMS`. Он проверяет читаемость созданных архивов и не останавливает сайт. На сервере уже есть задача `cron` с блокировкой от параллельного запуска:

```text
0 3 * * * /usr/bin/flock -n /home/appadmin/ai-companion-backups/.backup.lock /bin/bash /home/appadmin/ai-companion/deploy/backup-production.sh >> /home/appadmin/ai-companion-backups/backup.log 2>&1
```

Это **03:00 по UTC / 06:00 по Москве**. Проверка задания и последних папок:

```bash
crontab -l
ls -lt /home/appadmin/ai-companion-backups
tail -n 50 /home/appadmin/ai-companion-backups/backup.log
```

На дату документа задание установлено, а несколько ручных копий уже созданы; выполнение первого автоматического запуска, хранение копии вне VPS и восстановление на отдельной среде ещё не проверены. Копия на том же VPS защищает от ошибки приложения, но не от потери самого сервера. Перед восстановлением рабочей базы остановитесь и уточните нужную точку восстановления: процедура может заменить более свежие пользовательские данные.

## Кто за что отвечает

- **REG.RU:** VPS, его консоль/состояние и DNS домена `aicomp.fun`.
- **GitHub:** история кода и документов в `khovanov1977-boop/AI-comp-mvp`, ветка `main`; не хранит рабочую БД, медиа или секреты.
- **VPS:** Docker Compose и все рабочие аккаунты, переписки, медиа, текущий `.env.production`, локальные бэкапы.
- **Venice:** платные модельные запросы и баланс. Общего потолка расходов в приложении нет; лимиты на пользователя указаны в [карте проекта](PROJECT_STATUS.md). Владелец подтвердил, что Auto Top-Up выключено.
- **Ваш компьютер:** локальная копия проекта, PuTTY, Pageant и PPK. Пароли и парольная фраза у вас сохранены отдельно.

Для правок политики и согласия исходники лежат в `apps/web/app/privacy/page.tsx` и `apps/web/app/consent/page.tsx`; контакт на сайте — `xaa1@rambler.ru`, оператор — ООО «АИКОМП».
