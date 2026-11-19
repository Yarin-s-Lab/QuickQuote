# QuickQuote — מחולל הצעות מחיר

[![CI](https://github.com/talShporenMadanes/QuickQuote/actions/workflows/ci.yml/badge.svg)](https://github.com/talShporenMadanes/QuickQuote/actions/workflows/ci.yml)

סוכן ביטוח ממלא טופס קצר ומקבל הצעת מחיר בעברית, כקובץ PDF מוכן לשליחה ללקוח.
האפיון המלא: [`SPEC.md`](SPEC.md). כללי עבודה: [`CLAUDE.md`](CLAUDE.md).

## מה יש (רמות 1–3)

| רמה | יכולת |
|-----|-------|
| 1 | מנוע פרמיה לרכב ולדירה (`Decimal`, עיגול `ROUND_HALF_UP`, מינימום 500 ₪) · תצוגה מקדימה · טופס React בעברית וב-RTL |
| 2 | יצירת הצעה: שמירה ב-SQLite ו-PDF בעברית (WeasyPrint עם גופנים מוטמעים) · Docker לשני השירותים |
| 3 | מספור `Q-YYYY-NNNNNN` שעומד בבקשות מקבילות · הורדה מאובטחת לפי טוקן עם תוקף של 30 יום · בדיקות Snapshot ל-HTML ול-PNG · CI ב-GitHub Actions |

**הזרימה:** ממלאים את הטופס ← "חשב פרמיה" (תצוגה מקדימה) ← "צור הצעה" ← מקבלים מספר הצעה וקישור "הורדת PDF".
הקישור עובד שוב ושוב עד תאריך התוקף. אחרי התוקף הוא מחזיר `410`.

## הרצה ב-Docker (מומלץ — כולל יצירת PDF)

```bash
docker compose up --build                       # הטופס: http://localhost:8080
docker compose run --rm backend pytest          # כל הבדיקות, כולל PDF ו-Snapshot
docker compose run --rm backend pytest tests/snapshot
docker compose down                             # עצירה (הנתונים נשמרים ב-volumes)
docker compose down -v                          # עצירה ומחיקת ה-DB וקובצי ה-PDF
```

- ה-frontend (nginx) מעביר את `/api` ל-backend ברשת הפנימית. ה-backend לא חשוף על פורט במחשב.
- ה-DB נמצא ב-volume ‏`qq-data`, וקובצי ה-PDF ב-volume ‏`qq-storage`.
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

**PDF מקומית:** WeasyPrint צריך את Pango ו-HarfBuzz, שאינן מותקנות כברירת מחדל ב-Windows. בלעדיהן:
- `POST /api/quotes` מחזיר `503 pdf_unavailable`.
- בדיקות ה-PDF וה-PNG מדולגות עם הסבר.

כל השאר רץ מקומית, כולל ה-Snapshot של ה-HTML ובדיקות האבטחה. ליצירת PDF השתמשו ב-Docker.

ב-Windows עם Python 3.15, `uvicorn --reload` לפעמים לא טוען מחדש בפועל וממשיך להריץ קוד ישן. אם שינוי לא נקלט, הפעילו את השרת מחדש.

## בדיקות

```bash
cd backend  && pytest && ruff check . && ruff format --check .
cd frontend && npm test && npm run lint && npm run build
```

| תיקייה | מה נבדק |
|--------|---------|
| `tests/unit` | מנוע הפרמיה (כל סף משני הצדדים, מינימום, עיגול ‎.5), מספור, אחסון, רינדור HTML |
| `tests/integration` | ה-API, יצירת הצעה וביטול טרנזקציה בכישלון, **20 בקשות מקבילות בלי מספרים כפולים** |
| `tests/security` | Path Traversal בהורדה, תוקף (`410`), הזרקה לתבנית, חסימת משאבים חיצוניים ב-PDF |
| `tests/pdf` | PDF אמיתי: גופנים מוטמעים בלבד, טקסט עברי, מספר הצעה, עמוד A4 (רק ב-Docker) |
| `tests/snapshot` | HTML מרונדר לכל מוצר (בכל מקום), ועמוד 1 של ה-PDF כ-PNG (רק ב-Docker) |

### בדיקות Snapshot

- **ה-HTML** (ה-snapshot הראשי) מושווה בדיוק. **ה-PNG** (המשני) מושווה ב-RGB: מותר שעד 0.5% מהפיקסלים ישתנו ביותר מ-32 רמות בערוץ כלשהו.
- השעון, ה-UUID והטוקן קבועים, כך שהפלט דטרמיניסטי.
- ה-image של Docker נעול לגרסה `python:3.12.16-slim-trixie`, כדי שה-PNG ייראה זהה בכל מחשב וב-CI.

**עדכון snapshot רק כשהשינוי בעיצוב מכוון**, ותמיד עם הסבר בהודעת ה-commit. אסור לעדכן snapshot רק כדי שבדיקה תעבור.

```bash
cd backend && pytest tests/snapshot --snapshot-update          # HTML
docker compose run --rm \
  -v "$PWD/backend/tests/snapshot/__snapshots__:/app/tests/snapshot/__snapshots__" \
  backend pytest tests/snapshot --snapshot-update            # PNG (רק ב-Docker)
```

כשבדיקה נכשלת, הפלט בפועל ותמונת ה-diff נשמרים ב-`backend/tests/snapshot/.failures/`. ב-CI הם מועלים כ-artifact.

## CI

הקובץ `.github/workflows/ci.yml` רץ על כל push ו-pull request:
- **backend:** ruff ו-pytest.
- **frontend:** lint, בדיקות ו-build.
- **docker:**
  1. בונה את שני ה-images.
  2. מריץ את כל הבדיקות בתוך ה-image, ונכשל אם בדיקה כלשהי דולגה.
  3. smoke test דרך nginx: יצירת הצעה, הורדה (כולל בדיקת הכותרות), הורדה חוזרת, וטוקנים זדוניים שחייבים להחזיר 404.

## הגדרות

| משתנה | ברירת מחדל | שימוש |
|-------|------------|-------|
| `DATABASE_URL` | `sqlite:///./data/quickquote.db` | ה-DB (ב-Docker: `sqlite:////data/quickquote.db`) |
| `STORAGE_DIR` | `./storage` | תיקיית קובצי ה-PDF (ב-Docker: `/storage`) |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | המקור היחיד שמותר ב-CORS (ב-Docker: `http://localhost:8080`) |
| `VITE_API_PROXY_TARGET` | `http://localhost:8000` | יעד ה-proxy של `/api` ב-`npm run dev` |
| `VITE_API_BASE` | ריק | כתובת בסיס ל-API כשאין proxy |
| `SNAPSHOT_FAILURES_DIR` | `tests/snapshot/.failures` | לאן נכתב הפלט כשבדיקת snapshot נכשלת |

## גופנים

`backend/app/fonts/` מכיל את Noto Sans Hebrew ואת Noto Sans (לטיני). Noto Sans נדרש לספרות ולאנגלית, שאינן קיימות בגופן העברי. שני הגופנים ברישיון SIL OFL 1.1 (ראו `OFL.txt`).
