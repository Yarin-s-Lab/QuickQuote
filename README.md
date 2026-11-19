# QuickQuote — מחולל הצעות מחיר

סוכן ביטוח ממלא טופס ומקבל הצעת מחיר בעברית, כקובץ PDF. האפיון המלא: [`SPEC.md`](SPEC.md). כללי עבודה: [`CLAUDE.md`](CLAUDE.md).

**סטטוס: רמה 2**
- מנוע פרמיה (רכב, דירה), תצוגה מקדימה, טופס React ב-RTL.
- יצירת הצעה: מספור `Q-YYYY-NNNNNN`, שמירה ב-SQLite, ו-PDF בעברית (WeasyPrint, גופנים מוטמעים).
- Docker לשני השירותים.

עדיין אין: הורדה מאובטחת לפי טוקן, בדיקת Snapshot, CI (רמה 3).

## הרצה ב-Docker (מומלץ — כולל יצירת PDF)

```bash
docker compose up --build        # הטופס: http://localhost:8080
docker compose run --rm backend pytest     # כל הבדיקות, כולל PDF, בלי דילוגים
docker compose down              # עצירה (הנתונים נשמרים ב-volumes)
docker compose down -v           # עצירה ומחיקת ה-DB וקובצי ה-PDF
```

- ה-frontend (nginx) מעביר את `/api` ל-backend ברשת הפנימית. ה-backend לא חשוף על פורט במחשב.
- ה-DB נמצא ב-volume ‏`qq-data` (`/data`), וקובצי ה-PDF ב-volume ‏`qq-storage` (`/storage`).
- ב-Windows, Docker Desktop צריך לרוץ במצב **Linux containers**.

## הרצה מקומית (פיתוח)

דרישות: Python 3.12+ ו-Node 20+.

```bash
# backend — http://localhost:8000
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows; macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app

# frontend — http://localhost:5173 (מעביר את /api ל-8000 דרך proxy)
cd frontend
npm ci
npm run dev
```

**PDF מקומית:** WeasyPrint צריך את הספריות Pango ו-HarfBuzz, שאינן מותקנות כברירת מחדל ב-Windows. בלעדיהן:
- `POST /api/quotes` מחזיר `503 pdf_unavailable`.
- בדיקות ה-PDF (`tests/pdf` ושתי בדיקות ב-`tests/security`) מדולגות עם הסבר.

כל השאר רץ מקומית, כולל רינדור ה-HTML ובדיקות האבטחה. ליצירת PDF השתמשו ב-Docker.

ב-Windows עם Python 3.15, `uvicorn --reload` לפעמים לא טוען מחדש בפועל וממשיך להריץ קוד ישן. אם שינוי לא נקלט, הפעילו את השרת מחדש.

## בדיקות ו-lint

```bash
cd backend  && pytest && ruff check . && ruff format --check .
cd frontend && npm test && npm run lint && npm run build
```

## הגדרות

| משתנה | ברירת מחדל | שימוש |
|-------|------------|-------|
| `DATABASE_URL` | `sqlite:///./data/quickquote.db` | ה-DB (ב-Docker: `sqlite:////data/quickquote.db`) |
| `STORAGE_DIR` | `./storage` | תיקיית קובצי ה-PDF (ב-Docker: `/storage`) |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | המקור היחיד שמותר ב-CORS (ב-Docker: `http://localhost:8080`) |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | יעד ה-proxy של `/api` ב-`npm run dev` |
| `VITE_API_BASE` | ריק | כתובת בסיס ל-API כשאין proxy |

## גופנים

`backend/app/fonts/` מכיל את Noto Sans Hebrew ואת Noto Sans (לטיני). Noto Sans נדרש לספרות ולאנגלית, שאינן קיימות בגופן העברי. שני הגופנים ברישיון SIL OFL 1.1 (ראו `OFL.txt`).
