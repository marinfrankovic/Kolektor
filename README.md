# Kolektor

Self-hosted manager for a coin **and paper money** collection. Runs in Docker, stores everything
in PostgreSQL on your own machine, and works from a phone browser: photograph a coin or banknote,
the server crops it, cleans it up, reads what text it can, and suggests fields you can accept or ignore.

- Coins and banknotes are first-class, each with its own field set (weight, diameter, edge, mint
  vs Pick number, serial, signatures, watermark, security thread, printer).
- Photos are auto-cropped, deskewed and enhanced. The original file is never modified.
- OCR proposes year, denomination, currency and serial numbers. Nothing is written without you.
- A world map shows which countries you already cover, including historical states mapped to their
  present-day successor.
- Installable as a PWA. No Android app to sideload.
- Interface in **English or Croatian**, switchable at any time.
- Single user by design. If another person needs their own collection, run a second container.

---

## Quick start (LAN only, no domain, no TLS)

```bash
git clone https://github.com/marinfrankovic/Kolektor.git
cd Kolektor
cp .env.example .env
# set POSTGRES_PASSWORD and KOLEKTOR_SECRET_KEY (openssl rand -hex 32)
chmod 600 .env
docker compose up -d --build
```

Open `http://<host-ip>:8100`. That is the whole installation. A custom domain, HTTPS and a
reverse proxy are all optional extras, covered further down.

If you point `KOLEKTOR_MEDIA_DIR` at a directory you created yourself, hand it to the container
user first (`chown -R 10001:10001 <dir>`), otherwise uploads fail with a permission error.
`deploy/deploy.sh` does this for you.

### First run: password or no login

The first time you open the app it asks how you want to open it from then on:

| Choice | What it does | Use it when |
| --- | --- | --- |
| **Protect with a password** | Creates your account and asks for email + password at every visit. | The app is reachable from outside your home network, or several people share the network. |
| **No login** | Drops the login screen. Anyone who can open the address sees the collection. | A trusted home LAN only. |

Either choice can be changed later in **Settings → Access**, in both directions. Switching modes
signs out every existing session; your collection is untouched.

To skip the first-run screen entirely (useful for an unattended deploy), set both
`KOLEKTOR_INITIAL_USER_EMAIL` and `KOLEKTOR_INITIAL_USER_PASSWORD` in `.env` before the first
start. The account is created in password mode and the wizard never appears.

---

## Using it from a phone

1. Open the app in the phone browser and choose **Add to home screen**. It installs as a PWA.
2. Tap **Add photo**, pick the item (or "new item") and the side, then shoot.
3. A blur check runs on the phone before anything is uploaded; a soft photo is flagged so you can
   retake it.
4. Photos taken while offline are stored in the browser and uploaded when the connection returns.
5. The server crops the coin or note out of the background, straightens it, adjusts white balance
   and contrast, and generates thumbnail, preview and display sizes plus a perceptual hash.
6. Any OCR guesses appear at the top of the item as suggestions. Accept the ones you want.

Photographing tip: plain dark background, even light, fill the frame, hold the camera parallel to
the piece.

---

## Configuration

Everything lives in `.env`. The defaults are chosen for a LAN install.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | — | Required. Database password. |
| `KOLEKTOR_SECRET_KEY` | — | Required. Signs session tokens. `openssl rand -hex 32`. |
| `KOLEKTOR_HTTP_PORT` | `8100` | Host port. |
| `KOLEKTOR_INITIAL_USER_EMAIL` / `_PASSWORD` | empty | Optional pre-provisioned account; skips the first-run screen. |
| `KOLEKTOR_DEFAULT_LANGUAGE` | `en` | `en` or `hr`. Only the starting language; each user setting wins. |
| `KOLEKTOR_PGDATA` | `./data/postgres` | Where the database files live on the host. |
| `KOLEKTOR_MEDIA_DIR` | `./data/media` | Where photos live on the host. |
| `KOLEKTOR_ENABLE_OCR` | `true` | Turn OCR suggestions on or off. |
| `KOLEKTOR_OCR_LANGUAGES` | `eng` | Tesseract language string, e.g. `eng+hrv+deu`. |
| `KOLEKTOR_AUTOCROP` / `KOLEKTOR_AUTOENHANCE` | `true` | Automatic crop and image clean-up. |
| `KOLEKTOR_WITH_REMBG` | `false` | Build arg. Adds an ML background remover (~300 MB, slower). |
| `KOLEKTOR_BEHIND_PROXY` | `false` | Trust `X-Forwarded-*` headers. |
| `KOLEKTOR_COOKIE_SECURE` | `false` | HTTPS-only cookies. Also enables HSTS. |
| `KOLEKTOR_PUBLIC_BASE_URL` | empty | Public URL, when there is one. |

