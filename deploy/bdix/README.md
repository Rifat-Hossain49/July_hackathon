# Shongket BDIX/domestic hub deployment

This deploys the approved public text-capsule hub to one POSIX server. The
server must be in Bangladesh **and its address must be tested from the target
ISPs**; a Bangladesh billing address or data-centre label is not evidence of a
BDIX route.

## Required operator inputs

Provide these through a secure credential channel, never in the repository or
an issue:

- host/IP of a BDIX/domestically reachable VPS;
- SSH user and SSH public-key access;
- domain name and DNS control;
- the host provider's documented network/peering contact;
- TLS certificate path or permission to provision one before a blackout; and
- two named ISP connections for the separate field gate.

No GitHub token, Apple credential or Android signing key is needed for this
hub.

## Host preparation

Use a currently supported Linux distribution, Python 3.10+ and the
distribution's supported Nginx package. Record `python --version`,
`python -c "import sqlite3; print(sqlite3.sqlite_version)"`, `nginx -v` and the
deployment commit in the field log.

```sh
sudo useradd --system --home /opt/shongket --shell /usr/sbin/nologin shongket
sudo install -d -o shongket -g shongket -m 0750 /opt/shongket/current
sudo install -d -o shongket -g shongket -m 0700 /var/lib/shongket-hub
sudo python3 -m venv /opt/shongket/venv
sudo /opt/shongket/venv/bin/pip install -r deploy/bdix/requirements.txt
```

Copy a clean checkout at the approved commit into `/opt/shongket/current`.
Do not copy `.git`, local databases, `.env` files or credentials into the
served tree.

## Configuration

```sh
sudo install -o root -g shongket -m 0640 \
  deploy/bdix/shongket-hub.env.example /etc/shongket-hub.env
sudo install -o root -g root -m 0644 \
  deploy/bdix/shongket-hub.service /etc/systemd/system/shongket-hub.service
```

Edit `/etc/shongket-hub.env` and set the exact HTTPS origin. Keep the backend
bound to loopback. `SHONGKET_HUB_TRUSTED_PROXY=127.0.0.1` is safe only while
Nginx overwrites `X-Real-IP` and the Gunicorn socket remains loopback-only.

Copy `nginx.conf.example` into the distribution's enabled site directory,
replace the domain/certificate paths and validate with `sudo nginx -t`.
Provision and test the certificate before depending on the hub; installed
PWAs and service workers require HTTPS outside local development.

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now shongket-hub
sudo systemctl reload nginx
curl --fail --silent https://shongket.example.bd/healthz
```

Gunicorn access logging is intentionally disabled. Nginx logging must not be
changed to include request bodies. The application never logs capsule message
or location text.

## Backup and restore

Create a root-owned backup directory, then run the online SQLite backup:

```sh
sudo install -d -o root -g root -m 0700 /var/backups/shongket-hub
sudo -u shongket /opt/shongket/venv/bin/python deploy/bdix/backup.py \
  --source /var/lib/shongket-hub/hub.sqlite3 \
  --destination /var/backups/shongket-hub/hub-YYYYMMDD-HHMMSS.sqlite3
```

The command refuses to overwrite a backup and runs SQLite's integrity check.
To restore, stop the service, preserve the current database, copy one verified
backup into the configured database path with owner `shongket`, mode `0600`,
then start the service and check `/healthz`.

## Domestic field gate

Do not label the deployment "BDIX validated" until `BDIX_HUB_SCOPE.md` §8 is
complete. At minimum, test the same HTTPS hostname from two named fixed-line
ISPs while global reachability is intentionally unavailable but their domestic
routes remain active. Record both successes and failures. If domestic DNS is
not reachable, document a pre-distributed IP/hosts-file fallback; do not
bypass browser certificate warnings.

If the domestic route also fails, this hub cannot bridge the users. Switch to
the existing nearby local-Wi-Fi/hotspot mode.
