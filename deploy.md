# BMP Compliance Platform - Deployment and Hosting Guide (Ubuntu VM)

Audience: you, working from Windows with PuTTY (terminal) and WinSCP (file transfer).
Result: the whole project (database + web application) running on one Ubuntu VM, starting automatically,
reachable in a browser, with backups.

Verified: the packaging command (Part A) and the "move my existing data" procedure (Part H, Option 2) were
rehearsed on the local machine (all 66 tables, 769 rows, restored identically). The Ubuntu-side commands follow
the standard documented procedures for each tool but could not be executed from here, so read the "Check" line
after every step before moving on.

---------------------------------------------------------------------------------------------------------
## 0. What you will end up with

```
Browser --HTTPS--> Nginx (ports 80/443) --> BMP application (127.0.0.1:8000, systemd service "bmp")
                                                 |
                                                 +--> PostgreSQL 18 + pgvector (localhost only)
                                                 +--> /opt/bmp/storage   (uploaded evidence files)
                                                 +--> /opt/bmp/instance  (sign-in password hashes)
```

Everything lives under /opt/bmp, owned by a dedicated Linux user "bmp" (not root).

### Decisions to make now (they change a few steps)

1. HTTPS option (Part L):
   A. You have a domain name pointing to the VM  -> free trusted certificate (recommended).
   B. You only have the VM's IP address           -> self-signed certificate (browser shows a warning once).
   C. Internal trial only                          -> plain HTTP (not for real data: passwords travel unencrypted).
2. Database content (Part H):
   Option 1: fresh demo database (the fictional demo data).
   Option 2: move the data from your local PC database to the VM.
3. Sign-in passwords (Part I): set new ones on the VM (recommended) or copy your local credentials file.

### Placeholders used below (replace them with your values; do not type the angle brackets)

```
<VM_IP>     the VM's public/reachable IP address
<VM_USER>   the Linux login you were given (must be able to use sudo)
<DOMAIN>    your domain name (option A only)
```

---------------------------------------------------------------------------------------------------------
## 1. What you need before starting

- VM: Ubuntu 22.04 or 24.04 LTS, at least 1 vCPU, 2 GB RAM, 10 GB free disk, internet access from the VM.
- Credentials: <VM_USER> + password (or a private key). The user must be in the sudo group.
- Network: the VM's firewall / cloud "security group" allows inbound TCP 22 (SSH), 80 and 443.
- On Windows: PuTTY, WinSCP, and PowerShell (Windows 10/11 already includes "tar").
- The project folder: Latest_Implementation_with_approved_Database
- Optional (Option 2 only): the PostgreSQL 18 client tools on your PC (installed with your local PostgreSQL;
  path C:\Program Files\PostgreSQL\18\bin).

---------------------------------------------------------------------------------------------------------
## PART A - Package the project on Windows (how the project and its dependencies travel)

### A.1 What is copied, what is not, and why

The project is copied as source files only. Dependencies are NOT copied; they are installed again on the VM
from requirements.txt. Reasons:

| Item                    | Copy? | Reason                                                                         |
|-------------------------|-------|--------------------------------------------------------------------------------|
| app/, db/, scripts/, tests/, docs/, demo/, *.md, *.xlsx, *.docx, requirements.txt | YES | The product, database scripts and documents |
| venv/                   | NO    | A Windows Python environment does not run on Linux. Rebuilt on the VM (Part F) |
| .env                    | NO    | Contains your local passwords. A new one is created on the VM (Part G)         |
| instance/               | NO*   | Sign-in password hashes. *See Part I, you may choose to copy it                |
| storage/                | NO*   | Uploaded evidence files. *Copy only if you are moving existing data (Option 2) |
| tmp/, .pytest_cache/, __pycache__/, *.pyc | NO | Scratch files                                                  |
| PostgreSQL itself       | NO    | Installed on the VM (Part D); the data is created or restored in Part H        |

Python packages needed (from requirements.txt): psycopg[binary], psycopg-pool, python-dotenv, openpyxl, fastapi,
uvicorn[standard], jinja2, python-multipart, itsdangerous, httpx, pytest.

