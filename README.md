# Kolektor

[![CI](https://github.com/marinfrankovic/Kolektor/actions/workflows/ci.yml/badge.svg)](https://github.com/marinfrankovic/Kolektor/actions/workflows/ci.yml)
[![Docker Hub](https://img.shields.io/docker/v/mfrankovic/kolektor?label=docker%20hub&sort=semver)](https://hub.docker.com/r/mfrankovic/kolektor)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Self-hosted manager for a coin **and paper money** collection. Runs in Docker, stores everything
in PostgreSQL on your own machine, and works from a phone browser: photograph a coin or banknote
and the server crops it and cleans it up for you.

- Coins and banknotes are first-class, each with its own field set (weight, diameter, edge, mint
  vs Pick number, serial, signatures, watermark, security thread, printer).
- Adding an item takes two steps: front and back photo, then five fields. Everything else is
  optional and can be filled in later on the item page.
- Photos come from the camera, a file on your computer, or a link you paste.
- Photos are auto-cropped and deskewed. The original file is never modified, and no colour or
  sharpness processing is applied unless you turn `KOLEKTOR_AUTOENHANCE` on.
- Click a photo on the item page to open it full size; ‹ › or the arrow keys step through the rest,
  and the zoom buttons, the mouse wheel or a double click magnify up to 6×. Drag to move around.
- The collection country filter lists only the countries you own something from, plus **No country**
  for pieces you have not placed yet.
- The item page carries around 60 fields. **Settings → Item fields** lets you untick the ones you
  never use so the page only shows what you care about.
- A world map shows which countries you already cover, including historical states mapped to their
  present-day successor.
- Installable as a PWA. No Android app to sideload.
- Interface in **English or Croatian**, switchable at any time. Light, dark or system theme.
- Dates are shown and typed as `dd/mm/yyyy`.
- Single user by design. If another person needs their own collection, run a second container.

---

## Quick start (LAN only, no domain, no TLS)

The image is on Docker Hub as [`mfrankovic/kolektor`](https://hub.docker.com/r/mfrankovic/kolektor),
built for `amd64` and `arm64`, so a Raspberry Pi works as well as a NUC.

```bash
git clone https://github.com/marinfrankovic/Kolektor.git
cd Kolektor
cp .env.example .env
# set POSTGRES_PASSWORD and KOLEKTOR_SECRET_KEY (openssl rand -hex 32)
chmod 600 .env
docker compose up -d
```

That pulls the published image. To build it yourself from the checkout instead, run
`docker compose up -d --build`. To pin a release rather than follow `latest`, set
`KOLEKTOR_IMAGE=mfrankovic/kolektor:1.0` in `.env`.

Upgrading is `docker compose pull && docker compose up -d`. The database migrates itself on
start; your photos and rows are untouched.

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

## Adding an item

The **＋** tab opens a two-step form.

1. **Photos.** Every item carries at least two: obverse and reverse for a coin, face and back for
   a note. Each slot takes a camera shot, a file from the computer, or a pasted image URL. A blur
   check runs in the browser first, so a soft photo is flagged before it is uploaded.
2. **Details.** Name, country, currency, nominal value. The country field filters as you type, so
   you never scroll a list of 249. Year is there too but you can leave it empty. Save, and the item
   opens with everything else ready to fill in whenever you feel like it.

On a phone, open the app in the browser and choose **Add to home screen**; it installs as a PWA
and the same form uses the camera directly. Photos taken while offline are stored in the browser
and uploaded when the connection returns.

The server crops the coin or note out of the background, straightens it, and generates thumbnail,
preview and display sizes plus a perceptual hash. Colours and sharpness are left alone unless you
set `KOLEKTOR_AUTOENHANCE=true`.

On the item page each photo has a **⟳ Retake** button that shoots or picks a replacement and keeps
the same role; the old file is only deleted once the new one has uploaded. If an item is missing
its obverse or reverse (face or back for a note) a dashed **＋** slot appears in its place, so a
piece you photographed only from one side is easy to spot and finish.

Photographing tip: plain dark background, even light, fill the frame, hold the camera parallel to
the piece.

### Choosing which fields you see

A full record has around 60 fields, and most collectors use a fraction of them. **Settings → Item
fields** lists every optional one as a checkbox, grouped the same way the item page is: item
details, coin details, banknote details, acquisition, sale. Untick what you do not use and it
disappears from the item page. A group whose fields are all unticked drops its whole card.

Seven fields cannot be hidden, because an item without them describes nothing: **type, status,
title, country, denomination, currency unit and year**.

Hiding a field never touches your data. Anything you already typed stays in the database and comes
back the moment you tick the box again. The choice is stored in the browser, so each device can
show a different amount of detail.

---

## Configuration

Everything lives in `.env`. The defaults are chosen for a LAN install.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | — | Required. Database password. |
| `KOLEKTOR_SECRET_KEY` | — | Required. Signs session tokens. `openssl rand -hex 32`. |
| `KOLEKTOR_HTTP_PORT` | `8100` | Host port. |
| `KOLEKTOR_IMAGE` | `mfrankovic/kolektor:latest` | Image to run. Pin a version here, or point it at a local build. |
| `KOLEKTOR_INITIAL_USER_EMAIL` / `_PASSWORD` | empty | Optional pre-provisioned account; skips the first-run screen. |
| `KOLEKTOR_DEFAULT_LANGUAGE` | `en` | `en` or `hr`. Only the starting language; each user setting wins. |
| `KOLEKTOR_PGDATA` | `./data/postgres` | Where the database files live on the host. |
| `KOLEKTOR_MEDIA_DIR` | `./data/media` | Where photos live on the host. |
| `KOLEKTOR_AUTOCROP` | `true` | Crop the piece out of the background. |
| `KOLEKTOR_AUTOENHANCE` | `false` | White balance, denoise and contrast. Off by default: a cropped photo of a coin usually looks more honest than a processed one. |
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

A containerised nginx also has to share a Docker network with the app, otherwise it cannot resolve
`kolektor-app` at all. Add the proxy's network to the `app` service and declare it as external:

```yaml
  app:
    networks:
      - default
      - proxy_net

networks:
  default:
  proxy_net:
    external: true
```

Note that `KOLEKTOR_COOKIE_SECURE=true` makes the session cookie HTTPS-only, so signing in over
plain `http://<host-ip>:8100` stops working. Use the domain from then on.

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

The suite covers services, the API, authentication and the first-run modes, imaging,
statistics, the worker, remote image fetching, and a dedicated set of security tests (path
traversal, upload sniffing, SSRF, SQL injection, rate limiting, session handling, security
headers).

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest              # 203 tests
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
  fetching.py      Guarded download of images the user linked to
  seed.py          Countries, historical entities, optional first user
  worker.py        Polls the job table, processes images
  imaging/         detect, enhance, pipeline
  routers/         auth, items, images, stats, reference
backend/tests/     pytest suite
frontend/src/
  i18n/            English and Croatian dictionaries
  lib/             date formatting, theme, item field visibility
  pages/           Setup, Login, Collection, ItemNew, ItemEdit, MapView, Stats, Settings
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
- Images imported from a URL only reach public addresses: the scheme must be http or https, the
  hostname is resolved and checked against private, loopback, link-local and multicast ranges on
  every redirect hop, redirects stop at three, and the download has a timeout and a size cap.
- EXIF, including GPS, is stripped from every derivative image.
- HSTS is emitted only when you have actually terminated TLS, so a LAN install cannot lock itself
  out of plain HTTP.
- In **no login** mode there is no authentication at all. Do not expose that instance to the
  internet.

---

## Disclaimer

Kolektor is a personal project, published in case it is useful to someone else. It comes with no
warranty and no support commitment. Read the points below before you trust it with a collection
you care about.

- **Your data is yours to protect.** Kolektor stores everything on the machine you run it on. It
  does not back anything up on its own. Set up `deploy/backup.sh` or your own job, and test a
  restore at least once. A gzipped dump you have never restored is not a backup.
- **Nothing is uploaded anywhere.** There is no telemetry, no analytics, no cloud account, no
  phoning home. The only outbound request the app ever makes is fetching an image from a URL you
  paste yourself.
- **You are the administrator.** Keeping Docker, the host and your certificates current is your
  job. Exposing an instance to the internet, especially one in **no login** mode, is a decision
  only you can make.
- **Automatic cropping and enhancement are approximations.** They can misjudge a photo. Originals
  are never modified, so a bad result is always recoverable, but check the output rather than
  assuming it.
- **No valuations, no grading, no authentication.** Kolektor records what you type. It does not
  price your collection, grade a coin, or tell you whether a piece is genuine. Grade and
  certification fields are there to note what a third party already decided.
- **Not affiliated** with any mint, grading service, auction house or catalogue publisher.
  Catalogue reference fields exist so you can record numbers you looked up elsewhere.
- The software is provided "as is". See [LICENSE](LICENSE) for the full text.

---

## License

[MIT](LICENSE). Do what you like with it; keep the copyright notice.

## Contributing

Issues and pull requests are welcome, though this is a spare-time project and replies may be slow.
Run the test suite and `ruff` before opening a pull request; CI will run them anyway.
