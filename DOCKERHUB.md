# Kolektor

Self-hosted manager for a coin **and paper money** collection. Runs in Docker, keeps everything in
PostgreSQL on your own machine, and works from a phone browser: photograph a coin or banknote and
the server crops it and cleans it up for you.

Source, issues and the full documentation: **https://github.com/marinfrankovic/Kolektor**

## Supported tags

| Tag | What it is |
| --- | --- |
| `latest` | Built from `main` on every push. |
| `1.0.0`, `1.0` | Released versions. Pin one of these if you would rather upgrade deliberately. |

Built for `linux/amd64` and `linux/arm64`, so a Raspberry Pi works as well as a NUC.

## What it does

- Coins and banknotes are first-class, each with its own field set (weight, diameter, edge, mint vs
  Pick number, serial, signatures, watermark, security thread, printer).
- Adding an item takes two steps: front and back photo, then five fields.
- Photos are auto-cropped and deskewed. The original file is never modified.
- Around 60 fields per item, and Settings lets you hide the ones you never use.
- A world map shows which countries you already cover, including historical states mapped to their
  present-day successor.
- Installable as a PWA. Interface in English or Croatian. Light, dark or system theme.
- Optional password login, or no login at all on a trusted LAN.
- Single user by design. If another person needs their own collection, run a second container.

## Quick start

Kolektor needs a PostgreSQL database and a worker container alongside it, so compose is the way to
run it. Grab the compose file from the repository:

```bash
git clone https://github.com/marinfrankovic/Kolektor.git
cd Kolektor
cp .env.example .env
# set POSTGRES_PASSWORD and KOLEKTOR_SECRET_KEY (openssl rand -hex 32)
chmod 600 .env
docker compose up -d
```

Open `http://<host-ip>:8100`. The first screen asks whether to protect the app with a password or
run it without a login.

Upgrading is `docker compose pull && docker compose up -d`. The schema migrates itself on start.

## Configuration

Set these in `.env`. Full table in the repository README.

| Variable | Default | Purpose |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | — | Required. Database password. |
| `KOLEKTOR_SECRET_KEY` | — | Required. Signs session tokens. `openssl rand -hex 32`. |
| `KOLEKTOR_IMAGE` | `mfrankovic/kolektor:latest` | Pin a version here. |
| `KOLEKTOR_HTTP_PORT` | `8100` | Host port. |
| `KOLEKTOR_DEFAULT_LANGUAGE` | `en` | `en` or `hr`. |
| `KOLEKTOR_PGDATA` | `./data/postgres` | Database files on the host. |
| `KOLEKTOR_MEDIA_DIR` | `./data/media` | Photos on the host. |
| `KOLEKTOR_AUTOCROP` | `true` | Crop the piece out of the background. |
| `KOLEKTOR_AUTOENHANCE` | `false` | White balance, denoise and contrast. |
| `KOLEKTOR_BEHIND_PROXY` | `false` | Trust `X-Forwarded-*` headers. |
| `KOLEKTOR_COOKIE_SECURE` | `false` | HTTPS-only cookies. Also enables HSTS. |

The container runs as uid `10001`. If you bind-mount a media directory you created yourself, run
`chown -R 10001:10001 <dir>` first or uploads will fail.

Photos live on disk, not in the database. Back up both.

## Security

Passwords are hashed with argon2id. Session tokens are stored only as an HMAC and sent in an
`HttpOnly` cookie. Uploads are checked by magic bytes and re-encoded. EXIF, including GPS, is
stripped from every derivative image. Images imported from a URL only reach public addresses.

In **no login** mode there is no authentication at all. Do not expose that instance to the internet.

## Disclaimer

A personal project, published in case it is useful to someone else. No warranty, no support
commitment. Kolektor stores everything on the machine you run it on and backs up nothing on its
own; set up a backup job and test a restore. It sends no telemetry. It does not price, grade or
authenticate anything, and it is not affiliated with any mint, grading service or catalogue
publisher.

## License

[MIT](https://github.com/marinfrankovic/Kolektor/blob/main/LICENSE)
