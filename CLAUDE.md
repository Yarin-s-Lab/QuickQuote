# CLAUDE.md

מחולל הצעות מחיר PDF: סוכן ממלא טופס ומקבל הצעת מחיר בעברית מוכנה לשליחה.
**האפיון המלא נמצא ב-`SPEC.md` — קראי אותו לפני כל משימה.** אם משהו לא מופיע שם, שאלי לפני שממשים.

## מבנה

```
backend/            FastAPI, Python 3.12
  app/
    api/            routes בלבד, בלי לוגיקה עסקית
    domain/pricing/ מנוע הפרמיה (car.py, apartment.py) — פונקציות טהורות
    services/       quote_service, numbering, pdf_renderer, storage
    db/             מודלים ו-session (SQLAlchemy)
    templates/      quote.html, quote.css
    fonts/          Noto Sans Hebrew
  tests/            unit/, integration/, security/, snapshot/
frontend/           React + TypeScript + Vite
  src/
    api/            client ל-API (fetch + טיפוסים)
    components/     רכיבי טופס
    pages/
docker-compose.yml
.github/workflows/ci.yml
```

## פקודות

```bash
# backend
cd backend && pip install -e ".[dev]"
uvicorn app.main:app --reload          # http://localhost:8000
pytest                                  # כל הבדיקות
pytest tests/unit/test_pricing_car.py   # קובץ בודד
ruff check . && ruff format --check .

# frontend
cd frontend && npm ci
npm run dev                             # http://localhost:5173
npm test && npm run lint && npm run build

# הכל ביחד
docker compose up --build
docker compose run --rm backend pytest tests/snapshot
```

## כללים

### הפרדת backend / frontend
- ה-frontend מדבר עם ה-backend רק דרך `/api`. אין קוד משותף ביניהם.
- חישוב הפרמיה קיים **רק** ב-backend. ה-frontend מציג את מה שחוזר מ-`/api/quotes/preview`.
- שינוי בחוזה ה-API מחייב עדכון של `SPEC.md` סעיף 5 ושל הטיפוסים ב-`frontend/src/api/`.

### כסף ומספרים
- תמיד `Decimal`, לעולם לא `float`. עיגול רק בסוף, `ROUND_HALF_UP`.
- כל שינוי במנוע הפרמיה מגיע עם בדיקות לכל סף שהשתנה.

### אבטחה — לא לעקוף
- הורדת קובץ רק לפי `download_token`. אסור לבנות נתיב מקלט משתמש.
- כל נתיב קובץ עובר `resolve()` ובדיקה שהוא תחת `STORAGE_DIR`.
- Jinja2 עם `autoescape=True`. אסור `|safe` על קלט משתמש, אסור `Environment.from_string` עם קלט.
- WeasyPrint רק עם ה-`url_fetcher` המגביל שב-`pdf_renderer.py`.
- שינוי בקוד ההורדה או הרינדור → להריץ `pytest tests/security`.

### עברית ו-RTL
- `lang="he" dir="rtl"` ב-HTML של ה-PDF וב-`index.html` של ה-frontend.
- מספרים, מספרי הצעה וטקסט באנגלית בתוך משפט עברי → `<bdi>`.
- טקסטים למשתמש בעברית; שמות משתנים, קוד ו-commits באנגלית.
- הגופן נטען מ-`backend/app/fonts/` — לא מ-CDN (ה-PDF חייב להיווצר גם בלי רשת).

### בדיקות Snapshot
- לא לעדכן snapshot כדי "להעביר" בדיקה. עדכון רק כששינוי העיצוב מכוון, ולציין זאת בהודעת ה-commit.
- snapshot של PNG רץ רק בתוך Docker.

## סדר עבודה

עובדים לפי הרמות ב-`SPEC.md` סעיף 8, רמה אחרי רמה. בסוף כל רמה: כל הבדיקות ירוקות ו-checklist "מוכן כש" מתקיים.

לפני שמסיימים משימה:
1. `pytest` ו-`npm test` עוברים.
2. lint נקי בשני הצדדים.
3. אם נגעת ב-PDF — יצרת PDF לדוגמה ובדקת שהעברית תקינה.
4. `SPEC.md` / README מעודכנים אם התנהגות השתנתה.

## לא בהיקף — לא לממש

חתימה דיגיטלית, שליחה ללקוח, תמחור אמיתי, עורך תבניות, הזדהות סוכנים.
פיצ'רי בונוס (SPEC סעיף 10) רק אחרי שרמה 3 הושלמה ורק אם התבקש.