### A.2 Create the archive (PowerShell on your PC)

Open PowerShell and run (adjust the first path if your folder is elsewhere):

```
cd "C:\Users\Anant Sharma.CGBSBLRLAP10221\Desktop\BMP\Latest_Implementation_with_approved_Database"

tar -czf "$env:USERPROFILE\Desktop\bmp_deploy.tar.gz" --exclude=venv --exclude=.venv --exclude=.env --exclude=instance --exclude=storage --exclude=tmp --exclude=.pytest_cache --exclude=__pycache__ --exclude="*.pyc" --exclude=.git .
```

Check: the file bmp_deploy.tar.gz appears on your Desktop and is about 2-3 MB. To list what is inside:

```
tar -tzf "$env:USERPROFILE\Desktop\bmp_deploy.tar.gz"
```

You should see app/, db/, scripts/, tests/, docs/, requirements.txt and .env.example, and NOT venv, .env,
instance, storage.

Alternative without tar: in WinSCP you can upload the folder directly (drag and drop), but exclude venv, .env,
instance, storage, tmp, .pytest_cache, __pycache__ using WinSCP's transfer settings "File mask"
(for example:  | venv/; tmp/; instance/; storage/; .pytest_cache/; __pycache__/; .env ). One archive file is
faster and less error-prone.

### A.3 (Optional) Pin the exact package versions you tested with

requirements.txt allows newer versions ("fastapi>=0.115"). The VM will install the newest allowed versions, which
may be newer than the ones you tested. To install the same versions you have locally, create a lock list first:

```
.\venv\Scripts\Activate.ps1
pip freeze > "$env:USERPROFILE\Desktop\requirements.lock.txt"
```

and upload it next to the archive (Part E). On the VM you will then install from it (Part F). If the VM install
complains about a Windows-only package, use requirements.txt instead.

### A.4 (Optional) Offline package bundle - only if the VM cannot reach the internet

Match the Python version of the VM (Ubuntu 24.04 = 3.12, Ubuntu 22.04 = 3.10; check with "python3 --version" on
the VM). Example for 3.12:

```
pip download -r requirements.txt -d "$env:USERPROFILE\Desktop\wheels" --platform manylinux2014_x86_64 --python-version 3.12 --implementation cp --only-binary=:all:
tar -czf "$env:USERPROFILE\Desktop\bmp_wheels.tar.gz" -C "$env:USERPROFILE\Desktop" wheels
```

Upload bmp_wheels.tar.gz too; Part F explains the offline install. PostgreSQL and Nginx also need internet or an
internal mirror, so a VM with no internet at all is not covered by this guide.

### A.5 (Option 2 only) Dump your local database and uploaded files