Photos are stored on disk, not in the database. Back up both.

---

## Optional: custom domain and HTTPS

Only do this if you want to reach the collection from outside your network. The app works
without it.

1. Point a DNS record at your host and get a certificate however you normally do.
2. Copy [deploy/nginx/kolektor.conf](deploy/nginx/kolektor.conf), change `server_name` and the
   certificate paths, enable the site and reload nginx.
3. In `.env` set:
   ```
   KOLEKTOR_BEHIND_PROXY=true
   KOLEKTOR_COOKIE_SECURE=true
   KOLEKTOR_PUBLIC_BASE_URL=https://kolektor.example.com
   ```
4. `docker compose up -d`.

If your nginx runs in a container, keep the `resolver 127.0.0.11;` line and the variable upstream
from the sample config. Without them nginx resolves the app container's IP once at startup and
starts returning 502 the first time you recreate the app.

With a password-protected instance exposed to the internet, also consider putting an
authentication proxy in front of it.

---

## Backups

`deploy/backup.sh` writes a gzipped `pg_dump` and a media manifest into a directory of your
choice, then prunes anything older than 14 days:

```bash
crontab -e
30 2 * * * KOLEKTOR_BACKUP_DIR=/mnt/backup/kolektor /path/to/Kolektor/deploy/backup.sh
```

Restore:

```bash
gunzip -c kolektor-20260101-0230.sql.gz | docker exec -i kolektor-db psql -U kolektor -d kolektor
```

---

## Tests

The suite covers services, the API, authentication and the first-run modes, imaging, OCR parsing,
statistics, the worker, and a dedicated set of security tests (path traversal, upload sniffing,
SQL injection, rate limiting, session handling, security headers).

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest              # 220 tests
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r app
.venv/bin/pip-audit -r requirements.txt
```

On Windows use `.venv\Scripts\pytest.exe`.

`.github/workflows/ci.yml` runs all of the above on every push and pull request, then builds the
frontend and the Docker image. Nothing merges without a green run.

---

## Development

```bash
# backend
cd backend
uvicorn app.main:app --reload      # http://127.0.0.1:8000, API docs at /api/docs

# frontend
cd frontend
npm install
npm run dev                        # http://127.0.0.1:5174, proxies /api to the backend
```

Without `KOLEKTOR_DATABASE_URL` the backend expects Postgres on `db:5432`; point it at a local
instance or run `docker compose up -d db`.

### Layout

```
backend/app/
  main.py          FastAPI app, security headers, SPA fallback
  models.py        SQLAlchemy models (Postgres, SQLite-compatible for tests)
  schemas.py       Pydantic request/response models
  seed.py          Countries, historical entities, optional first user
  worker.py        Polls the job table, processes images
  imaging/         detect, enhance, ocr, pipeline
  routers/         auth, items, images, stats, reference
backend/tests/     pytest suite
frontend/src/
  i18n/            English and Croatian dictionaries
  pages/           Setup, Login, Collection, ItemEdit, Capture, MapView, Stats, Settings
deploy/            optional nginx vhost, deploy and backup scripts
```

Adding a language means adding one dictionary in `frontend/src/i18n/dictionaries.ts` and one entry
to `UI_LANGUAGES` in `backend/app/models.py`.

---

## Security notes

- Passwords are hashed with argon2id. Session tokens are random, stored only as an HMAC, and sent
  in an `HttpOnly` cookie.
- Failed logins are rate limited per IP.
- Uploads are checked by magic bytes, not by file extension, and re-encoded before being served.
- EXIF, including GPS, is stripped from every derivative image.
- HSTS is emitted only when you have actually terminated TLS, so a LAN install cannot lock itself
  out of plain HTTP.
- In **no login** mode there is no authentication at all. Do not expose that instance to the
  internet.
