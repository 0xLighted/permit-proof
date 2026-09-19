# PermitProof — Industrial IoT Zero-Trust Access & Permit Verification

PermitProof provides a fail-safe, cryptographic zero-trust verification system for industrial plant maintenance workflows and server-room access control. It combines physical NFC card taps with time-bound, out-of-band email approvals, database pre-approval validation, and HMAC anti-replay protection.

---

## 📁 Repository Structure

```text
permit-proof/
├── DESIGN.md                  # Industrial UI/UX design tokens & style guide
├── STAGE2_HANDOFF.md          # Cryptographic protocol & architecture specification
├── pyproject.toml             # Python package configuration, dependencies, and CLI entrypoints
│
├── src/
│   └── server/                # FastAPI Zero-Trust Access API & Database Engine
│       ├── __init__.py        # Exports app, main, db
│       ├── crypto.py          # HMAC-SHA256 derivation & signature verification
│       ├── db.py              # SQLite database manager (WAL mode + foreign keys)
│       ├── email_service.py   # Out-of-band magic link dispatcher
│       ├── main.py            # FastAPI access control protocol & jobs gateway
│       ├── schemas.py         # Pydantic request/response contracts
│       └── scripts/           # Management & demo CLI tools
│           ├── manage.py      # CRUD commands & interactive console menu
│           ├── db_viewer.py   # Interactive database table navigator
│           └── seed.py        # Demo data seeder
│
├── frontend/                  # React 19 + TypeScript + Vite Industrial Dashboard
│   ├── package.json           # Frontend dependencies & scripts
│   ├── vite.config.ts         # Vite configuration & proxy settings
│   ├── index.html             # Application entrypoint
│   └── src/
│       ├── main.tsx           # React root
│       ├── App.tsx            # Role routing (Station Launcher, Supervisor, Technician)
│       ├── api.ts             # API client adapter
│       ├── types.ts           # Frontend TypeScript types
│       ├── index.css          # Industrial design system tokens & base styles
│       ├── pages/             # Dashboards (Launcher, Supervisor, Technician)
│       └── components/        # UI components (JobCard, AuthPanel, AuditLog, Shell)
│
└── test/
    ├── test_api.py            # 19 tests: API protocols, replay protection, audit privacy
    └── test_cli.py            # 4 tests: CLI CRUD & database viewer validation
```

---

## 🚀 Quick Start

### 1. Build the Frontend Application

Before running the unified web portal on a production/LAN server, compile the frontend assets:

```bash
# On Linux / macOS:
./build.sh

# On Windows:
build.bat

# Or using npm / uv:
npm run build
uv run build-frontend
```

This compiles the React 19 + Vite frontend directly into `frontend/dist`.

---

### 2. Run the Unified Application Server

Start the FastAPI application server, which hosts both the API and the compiled frontend dashboard on port 8000 (accessible across the LAN):

```bash
# On Linux / macOS:
./start.sh
# or: uv run server

# On Windows:
start.bat
# or: uv run server
```

The server binds to `0.0.0.0:8000` and automatically prints the local & LAN IP access links:
- **Web Portal / Launcher**: `http://<server-ip>:8000/`
- **Technician Terminal**: `http://<server-ip>:8000/technician`
- **Supervisor Console**: `http://<server-ip>:8000/supervisor`
- **Swagger API Docs**: `http://<server-ip>:8000/docs`
- **System Health Check**: `http://<server-ip>:8000/health`

---

### 3. Database Management & CLI Tools

```bash
# Seed initial demo database fixtures
uv run seed

# Interactive CRUD menu for demoing
uv run manage

# Interactive database table navigator & row inspector
uv run view-db

# Run full test suite (29 tests)
uv run pytest
```

---

### 4. Optional: Frontend Standalone Development Server

If actively developing frontend UI components with Vite hot module replacement (HMR):

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000/` in your browser. All `/api/*` calls will automatically proxy to the backend on `http://localhost:8000`.

