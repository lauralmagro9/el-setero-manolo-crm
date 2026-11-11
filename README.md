# El Setero Manolo CRM

Central database and API of the business (see `../El_Setero_Manolo_Data_Model_v2.xlsx` and `../Background El Setero Manolo.txt`).

- **Database**: Postgres. Development runs on Supabase local (Docker); production on Supabase cloud. Alembic owns the `public` schema.
- **Auth**: Supabase Auth (email + password, public sign-up disabled). The API validates the Supabase JWT on every `/api` call.
- **API**: FastAPI (`/api/...`, docs at `/docs`). Business logic lives in `services/` so future agents reuse it.
- **Voice notes**: audio is transcribed with Groq (Whisper Large V3 Turbo) and only the transcript is stored (as a *pending* interaction).

## Development

Requirements: Docker Desktop, Node (for `npx supabase`) and Poetry.

```bash
npx supabase start
```

Copy `.env.example` to `.env` (the defaults match Supabase local) and set `SERVICES_GROQ_API`. Then:

```bash
poetry install
poetry run alembic upgrade head
poetry run python -m crm.seed
poetry run uvicorn --factory crm.api.app:create_app --reload
poetry run pytest
```

Frontend (React + Vite, Spanish UI) in `frontend/`:

```bash
cd frontend
npm install
cp .env.example .env.local   # fill VITE_SUPABASE_ANON_KEY from `npx supabase status`
npm run dev                  # https://localhost:5173 (self-signed; VITE_HTTPS=false for plain HTTP)
npm run build
```

To test the microphone from a phone on the LAN, open `https://<your-pc-ip>:5173` (HTTPS is required).

| Service | URL |
|---|---|
| Frontend (dev) | https://localhost:5173 |
| API / docs | http://localhost:8000 · http://localhost:8000/docs |
| Supabase Studio (create users, edit orders/stock/invoices) | http://localhost:54323 |
| Postgres | 127.0.0.1:54322 (tests use the `setero_pytest` database, created automatically) |

Create Laura's and Manolo's users in Studio → Authentication → Users (sign-up is disabled).

## End-to-end environment

```bash
poetry run pytest -m e2e
```

Independent of the rest of the tests (a plain `pytest` skips it). It runs `alembic upgrade head`, **empties every table of `public` except `alembic_version`** in `DATABASE_URL` (the Supabase credentials in the `auth` schema are not touched), loads the seed data (`tests/data/seed.py`), builds the frontend and deploys everything on **http://127.0.0.1:8010**. The app **stays running after the tests** (detached; output in `.e2e/server.log`) with the seeded data, so you can log in and use it; the next e2e run replaces it. To stop it by hand, kill the pid in `.e2e/server.pid`. It refuses to run if the database host is not in `[e2e] allowed_database_hosts` (`settings.toml`).

## Invoicing

Facturas → Nueva factura issues an invoice without an order. An invoice belongs to a single company, and its customer data comes from the company's **billing data** (nombre fiscal, NIF/CIF fiscal and dirección fiscal), so a fruit shop run by a self-employed person is invoiced under the owner's name.

- Existing company: its billing data is copied into the invoice (edit them from the form if they are missing). New company: every company field is required, plus the billing data, and it is created together with the invoice in one transaction.
- The copy means editing the company later never changes an issued invoice.
- Dates: fecha de expedición and fecha de operación (both default to today). Number `VDA-<year of the issue date>-<0001>`, one sequence per series and year.
- Lines: the product is mandatory; the form shows the total without VAT and with VAT live (calculated by the API, VAT 10 % from `[invoicing] vat_rate`).
- Only the VDA series can be issued for now (`[invoicing] enabled_types`); Agrario and Empresa already exist in the model.
- Seller data (`ISSUER_NAME`, `ISSUER_TAX_ID`, `ISSUER_ADDRESS`) and the logo (`assets/logo.png`) are printed on the PDF; without them no invoice can be issued.
- Email: set `EMAIL_ENABLED=true`, `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_SSL` (true for port 465), `EMAIL_SMTP_USERNAME`, `EMAIL_SMTP_PASSWORD`, `EMAIL_SENDER` and `EMAIL_INVOICE_RECIPIENT` in `.env`. Every invoice is sent to that configured address (the customer is not emailed; the invoice carries no email or phone). Status: `pending` (email disabled or not sent yet), `sent`, `failed` (the invoice is kept; use *Enviar* to retry).

## Audit columns and soft delete

Every table inherits these columns from `Base` (`models.py`), so a new table gets them without writing anything: `created_at`, `modified_at`, `created_by` (all NOT NULL), and `deleted_at` / `deleted_by`.

- `created_by` is the logged-in user's email (the API binds it per request in `api/auth.py::bind_actor`); scripts, agents and the seed are recorded as `system` (`[audit] default_actor`). Code that inserts with raw SQL must fill the three columns itself (see `services/invoices.py::_next_number`).
- **Deleting never removes rows.** `services/deletion.py::delete_record(session, Model, id)` sets `deleted_at` / `deleted_by`; from then on the row is invisible to every ORM query and to the SQL views. `execution_options(include_deleted=True)` shows deleted rows; to restore one, set its `deleted_at` back to NULL.
- What happens to related records is declared in `DELETE_RULES`: *cascade* (a company takes its contacts, interactions and orders with it), *detach* (deleting a contact keeps its interactions, without contact) or *block* (a company with invoices, or a product used by lots or orders, cannot be deleted: the API answers 409 with the reason).
- Uniqueness (company NIF, product name, lot code, interaction external id) only counts live rows, so a deleted name or NIF can be reused. Invoice numbers stay unique forever: a deleted invoice leaves a gap in the numbering.
- New views must filter `deleted_at IS NULL` (see `views.py`).

## Security

Only the backend may read or write data. The frontend uses Supabase just to log in.

- `security.secure_public_schema` enables Row Level Security on every table of `public` and revokes the `anon`/`authenticated` grants (this also protects the SQL views). It runs in the migration `secure_public_schema`.
- **Every migration that creates tables or views must end by calling `secure_public_schema(op.get_bind())`.** `tests/test_security.py` fails if a table is left open.
- Local: the Supabase Data API is disabled in `supabase/config.toml` (`[api] enabled = false`).
- Cloud: disable it too (Project Settings -> Data API) and keep `DATABASE_URL` (the pooler URL) and the Groq key only in the hosting provider's environment variables.
- Running `pytest` empties the database in `DATABASE_URL`; point it at a throw-away database when that matters.

## Layout

- `crm/models.py`: tables (SQLAlchemy 2). Only real data is stored.
- `crm/views.py`: SQL views with every calculated value; `view_models.py` maps them read-only.
- `crm/schemas.py`: Pydantic input/output schemas.
- `crm/services/`: business logic (companies, interactions, dashboard, transcription).
- `crm/api/`: FastAPI app, JWT auth and routers.
- `crm/config.py`: `settings.toml` defaults overridden by `.env` and environment variables (`[services] groq_api` -> `SERVICES_GROQ_API`).
- `frontend/`: React + Vite + Tailwind app. Brand tokens (colours, dark mode) are in `src/index.css`; data access only through `src/lib/api.ts`.
- `supabase/config.toml`: Supabase local configuration.
- `migrations/`: Alembic (only manages `public`). If you change a view, add a migration that drops and recreates it.
