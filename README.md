# 🏠 CoreNest — Household Finance Tracker

A modern household rent and shared expense tracking web application (**CoreNest**) with a **FastAPI (Python 3.12)** backend and **PostgreSQL 16** database, fully containerized with **Docker** and automatically built & published to GitHub Container Registry (`ghcr.io/gunnhil25/rent_app:latest`) via GitHub Actions.

---

## 🚀 Quick Start (Prebuilt Image via GHCR)

The fastest way to deploy **CoreNest** on a server or Proxmox LXC is by pulling the prebuilt image from GitHub Container Registry:

```bash
# 1. Clone this repository
git clone https://github.com/gunnhil25/rent_app.git
cd rent_app

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
* **Web Application:** `http://<YOUR_SERVER_IP>:8000/`
* **Interactive API Docs (Swagger UI):** `http://<YOUR_SERVER_IP>:8000/docs`
* **Database Health Check:** `http://<YOUR_SERVER_IP>:8000/api/health`

### Building Locally from Source (Optional)
If you prefer to build the image locally instead of pulling from GHCR:
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
   git clone https://github.com/gunnhil25/rent_app.git /opt/corenest
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

Every push or pull request to `main` triggers [`.github/workflows/docker.yml`](.github/workflows/docker.yml):
1. Builds the Docker image from `Dockerfile` using Buildx with GitHub Actions layer caching.
2. Starts the full `docker compose` stack (`db` + `web`) and smoke-tests `/api/health` and `/`.
3. On pushes to `main`, pushes the verified image to `ghcr.io/gunnhil25/rent_app:latest` (along with `main` and commit SHA tags).

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
│   │  • REST API endpoints │   │   • Named Volume   │   │
│   │  • Atomic /api/data   │   │     Persistence    │   │
│   └──────────▲────────────┘   └────────────────────┘   │
└──────────────┼─────────────────────────────────────────┘
               │ Port 8000
        ┌──────┴──────┐
        │   Browser   │
        └─────────────┘
```

* **Backend:** FastAPI with `asyncpg` and SQLAlchemy 2.0.
* **Database:** PostgreSQL 16 Alpine with persistent volume `rent_app_postgres_data`.
* **Frontend:** Glassmorphism UI with Dark/Light theme, monthly spending trends, category donuts, settlement balance calculation, and category filtering & sorting.
* **Full Persistence:** All members, categories, and transactions are stored in PostgreSQL.
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
You can also back up or transfer your data at any time directly through the web UI under **Settings → Data Management** (Export JSON / Export CSV / Import JSON).

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web application UI |
| `GET` | `/api/health` | Backend & database health check |
| `GET` | `/api/data` | Fetch complete household state |
| `POST` | `/api/data` | Synchronize full state atomically |
| `GET` | `/api/members` | List household members |
| `POST` | `/api/members` | Add new member |
| `DELETE` | `/api/members/{name}` | Remove member and their transactions |
| `GET` | `/api/categories` | List expense categories |
| `POST` | `/api/categories` | Create new category |
| `PUT` | `/api/categories/{name}` | Update category icon/color |
| `DELETE` | `/api/categories/{name}` | Delete category |
| `GET` | `/api/expenses` | List/filter transactions (query by category, payer, sort) |
| `POST` | `/api/expenses` | Record a new expense or income |
| `PUT` | `/api/expenses/{id}` | Edit a transaction |
| `DELETE` | `/api/expenses/{id}` | Delete a transaction |