Skip this unless you chose "move my data" in section 0. The dump contains data only (the structure is rebuilt on
the VM from the project's own migration files). In PowerShell:

```
& "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -h localhost -U postgres -d bmp -Fc --data-only --exclude-table=public.schema_migrations --exclude-table=public.schema_seeds --exclude-table-data=activity.entity_field_registry -f "$env:USERPROFILE\Desktop\bmp_data.dump"
```

It asks for your local postgres password (typing is not shown). The three excluded items are rebuilt by the
migrations on the VM, so they must not be loaded twice.

Check: bmp_data.dump exists (size in the 100s of KB). Also note the row count of a table to compare later, for
example in pgAdmin or psql:   SELECT count(*) FROM core.company;

Uploaded evidence files (only if you have some in the local "storage" folder):

```
tar -czf "$env:USERPROFILE\Desktop\bmp_storage.tar.gz" storage
```

NOTE: the VM needs PostgreSQL 18 (the same major version as your PC), because pg_restore can only read dumps made
by the same or an older version. Part D installs 18.

---------------------------------------------------------------------------------------------------------
## PART B - Connect with PuTTY and WinSCP

### B.1 PuTTY (terminal)

1. Open PuTTY. Host Name: <VM_IP>   Port: 22   Connection type: SSH.
2. If you were given a key file (.ppk): Connection > SSH > Auth > Credentials > Private key file.
3. Connection > "Seconds between keepalives" = 30 (stops idle disconnects during long steps).
4. Session > Saved Sessions: type "BMP-VM" > Save.  Then Open. Accept the host key the first time.
5. Log in as <VM_USER>.

PuTTY tips: right-click pastes into the terminal; select text with the mouse to copy. In the nano editor:
Ctrl+O then Enter saves, Ctrl+X exits. Stay in ONE PuTTY window for Parts G-H because some commands reuse
variables set earlier in the same session.

### B.2 WinSCP (files)

1. New Site: File protocol SFTP, Host name <VM_IP>, Port 22, User name <VM_USER>, password (or Advanced >
   SSH > Authentication > the same .ppk key). Save as "BMP-VM", then Login.
2. You land in /home/<VM_USER>. This is where you will upload the archive (that folder is writable by you).
3. Tip: WinSCP > Options > Preferences > Panels > "Show hidden files" so you can see dotfiles such as .env.
   In the site's Advanced > Environment > Directories you can set the remote start folder to /opt/bmp later.

Both tools use the same login, so you can type commands in PuTTY and watch/upload files in WinSCP at the same
time.

---------------------------------------------------------------------------------------------------------
## PART C - Prepare the Ubuntu VM (PuTTY)

### C.1 Look at the machine

```
lsb_release -a
python3 --version
free -h
df -h /
```

Check: Ubuntu 22.04 or 24.04; Python 3.10 or newer (the project supports 3.10+); at least 1 GB free memory.

### C.2 Update the system and install base packages

```
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx ufw curl ca-certificates openssl
```

Check: "nginx -v" and "python3 -m venv --help" both print something (no "command not found").

### C.3 (Recommended) Set the time zone

Overdue dates and due dates are calculated using the database server's date.

```
sudo timedatectl set-timezone Asia/Kolkata
timedatectl
```

### C.4 Create the application user and folders

```
sudo useradd --system --create-home --home-dir /opt/bmp --shell /bin/bash bmp
sudo mkdir -p /opt/bmp/instance /opt/bmp/storage
sudo chown -R bmp:bmp /opt/bmp
```

Check: "ls -ld /opt/bmp" shows owner bmp bmp.

---------------------------------------------------------------------------------------------------------
## PART D - Install PostgreSQL 18 with pgvector

The project's database needs the extensions vector (pgvector), btree_gist and pgcrypto. Ubuntu's own repository
does not carry version 18, so add the official PostgreSQL (PGDG) repository:

```
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt install -y postgresql-18 postgresql-18-pgvector
```

Check:

```
sudo -u postgres psql -c "select version();"
sudo -u postgres psql -c "select name, default_version from pg_available_extensions where name in ('vector','btree_gist','pgcrypto');"
```

The first shows PostgreSQL 18.x; the second lists three rows (vector, btree_gist, pgcrypto).
The service starts automatically and listens on localhost only (do not change that).

If version 18 is not available for your Ubuntu release: install 17 instead (replace 18 by 17 in the two package
names). That is fine for Option 1. For Option 2 it means the dump from your PC (made by version 18) cannot be read
by pg_restore 17; in that case make the dump in plain format instead (add "-Fp" instead of "-Fc" and use
.sql as the file extension in A.5) and load it with: sudo -u postgres psql -d bmp -f /tmp/bmp_data.sql
(this alternative path was not rehearsed).

---------------------------------------------------------------------------------------------------------
## PART E - Upload the project (WinSCP) and unpack it (PuTTY)

1. In WinSCP, drag bmp_deploy.tar.gz from your Desktop into /home/<VM_USER> (the remote left panel).
   Also upload, if you made them: requirements.lock.txt, bmp_wheels.tar.gz, bmp_data.dump, bmp_storage.tar.gz.
2. In PuTTY:

```
sudo tar -xzf ~/bmp_deploy.tar.gz -C /opt/bmp
sudo chown -R bmp:bmp /opt/bmp
ls /opt/bmp
```

Check: the listing shows app  db  docs  scripts  tests  requirements.txt (and the .md/.docx/.xlsx files).
Harmless messages such as "Ignoring unknown extended header keyword" can be ignored.

3. If you uploaded a lock file or the stored files:

```
sudo cp ~/requirements.lock.txt /opt/bmp/ 2>/dev/null
sudo tar -xzf ~/bmp_storage.tar.gz -C /opt/bmp 2>/dev/null
sudo chown -R bmp:bmp /opt/bmp
```

---------------------------------------------------------------------------------------------------------
## PART F - Create the Python environment and install the dependencies

```
cd /opt/bmp
sudo -u bmp python3 -m venv venv
sudo -u bmp ./venv/bin/pip install --upgrade pip
sudo -u bmp ./venv/bin/pip install -r requirements.txt
```

(pinned versions from A.3:  ... pip install -r requirements.lock.txt)

Offline install (A.4):

```
sudo tar -xzf ~/bmp_wheels.tar.gz -C /opt/bmp && sudo chown -R bmp:bmp /opt/bmp/wheels
sudo -u bmp ./venv/bin/pip install --no-index --find-links /opt/bmp/wheels -r requirements.txt
```

Check:

```
sudo -u bmp ./venv/bin/python -c "import fastapi, psycopg, uvicorn; print('imports ok', fastapi.__version__)"
```

---------------------------------------------------------------------------------------------------------
## PART G - Create the settings file (.env) with new random passwords

Do this in a single PuTTY window, in one go. It generates strong passwords (letters and digits only, so no special
characters break the connection addresses), sets the PostgreSQL administrator password, and writes .env.

```
cd /opt/bmp
OWNER_PW=$(openssl rand -hex 16)
APP_PW=$(openssl rand -hex 16)
PG_PW=$(openssl rand -hex 16)
SECRET=$(./venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))")

sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$PG_PW';"

{
echo "DATABASE_URL=postgresql+psycopg://bmp_owner:${OWNER_PW}@localhost:5432/bmp"
echo "DATABASE_URL_APP=postgresql+psycopg://bmp_app:${APP_PW}@localhost:5432/bmp"
echo "DATABASE_URL_ADMIN=postgresql+psycopg://postgres:${PG_PW}@localhost:5432/postgres"
echo "APP_ENV=production"
echo "APP_SECRET_KEY=${SECRET}"
echo "COOKIE_SECURE=true"
echo "SESSION_MAX_AGE_SECONDS=28800"
echo "MAX_UPLOAD_MB=25"
} | sudo -u bmp tee /opt/bmp/.env > /dev/null

sudo chmod 600 /opt/bmp/.env
sudo cat /opt/bmp/.env
```

IMPORTANT
- A message like "could not change directory to /opt/bmp: Permission denied" from the psql line is harmless.
- If you prefer to edit by hand: "sudo -u bmp nano /opt/bmp/.env", type the 8 lines with your own passwords, save.
- If you chose HTTPS option C (plain HTTP), change the line to  COOKIE_SECURE=false  (otherwise the browser
  refuses to keep the sign-in cookie and nobody can log in). Options A and B keep it true.
- Copy the contents of .env into your password manager now. Passwords are not recoverable from the application.
- What each line does: DATABASE_URL = the "owner" login (migrations, audit-log reading, company onboarding);
  DATABASE_URL_APP = the login used for normal requests; DATABASE_URL_ADMIN = the PostgreSQL administrator (needed
  only to create the database and to run the test suite); APP_ENV=production turns on strict start-up checks, hides
  the interactive API documentation and adds HSTS; APP_SECRET_KEY signs session cookies (keep it secret, at least
  32 characters); COOKIE_SECURE sends the cookie only over HTTPS.
- Database name must stay "bmp" (the setup script uses that name).

Check: "sudo ls -l /opt/bmp/.env" shows -rw------- bmp bmp.

---------------------------------------------------------------------------------------------------------
## PART H - Build the database

### Option 1 - fresh demo database (migrations + the fictional seed data)

```
cd /opt/bmp
sudo -u bmp ./venv/bin/python scripts/setup_db.py --seed
```

Check: the output ends with "Migrations: 11 applied", five seed files "OK" and "Done." Re-running is safe.

### Option 2 - move the data from your local PC

1. Build the empty structure only (NO --seed):

```
cd /opt/bmp
sudo -u bmp ./venv/bin/python scripts/setup_db.py
```

   Check: "Migrations: 11 applied" and "Done."

2. Put the dump where PostgreSQL can read it and load it (the dump was uploaded to /home/<VM_USER> in Part E):

```
sudo cp ~/bmp_data.dump /tmp/bmp_data.dump
sudo chmod 644 /tmp/bmp_data.dump
sudo -u postgres pg_restore -d bmp --data-only --disable-triggers /tmp/bmp_data.dump
sudo rm /tmp/bmp_data.dump ~/bmp_data.dump
```

   "--disable-triggers" lets the data load in any order and keeps your original audit history untouched while
   loading; the triggers are active again afterwards. No error output means success.

3. Compare with your PC (use a table you noted in A.5):

```
sudo -u postgres psql -d bmp -c "select count(*) from core.company;"
sudo -u postgres psql -d bmp -c "select count(*) from audit.log;"
```

   The numbers must equal your local database. Also confirm structure protections are still on:

```
sudo -u postgres psql -d bmp -c "select count(*) from pg_trigger where not tgisinternal and tgenabled <> 'O';"
```

   This must print 0.

Removing a mistake: if the restore reports errors, drop and rebuild before retrying:

```
sudo -u postgres psql -c "DROP DATABASE bmp;"
cd /opt/bmp && sudo -u bmp ./venv/bin/python scripts/setup_db.py
```

(This is safe only because no real data has been entered on the VM yet.)

---------------------------------------------------------------------------------------------------------
## PART I - Sign-in passwords

The database has no password column. Passwords are stored (salted, hashed) in /opt/bmp/instance/users.json.
A person can sign in only if they have a password there AND an active row in the database (Administration > Users).

Recommended: set new passwords on the VM. In production mode "init-demo" is disabled, so set each one
(you are asked twice; typing is hidden; at least 8 characters):

```
cd /opt/bmp
sudo -u bmp ./venv/bin/python scripts/manage_users.py list
sudo -u bmp ./venv/bin/python scripts/manage_users.py set-password admin@bmpco.in
sudo -u bmp ./venv/bin/python scripts/manage_users.py set-password manager@bmpco.in
sudo -u bmp ./venv/bin/python scripts/manage_users.py set-password client@nexatech.co.in
```

(Use the e-mail addresses of your real users instead of, or in addition to, the demo ones. New users are added in
the application under Administration > Users and User company access, then given a password with the command
above or with "Set password" inside the user's record.)

Alternative: keep the same passwords you use locally by copying the local file C:\...\instance\users.json with
WinSCP to /opt/bmp/instance/users.json, then:

```
sudo chown bmp:bmp /opt/bmp/instance/users.json && sudo chmod 600 /opt/bmp/instance/users.json
```

---------------------------------------------------------------------------------------------------------
## PART J - Start it once by hand

```
cd /opt/bmp
sudo -u bmp ./venv/bin/python scripts/run_server.py --host 127.0.0.1 --port 8000
```

Leave it running, open a SECOND PuTTY window and run:

```
curl -s http://127.0.0.1:8000/api/health
```

Check: it prints {"status": "ok", "database": true, "version": "1.0.0"}.
Then press Ctrl+C in the first window to stop it. (If it fails to start, the message is explicit: for example
"APP_SECRET_KEY must be set" or a database authentication error - see the Troubleshooting table.)

---------------------------------------------------------------------------------------------------------
## PART K - Run it as a service (starts at boot, restarts if it crashes)

Create the service file:

```
sudo nano /etc/systemd/system/bmp.service
```

Paste:

```
[Unit]
Description=BMP Compliance Platform
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=bmp
Group=bmp
WorkingDirectory=/opt/bmp
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/bmp/venv/bin/python scripts/run_server.py --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Save (Ctrl+O, Enter, Ctrl+X), then:

```
sudo systemctl daemon-reload
sudo systemctl enable --now bmp
sudo systemctl status bmp --no-pager
curl -s http://127.0.0.1:8000/api/health
```

Check: status shows "active (running)" and the health call returns "ok".

Keep ONE worker (the default). The sign-in lock-out counter is kept in memory per process, so extra workers would
weaken it.

Everyday service commands:

```
sudo systemctl restart bmp          restart after a change
sudo systemctl stop bmp             stop
sudo journalctl -u bmp -f           live log (Ctrl+C to leave)
sudo journalctl -u bmp --since "1 hour ago"
```

---------------------------------------------------------------------------------------------------------
## PART L - Nginx in front (the public address) and HTTPS

The application only listens on 127.0.0.1:8000. Nginx receives public traffic, handles HTTPS and forwards it.

### L.1 Base site (all options)

```
sudo nano /etc/nginx/sites-available/bmp
```

Paste (option A: put your domain after server_name; options B/C: use _ ):

```
server {
    listen 80;
    server_name <DOMAIN>;

    client_max_body_size 30m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

(client_max_body_size 30m matches the 25 MB upload limit of the application.)

Enable it and remove the default welcome site:

```
sudo ln -s /etc/nginx/sites-available/bmp /etc/nginx/sites-enabled/bmp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Check: "nginx -t" says "syntax is ok"; from your PC browser, http://<VM_IP>/ shows the BMP sign-in page
(if the firewall from Part M is already open).

### L.2 Option A - domain name + free trusted certificate (recommended)

Prerequisite: a DNS "A" record <DOMAIN> -> <VM_IP>, and ports 80/443 open.

```
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <DOMAIN>
```

Answer the e-mail question, accept the terms, choose to redirect HTTP to HTTPS. Certificates renew automatically
(check with: sudo certbot renew --dry-run).

### L.3 Option B - IP address only: self-signed certificate

```
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/bmp.key -out /etc/ssl/certs/bmp.crt -subj "/CN=<VM_IP>" -addext "subjectAltName=IP:<VM_IP>"
```

Replace the whole content of /etc/nginx/sites-available/bmp (sudo nano ...) with:

```
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;
    ssl_certificate     /etc/ssl/certs/bmp.crt;
    ssl_certificate_key /etc/ssl/private/bmp.key;

    client_max_body_size 30m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Then "sudo nginx -t && sudo systemctl reload nginx". Browsers warn about the certificate on first visit (expected
for a self-signed certificate); choose Advanced > Continue. Renew before 365 days by repeating the openssl command.

### L.4 Option C - plain HTTP (trial only)

Nothing more to do (and COOKIE_SECURE=false must be set in .env, then: sudo systemctl restart bmp). Do not enter
real passwords or data this way.

---------------------------------------------------------------------------------------------------------
## PART M - Firewall

Allow SSH FIRST, otherwise enabling the firewall can lock you out of PuTTY:

```
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

(If your SSH port is not 22, allow that port instead.) PostgreSQL (5432) and the application (8000) are NOT
opened: they must stay reachable from the VM itself only. If the VM is in a cloud, also open 80/443 in the
provider's security group / network rules.

---------------------------------------------------------------------------------------------------------
## PART N - Verify the deployment

1. Health through Nginx:   curl -s https://<DOMAIN or VM_IP>/api/health   (add -k for a self-signed certificate)
2. In your browser open https://<DOMAIN or VM_IP>/ , sign in as admin@bmpco.in with the password you set,
   open a company, then Dashboard Overview, Directors & KMP Register, Activities & Tasks.
3. Upload a small PDF in Documents & Evidence, then download it again (checks the storage folder permissions).
4. Sign out, sign in as client@nexatech.co.in: only Nexatech is visible and there are no "+ Add" buttons.
5. Reboot test:  sudo reboot  - wait a minute, reconnect, and confirm the site works without any manual start.
6. (Optional) run the automated tests on the VM:

```
cd /opt/bmp && sudo -u bmp ./venv/bin/python -m pytest -q
```

   Expected: 307 passed (306 passed + 1 skipped if Node.js is not installed - that is fine). The tests create and
   delete a throw-away database "bmp_api_test"; they never touch the real "bmp" data.
7. (Optional) the Postman collection (docs/postman) can be pointed at the VM by setting baseUrl to
   https://<DOMAIN or VM_IP>. WARNING: it creates test records, so run it only on a demo/test database, never on a
   database holding real client data.

If the tests passed and you do not want the PostgreSQL administrator password kept in the file, delete the
DATABASE_URL_ADMIN line from /opt/bmp/.env (nano), then: sudo systemctl restart bmp. Put it back only when you
run set-up or tests again.

---------------------------------------------------------------------------------------------------------
## PART O - Backups (do this before real use)

Back up BOTH the database and the uploaded files. Create the script:

```
sudo nano /usr/local/bin/bmp-backup.sh
```

Paste:

```
#!/bin/bash
set -euo pipefail
DEST=/var/backups/bmp
STAMP=$(date +%F_%H%M)
mkdir -p "$DEST"
sudo -u postgres pg_dump -d bmp -Fc --data-only \
    --exclude-table=public.schema_migrations --exclude-table=public.schema_seeds \
    --exclude-table-data=activity.entity_field_registry > "$DEST/bmp_data_$STAMP.dump"
tar -czf "$DEST/bmp_storage_$STAMP.tar.gz" -C /opt/bmp storage
cp /opt/bmp/instance/users.json "$DEST/users_$STAMP.json"
chmod 600 "$DEST"/*
find "$DEST" -type f -mtime +14 -delete
```

Then:

```
sudo chmod 700 /usr/local/bin/bmp-backup.sh
sudo /usr/local/bin/bmp-backup.sh && ls -l /var/backups/bmp
sudo crontab -e
```

and add the line (every night at 02:00):

```
0 2 * * * /usr/local/bin/bmp-backup.sh >> /var/log/bmp-backup.log 2>&1
```

Copy the backups off the VM regularly with WinSCP (download /var/backups/bmp to your PC or a file server). A
backup that lives only on the same VM is not a backup.

Restoring a backup = the same as Part H Option 2: rebuild the structure with
"sudo -u bmp ./venv/bin/python scripts/setup_db.py" on an empty database (drop it first), then
"sudo -u postgres pg_restore -d bmp --data-only --disable-triggers <dump file>", extract the storage archive into
/opt/bmp, and put users.json back in /opt/bmp/instance. Practise this once on a spare database before you need it.

---------------------------------------------------------------------------------------------------------
## PART P - Deploying a new version later

On Windows: create a new archive exactly as in A.2 (it never contains .env, instance or storage, so your server
settings, passwords and files are untouched). Upload it with WinSCP to /home/<VM_USER>. Then in PuTTY:

```
sudo /usr/local/bin/bmp-backup.sh                       # safety copy first
sudo systemctl stop bmp
sudo tar -xzf ~/bmp_deploy.tar.gz -C /opt/bmp
sudo chown -R bmp:bmp /opt/bmp
cd /opt/bmp
sudo -u bmp ./venv/bin/pip install -r requirements.txt  # only matters if requirements.txt changed
sudo -u bmp ./venv/bin/python scripts/setup_db.py       # applies any NEW migration files only; safe to repeat
sudo systemctl start bmp
curl -s http://127.0.0.1:8000/api/health
```

Notes: extracting overwrites changed files but does not delete files you removed locally; remove those by hand if
it matters. Never edit the already-applied migration files 001-011; database changes are new numbered files
(012_...sql). Roll back by restoring the previous archive the same way (keep the last archive on the VM).

---------------------------------------------------------------------------------------------------------
## Troubleshooting

| Symptom                                                        | Likely cause and fix |
|----------------------------------------------------------------|----------------------|
| PuTTY "Connection timed out"                                   | VM off, wrong IP, or port 22 blocked by firewall/security group |
| WinSCP "Permission denied" when uploading                      | Upload to /home/<VM_USER> (not /opt/bmp); then move with sudo as in Part E |
| tar: "Cannot open: No such file"                               | You are in the wrong folder; run "ls ~" and use the real file name |
| pip install fails: "No matching distribution"                  | No internet from the VM, or an unsupported Python (need 3.10+); try the offline route A.4 |
| setup_db.py: "password authentication failed for user postgres"| PG_PW was not applied or .env was edited. Re-run the ALTER USER line and fix DATABASE_URL_ADMIN |
| setup_db.py: "extension vector is not available"               | postgresql-18-pgvector not installed (Part D) |
| Service fails: "APP_SECRET_KEY must be set"                    | .env missing/unreadable by user bmp: "sudo ls -l /opt/bmp/.env" must show owner bmp |
| Login says "Email or password is incorrect"                    | No password set yet (Part I "list"), or the user is inactive/missing in the database |
| Login seems to work then returns to the sign-in page           | HTTP site with COOKIE_SECURE=true. Use HTTPS, or set COOKIE_SECURE=false (trial only) and restart |
| "Too many failed sign-in attempts"                             | Wait 10 minutes or: sudo systemctl restart bmp |
| Nginx 502 Bad Gateway                                          | The app is not running: sudo systemctl status bmp ; sudo journalctl -u bmp -n 50 |
| Nginx 413 on upload                                            | client_max_body_size too small in the Nginx site file |
| Upload fails with a server error                               | Folder rights: sudo chown -R bmp:bmp /opt/bmp/storage |
| Browser cannot reach the site but curl on the VM works         | Firewall (ufw) or cloud security group is not open for 80/443 |
| Everything worked, then stopped after a reboot                 | sudo systemctl enable bmp ; sudo systemctl status postgresql nginx bmp |
| Disk filling up                                                | Check /var/backups/bmp, journalctl size (sudo journalctl --vacuum-time=14d) |

Useful checks: sudo systemctl status bmp nginx postgresql --no-pager ; sudo nginx -t ;
sudo -u postgres psql -d bmp -c "select count(*) from core.company;" ; df -h ; free -h

---------------------------------------------------------------------------------------------------------
## Security checklist before real data goes in

- [ ] HTTPS enabled (option A or B) and COOKIE_SECURE=true
- [ ] APP_ENV=production and a long random APP_SECRET_KEY
- [ ] .env is mode 600 and owned by bmp; passwords stored in your password manager
- [ ] Demo users either given new strong passwords or deactivated (Administration > Users)
- [ ] ufw enabled; only 22, 80, 443 open; PostgreSQL not exposed
- [ ] SSH: key-based login preferred; no root login (the default on Ubuntu images is already no password for root)
- [ ] Nightly backup running, and a copy taken off the VM; one test restore done
- [ ] Automatic security updates:  sudo apt install -y unattended-upgrades

---------------------------------------------------------------------------------------------------------
## One-page summary (order of work)

```
A  Windows: tar the project (no venv/.env/instance/storage); optional dump of local data
B  PuTTY + WinSCP sessions to the VM
C  VM: update, packages, user "bmp", folders
D  PostgreSQL 18 + pgvector
E  WinSCP upload -> sudo tar -xzf into /opt/bmp -> chown bmp
F  python3 -m venv ; pip install -r requirements.txt
G  .env with generated passwords (chmod 600)
H  setup_db.py --seed   (or: setup_db.py then pg_restore of your data)
I  manage_users.py set-password for each user
J  test run + /api/health
K  systemd service "bmp"
L  Nginx + HTTPS
M  ufw firewall
N  verify, reboot test
O  nightly backups (copy off the VM)
P  update procedure for later releases
```
