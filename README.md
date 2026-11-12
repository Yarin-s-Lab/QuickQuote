# QuickQuote — מחולל הצעות מחיר

סוכן ביטוח ממלא טופס ומקבל הצעת מחיר בעברית. האפיון המלא: [`SPEC.md`](SPEC.md). כללי עבודה: [`CLAUDE.md`](CLAUDE.md).

**סטטוס: רמה 1** — מנוע פרמיה (רכב, דירה) עם בדיקות, `GET /api/products`, `POST /api/quotes/preview`, וטופס React ב-RTL.
עדיין אין שמירה, PDF, Docker או CI (רמות 2–3).

## הרצה מקומית

דרישות: Python 3.12+ ו-Node 20+.

```bash
# backend — http://localhost:8000
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows; macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# frontend — http://localhost:5173 (מעביר את /api ל-8000 דרך proxy)
cd frontend
npm ci
npm run dev
```

## בדיקות ו-lint

```bash
cd backend  && pytest && ruff check . && ruff format --check .
cd frontend && npm test && npm run lint && npm run build
```

## הגדרות

| משתנה | ברירת מחדל | שימוש |
|-------|------------|-------|
| `FRONTEND_ORIGIN` | `http://localhost:5173` | המקור היחיד שמותר ב-CORS (backend) |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | יעד ה-proxy של `/api` ב-`npm run dev` |
| `VITE_API_BASE` | ריק | כתובת בסיס ל-API כשאין proxy (build) |
