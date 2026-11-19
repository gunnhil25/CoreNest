# 🏠 CoreNest — Household Finance Tracker

A modern household rent and shared expense tracking web application (**CoreNest**) with a **FastAPI (Python 3.12)** backend and **PostgreSQL 16** database, fully containerized with **Docker** and automatically built & published to GitHub Container Registry (`ghcr.io/gunnhil25/corenest:latest`) via GitHub Actions.

---

## 🚀 Quick Start (Prebuilt Image via GHCR)

The fastest way to deploy **CoreNest** on a server or Proxmox LXC is by pulling the prebuilt image from GitHub Container Registry:

```bash
# 1. Clone this repository
git clone https://github.com/gunnhil25/CoreNest.git
cd CoreNest

# 2. (Optional) Customize database passwords or port in .env
cp .env.example .env

# 3. Pull the latest images and start the stack
docker compose pull
docker compose up -d
```

> **Note for private repositories:** If the GitHub repository or GHCR package is private, authenticate Docker once with a GitHub Personal Access Token (`read:packages` scope):
> ```bash
> echo "<YOUR_GITHUB_PAT>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
> ```

Once running:
* **Web Application:** `http://<YOUR_SERVER_IP>:8000/` (On first launch, you will be prompted to **Create an Admin Account**.)
* **Interactive API Docs (Swagger UI):** `http://<YOUR_SERVER_IP>:8000/docs`
* **Database Health Check:** `http://<YOUR_SERVER_IP>:8000/api/health`

> **HTTPS Reverse Proxy Note:** By default, `COOKIE_SECURE=false` is set so HTTP deployments (such as a local Proxmox LXC) work out of the box. If you serve CoreNest behind an HTTPS reverse proxy (Nginx, Caddy, Traefik), set `COOKIE_SECURE=true` in `.env`.

### Building Locally from Source (Optional)
If you prefer to build the image locally instead of pulling from GHCR (do not pass `--build` when using the prebuilt GHCR image):
```bash
docker compose up -d --build
```

### Updating to the Latest Release
Whenever new changes are pushed to `main`, GitHub Actions builds, smoke-tests, and publishes an updated `:latest` image. To update your running instance:
```bash
docker compose pull
docker compose up -d
```

---

## 📦 Proxmox LXC Deployment Guide

### Step-by-Step Setup (Docker inside an LXC Container)
If you are running Docker inside a Proxmox LXC container (e.g., Debian 12 or Ubuntu 24.04 template):

1. **Enable LXC features for Docker:**
   - In the Proxmox VE Web UI, select your LXC container → **Options** → **Features**.
   - Enable **`nesting=1`** and **`keyctl=1`** (required for Docker inside an unprivileged LXC), then reboot the LXC if prompted.

2. **Install Docker & Docker Compose plugin inside the LXC:**
   ```bash
   apt-get update && apt-get install -y curl git
   curl -fsSL https://get.docker.com | sh
   ```
   Verify installation:
   ```bash
   docker --version
   docker compose version
   ```

3. **Clone the repository and configure environment:**
   ```bash
   git clone https://github.com/gunnhil25/CoreNest.git /opt/corenest
   cd /opt/corenest
   cp .env.example .env
   # Optional: edit .env to set custom POSTGRES_PASSWORD or PORT
   nano .env
   ```

4. **Pull the image and launch the stack:**
   ```bash
   # (Only needed if the GHCR package is private)
   # docker login ghcr.io -u gunnhil25

   docker compose pull
   docker compose up -d
   ```

5. **Verify the deployment:**
   ```bash
   docker compose ps
   curl -s http://localhost:8000/api/health
   ```
   You should see `"status":"ok"` and `"database":"connected"`.

6. **Auto-start on LXC boot:**
   Both services use `restart: unless-stopped`, so they start automatically whenever your Proxmox LXC boots.

---

## ⚙️ CI/CD Pipeline (GitHub Actions)

Every push or pull request on any branch triggers [`.github/workflows/docker.yml`](.github/workflows/docker.yml):
1. Builds the Docker image from `Dockerfile` using Buildx with GitHub Actions layer caching.
2. Starts the full `docker compose` stack (`db` + `web`) and runs end-to-end smoke tests covering `/api/health`, `/`, initial admin setup, authentication, and role-based access control.
3. On branch pushes (non-PR), pushes the verified image to GHCR (`ghcr.io/gunnhil25/corenest:<branch>` and commit SHA tags, plus `:latest` on `main`).

---

## 👥 Users, Roles & Permissions

On a fresh deployment (0 users in the database), CoreNest opens directly to the **Create an Admin Account** setup screen. Once the initial administrator is created, the app requires signing in and enforces two roles:

