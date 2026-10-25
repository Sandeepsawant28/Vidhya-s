# Vidya's Liquor Loft: Inventory and Billing

A custom inventory and billing system built for **Vidya's Liquor Loft**, Fatorda, Goa. It runs in the browser, works on phones and computers, and can run either on the shop PC with no internet or online on Render with a Neon database.

> Premium spirits. Exceptional experiences.

## Features

- **Billing:** barcode scan, brand search or quick-pick buttons. Payment by cash, UPI, card, credit or split. Stock reduces automatically with every bill.
- **Inventory:** brand, category, size, barcode, MRP, purchase price and reorder level for every product. Live stock is calculated from stock movements and is never edited directly.
- **Purchase entry:** add stock from suppliers with invoice details.
- **Credit customers:** balances, ledger and payments received.
- **Dashboard:** today's sales, comparison with yesterday, last 7 days, payment mode split, low stock, recent bills and credit outstanding.
- **Reports:** daily closing and sales summaries (owner only).
- **Roles:** Owner and Cashier. Cashiers cannot see cost prices, profit or owner-only reports.
- **Audit log:** edits and cancellations are recorded.
- **Backups:** a management command copies the database into dated files.
- **Installable on phones:** works as a home screen app (PWA).
- **First-run setup wizard:** enter shop details and create the owner account. There are no default passwords.

## Tech stack

| Part | Choice |
|---|---|
| Language | Python 3.12 or newer |
| Framework | Django |
| Database (local) | SQLite, with WAL mode |
| Database (online) | PostgreSQL on Neon |
| Web server | gunicorn (online), waitress (shop PC) |
| Static files | WhiteNoise |
| Frontend | Django templates, plain CSS and vanilla JavaScript. No CDN, so it works offline. |

## Project structure

```
liquor-shop/
  core/               models, views, forms, middleware, management commands
  liquor_shop/        Django settings, urls, wsgi
  static/             css, js, icons, manifest.json, sw.js
  templates/          billing, customers, inventory, purchase, reports, settings
  manage.py
  requirements.txt
  backup.bat
  build.bat
```

## Run it locally (Windows)

1. Install Python from python.org and tick **Add python.exe to PATH**.
2. Open the project folder in a terminal and run:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

3. Open `http://127.0.0.1:8000` in Chrome.

To see sample data for testing, run this once (never on a real shop database):

```
python manage.py seed_data
```

To see detailed error pages while testing, set `DJANGO_DEBUG=True` for that terminal only:

```
set DJANGO_DEBUG=True
```

### Where local data is stored

On Windows, the database, backups, logs and secret key are kept outside the project folder so updates never delete shop data:

```
C:\ProgramData\LiquorShop\
```

## Use it on phones (shop Wi-Fi)

1. Connect the phone to the same Wi-Fi as the shop PC.
2. Find the PC's address with `ipconfig` (the IPv4 address, for example `192.168.1.10`).
3. Open `http://192.168.1.10:8000` in Chrome on the phone.
4. Tap the three dots, then **Add to Home screen**.

Reserve a fixed address for the PC in the router so phones always find it. On Windows, allow port 8000 through the firewall when asked.

## Deploy online (Render and Neon)

The online version needs a PostgreSQL database. Render's own disk is wiped on every restart, so data must live in Neon.

### 1. Create the database

Create a free project on [Neon](https://neon.tech) and copy the connection string (it starts with `postgresql://` and ends with `?sslmode=require`). Keep it private.

### 2. Create the Render web service

Connect this GitHub repository and set:

| Setting | Value |
|---|---|
| Build Command | `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate` |
| Start Command | `gunicorn liquor_shop.wsgi` |

### 3. Environment variables

| Name | Value |
|---|---|
| `DATABASE_URL` | Your Neon connection string |
| `DJANGO_SECRET_KEY` | A long random text |
| `PYTHON_VERSION` | Optional, for example `3.12.3` |

Never commit these values to GitHub.

### 4. First login

Open the Render address. The setup wizard appears once. Enter the shop details and create the owner account.

To check that data is really saved, redeploy once from Render. The app should open at the login page, not the setup wizard.

## Backups

On the shop PC:

```
python manage.py backup_db
```

This creates a dated copy of the SQLite database in the backups folder. Schedule it every night with Windows Task Scheduler, copy it to a USB drive, and test a restore once a month.

On Neon, create a child branch under **Branches** before big changes, and export reports regularly.

## Roles

| Role | Can do |
|---|---|
| Owner | Everything: purchases, reports, profit, settings, cancellations, users |
| Cashier | Billing, stock lookup and credit payments. No cost prices, profit or owner reports. |

Use strong passwords, give each person their own login, and never share the owner login.

## Useful commands

| Command | What it does |
|---|---|
| `python manage.py migrate` | Creates or updates the database tables |
| `python manage.py createsuperuser` | Creates an owner login |
| `python manage.py collectstatic --noinput` | Collects design files for production |
| `python manage.py seed_data` | Adds sample products (testing only) |
| `python manage.py backup_db` | Makes a dated database backup |
| `python manage.py check` | Checks the project for problems |

## Important notes

- Local and online copies have **separate databases**. They never sync. Use one address for real work.
- Do not enter real stock or bills until you have confirmed that the database is saving correctly.
- Excise and billing rules differ by state. Check with your accountant or excise office for required bill formats, registers and record keeping before going live.
- Run the app beside your old register for one to two weeks before relying on it.

## Files to keep out of GitHub

Add a `.gitignore` containing at least:

```
venv/
__pycache__/
*.pyc
db.sqlite3
data/
staticfiles/
.env
*.bak
```
