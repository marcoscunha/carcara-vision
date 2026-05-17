# Carcara Vision Backend

FastAPI backend for Carcara Vision - Hardware-Accelerated ML Inference Platform.

## Database migration (single baseline)

This backend now uses a single Alembic baseline revision:

- Revision: `20260221_0001`
- Location: `src/db/migrations/versions/20260221_0001_baseline_schema.py`

### Fresh install (new machine / empty database)

No extra step is required. Start the stack and the backend migration step will run:

```bash
docker compose up -d --build
```

### Existing database (already has tables/data)

Before running upgrades with the new migration history, stamp the database to the baseline:

```bash
cd backend
.venv/bin/alembic stamp 20260221_0001
.venv/bin/alembic upgrade head
```

If your environment does not use `.venv`, run `alembic` with the Python environment used by the backend container/project.

See the main [README.md](../README.md) in the project root for full documentation.