| Capability | `admin` | `user` |
|---|---|---|
| View Settlement Overview & Spending Analytics | Yes | Yes |
| View all Transactions | Yes | Yes |
| Record new Transactions | Yes | Yes |
| Edit / Delete own recorded Transactions | Yes | Yes |
| Edit / Delete other users' Transactions | Yes | No (`403`) |
| Manage Users (create, change role, reset password, delete) | Yes | No |
| Manage Household Members & Categories | Yes | No |
| Export JSON / CSV & Import JSON backups | Yes | No |
| Change own Password | Yes | Yes |

---

## 🛠️ Architecture & Features

```
┌────────────────────────────────────────────────────────┐
│                   Proxmox LXC Container                │
│                                                        │
│   ┌───────────────────────┐   ┌────────────────────┐   │
│   │     rent_app_web      │   │    rent_app_db     │   │
│   │     (FastAPI 3.12)    │   │  (Postgres 16)     │   │
│   │                       │   │                    │   │
│   │  • Serves Frontend    │◄──┼─► • Relational DB  │   │
│   │  • Auth & RBAC API    │   │   • Users/Sessions │   │
│   │  • Atomic /api/data   │   │   • Named Volume   │   │
│   └──────────▲────────────┘   └────────────────────┘   │
└──────────────┼─────────────────────────────────────────┘
               │ Port 8000
        ┌──────┴──────┐
        │   Browser   │
        └─────────────┘
```

* **Backend:** FastAPI with `asyncpg`, SQLAlchemy 2.0, `scrypt` password hashing, and server-side `HttpOnly` cookie sessions.
* **Database:** PostgreSQL 16 Alpine with persistent volume `rent_app_postgres_data`.
* **Frontend:** Left-hand sidebar console with mobile slide-over drawer, Dark/Light theme, monthly spending trends, category donuts, settlement balance calculation, category filtering & sorting, and role-aware UI.
* **Full Persistence:** All users, sessions, members, categories, and transactions are stored in PostgreSQL.
* **Zero-Setup Seeding:** Automatically seeds default household categories (Rent, Groceries, Utilities, etc.) if the database is fresh.

---

## 🗄️ Database Management & Backups

### Creating a Database Backup
```bash
docker exec -t rent_app_db pg_dump -U rentapp household_tracker > backup_$(date +%F).sql
```

### Restoring from Backup
```bash
cat backup_2026-10-22.sql | docker exec -i rent_app_db psql -U rentapp household_tracker
```

### In-App Data Export/Import
Admins can also back up or transfer household data at any time through the web UI under **Settings → Data Management** (Export JSON / Export CSV / Import JSON).

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/` | Public | Web application UI |
| `GET` | `/api/health` | Public | Backend & database health check |
| `GET` | `/api/auth/status` | Public | Initialization & session status |
| `POST` | `/api/auth/setup` | Public (uninitialized only) | Create initial admin account |
| `POST` | `/api/auth/login` | Public | Sign in and set session cookie |
| `POST` | `/api/auth/logout` | Public | Revoke session & clear cookie |
| `GET` | `/api/auth/me` | Authenticated | Get current user profile |
| `POST` | `/api/auth/change-password` | Authenticated | Change own password |
| `GET` | `/api/users` | Admin | List all user accounts |
| `POST` | `/api/users` | Admin | Create user or admin account |
| `PUT` | `/api/users/{user_id}` | Admin | Update display name, role, or password |
| `DELETE` | `/api/users/{user_id}` | Admin | Delete user account |
| `GET` | `/api/data` | Authenticated | Fetch complete household state |
| `POST` | `/api/data` | Admin | Synchronize full state atomically (JSON import) |
| `GET` | `/api/members` | Authenticated | List household members |
| `POST` | `/api/members` | Admin | Add new member |
| `PUT` | `/api/members/reorder` | Admin | Reorder household members |
| `DELETE` | `/api/members/{name}` | Admin | Remove member and their transactions |
| `GET` | `/api/categories` | Authenticated | List expense categories |
| `POST` | `/api/categories` | Admin | Create new category |
| `PUT` | `/api/categories/reorder` | Admin | Reorder expense categories |
| `PUT` | `/api/categories/{name}` | Admin | Update category icon/color |
| `DELETE` | `/api/categories/{name}` | Admin | Delete category |
| `GET` | `/api/expenses` | Authenticated | List/filter transactions (query by category, payer, sort) |
| `POST` | `/api/expenses` | Authenticated | Record a new expense or income |
| `PUT` | `/api/expenses/{id}` | Admin or Owner | Edit a transaction |
| `DELETE` | `/api/expenses/{id}` | Admin or Owner | Delete a transaction |
