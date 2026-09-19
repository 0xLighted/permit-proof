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

### 1. Backend Server (FastAPI + SQLite)

```powershell
# Install dependencies & seed demo fixtures
uv run seed

# Run the API server (port 8080)
uv run server
```

### 2. Database Management & CLI Tools

```powershell
# Interactive CRUD menu for demoing
uv run manage

# Interactive database table navigator & row inspector
uv run view-db

# Run full test suite
uv run pytest
```

### 3. Frontend Dashboard (React + Vite)

```powershell
cd frontend
npm install
npm run dev
```

Open your browser to `http://localhost:3000` (or `http://localhost:5173`) to view the industrial dashboards:
- **Station Launcher**: Central portal connecting roles.
- **Supervisor Dashboard**: Dispatch inspection permits and view real-time audit logs.
- **Technician Dashboard**: View assigned jobs, simulate NFC badge tap, and complete procedures.
