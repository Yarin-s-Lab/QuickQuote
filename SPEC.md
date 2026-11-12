# SPEC — מחולל הצעות מחיר PDF

> מסמך האפיון של הפרויקט. כל החלטה שאינה מופיעה כאן נחשבת פתוחה ויש לשאול לפני מימוש.

## 1. מטרה

סוכן ביטוח ממלא טופס קצר ומקבל הצעת מחיר מעוצבת בעברית, כקובץ PDF מוכן לשליחה ללקוח.
המשך טבעי של ההדגמה החיה.

- **משתמשים:** סוכן
- **מתאים ל:** מפתחים
- **גודל:** קטן · רמות 1–3

## 2. ארכיטקטורה

הפרויקט מופרד לשני שירותים עצמאיים שמתקשרים רק דרך REST API:

| רכיב | טכנולוגיה | אחריות |
|------|-----------|--------|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy, Jinja2, WeasyPrint | חישוב פרמיה, מספור, שמירה, יצירת PDF, הורדה מאובטחת |
| `frontend/` | React 18, TypeScript, Vite, zod | טופס RTL, תצוגה מקדימה של הפרמיה, הצגת קישור הורדה |
| DB | SQLite (קובץ על volume) | שמירת הצעות ומונה מספור |
| אחסון קבצים | תיקייה מקומית `storage/` על volume | קובצי PDF שנוצרו |

עקרונות:
- ה-backend הוא מקור האמת היחיד לחישוב הפרמיה. ה-frontend מציג תצוגה מקדימה בלבד שמגיעה מה-API.
- ה-frontend לא ניגש לקבצים או ל-DB ישירות.
- כל שירות עם Dockerfile משלו; `docker-compose.yml` מרים את שניהם.

## 3. ישויות

### סוכן (Agent)
- `name` — שם הסוכן (טקסט חופשי, נדרש). אין הזדהות בגרסה זו.

### לקוח דמה (Client)
- `full_name` (נדרש), `phone`, `email` (אופציונליים, עם ולידציה בסיסית).
- לא נאספים מספרי זהות או פרטים פיננסיים.

### מוצר (Product)
שני מוצרים בלבד: `car` (רכב), `apartment` (דירה). לכל מוצר שדות קלט וכיסויים משלו.

### כיסוי (Coverage)
- `code`, `label_he`, `price_rule` — ראו סעיף 4.

### הצעה (Quote)
| שדה | תיאור |
|-----|-------|
| `id` | מזהה פנימי (UUID) |
| `quote_number` | מספר הצעה ייחודי, פורמט `Q-YYYY-NNNNNN` |
| `product` | `car` / `apartment` |
| `agent_name`, `client_*` | פרטי הסוכן והלקוח |
| `inputs` | שדות המוצר (JSON) |
| `coverages` | רשימת קודי כיסויים |
| `premium` | פרמיה שנתית בש"ח, `Decimal`, מעוגלת לשקל שלם |
| `breakdown` | פירוט החישוב (JSON) — מוצג ב-PDF |
| `issued_at` | מועד הנפקה |
| `valid_until` | `issued_at` + 30 ימים |
| `download_token` | טוקן אקראי לא ניתן לניחוש (`secrets.token_urlsafe(32)`) |
| `pdf_filename` | שם קובץ שנבנה בשרת בלבד: `{id}.pdf` |

## 4. נוסחת פרמיה (דמה)

כל החישובים ב-`Decimal`. עיגול סופי לשקל שלם (`ROUND_HALF_UP`). פרמיה מינימלית: **500 ₪**.

### רכב (`car`)
קלט: `driver_age` (17–90), `license_years` (0–70), `car_value` (10,000–1,000,000), `claims_last_3_years` (0–5), `coverage_type` (`comprehensive` / `third_party`).

```
base = 1,500 אם comprehensive, 900 אם third_party
value_part = car_value × 2%   (רק ב-comprehensive)
age_factor = 1.5 אם גיל < 24, 1.2 אם 24–29, 1.0 אחרת
license_factor = 1.3 אם ותק < 2, 1.0 אחרת
claims_factor = 1 + 0.15 × claims
premium = (base + value_part) × age_factor × license_factor × claims_factor + תוספות
```
תוספות: גרירה `towing` +150 · שמשות `glass` +200 · רכב חלופי `replacement_car` +250.

### דירה (`apartment`)
קלט: `structure_value` (0–5,000,000), `contents_value` (0–2,000,000), `floor` (0–60), `has_alarm` (bool). לפחות אחד מהערכים חייב להיות גדול מ-0.

```
structure_part = structure_value × 0.1%
contents_part = contents_value × 0.3%
floor_factor = 1.1 אם קומת קרקע (0), 1.0 אחרת
alarm_factor = 0.9 אם יש אזעקה, 1.0 אחרת
premium = (structure_part + contents_part) × floor_factor × alarm_factor + תוספות
```
תוספות: רעידת אדמה `earthquake` = structure_value × 0.05% · צנרת `plumbing` +120 · תכשיטים `jewelry` +300.

### בדיקות חובה למנוע
- ערך לכל פקטור בכל צד של סף (23/24, 29/30, 1/2 שנות ותק).
- פרמיה מינימלית נאכפת.
- עיגול: מקרה של ‎.5 בדיוק.
- קלט מחוץ לטווח נדחה עם שגיאת ולידציה.
- `breakdown` סוכם בדיוק ל-`premium` לפני עיגול.

## 5. API

בסיס: `/api`. כל הגופים ב-JSON, שגיאות בפורמט `{"error": {"code": "...", "message_he": "..."}}`.

| שיטה | נתיב | תיאור |
|------|------|-------|
| GET | `/products` | רשימת מוצרים, שדות וכיסויים (לבניית הטופס) |
| POST | `/quotes/preview` | חישוב פרמיה ו-breakdown בלי שמירה |
| POST | `/quotes` | יצירת הצעה: חישוב, מספור, שמירה, יצירת PDF. מחזיר `quote_number`, `premium`, `valid_until`, `download_url` |
| GET | `/quotes/{quote_number}` | מטא-דאטה של הצעה (ללא הטוקן) |
| GET | `/quotes/download/{token}` | הורדת ה-PDF |
| GET | `/health` | בדיקת חיות |

קודי תגובה להורדה: `200` קובץ · `404` טוקן לא קיים · `410` ההצעה פגה. כותרות: `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="{quote_number}.pdf"`.

### `POST /quotes/preview` (רמה 1)
גוף: `{"product": "car" | "apartment", "inputs": {...}, "coverages": ["towing", ...]}` — בלי פרטי סוכן/לקוח (אלה נשלחים ב-`POST /quotes`).
שדות שלמים (גיל, ותק, שווי וכו') הם מספרים שלמים ב-JSON; מחרוזת או שבר נדחים. כיסוי לא מוכר או כפול נדחה.

תגובה:
```json
{
  "product": "car", "currency": "ILS",
  "premium": "6975", "premium_before_rounding": "6975.000000", "minimum_applied": false,
  "breakdown": [{"code": "base", "label_he": "...", "amount": "1500"}, ...],
  "factors": [{"code": "age_factor", "label_he": "...", "value": "1.5"}, ...]
}
```
- סכומים כמחרוזות `Decimal` (לא float).
- `breakdown` הוא שורות חיבוריות שסכומן בדיוק `premium_before_rounding`: בסיס/רכיבי שווי · `factors_adjustment` (השפעת כל הפקטורים יחד) · שורה לכל תוספת · `minimum_adjustment` אם הסכום נמוך מ-500.
- `factors` למידע בלבד (השפעתם כבר בשורת `factors_adjustment`).
- הפרמיה המינימלית נאכפת על הסכום הכולל כולל תוספות, לפני העיגול.
- שגיאת ולידציה: `422` עם `{"error": {"code": "validation_error", "message_he": "גיל הנהג: הערך חייב להיות לפחות 17"}}`.

### `GET /products`
`{"min_premium": "500", "products": [{"code", "label_he", "fields": [{"name", "label_he", "type": "integer|money|boolean|enum", "required", "min", "max", "options"}], "coverages": [{"code", "label_he", "price_rule_he"}]}]}` — הטווחים נגזרים ממודלי הקלט ב-backend (מקור אמת יחיד).

## 6. PDF

- תבנית HTML אחת (`backend/app/templates/quote.html`) + CSS, מומרת ל-PDF עם WeasyPrint.
- `<html lang="he" dir="rtl">`, גופן עברי מוטמע (Noto Sans Hebrew, מתוך `backend/app/fonts/`, נטען ב-`@font-face`).
- תוכן: לוגו/כותרת דמה · מספר הצעה · תאריך הנפקה ותוקף · פרטי סוכן ולקוח · מוצר וכיסויים · טבלת פירוט חישוב · פרמיה סופית · הערת "הצעה לדוגמה — לא מחייבת".
- מספרים וסכומים בפורמט `1,234 ₪`, תאריכים `DD/MM/YYYY`.
- מספרים ואנגלית בתוך טקסט עברי עטופים ב-`<bdi>` כדי למנוע היפוך.

## 7. אבטחה (מוקד)

### Path Traversal בהורדת קבצים
- ההורדה מתבצעת לפי `download_token` בלבד, לא לפי שם קובץ או נתיב.
- הנתיב נבנה בשרת מה-`id` הפנימי; אחרי `resolve()` מוודאים שהוא תחת `STORAGE_DIR`, אחרת `404`.
- שום שדה מהטופס לא משתתף בבניית נתיב או שם קובץ.
- בדיקות: טוקנים כמו `../../etc/passwd`, `..%2F..%2F`, נתיב מוחלט, null byte — כולם מחזירים `404`.

### הזרקה לתבנית דרך שדות הטופס
- Jinja2 עם `autoescape=True`; אסור `|safe` על קלט משתמש.
- קלט משתמש מועבר לתבנית רק כמשתנים, לעולם לא כחלק מטקסט התבנית (`from_string` אסור).
- WeasyPrint עם `url_fetcher` שחוסם כל URL חיצוני ו-`file://` מחוץ לתיקיית התבנית.
- בדיקות: `{{7*7}}`, `<script>`, `<img src="file:///etc/passwd">`, `<link href="http://...">` — מופיעים ב-PDF כטקסט מילולי ולא מבוצעים.

### כללי
- ולידציה עם Pydantic על כל קלט, אורך מקסימלי לכל שדה טקסט (100 תווים).
- CORS מוגבל לכתובת ה-frontend.

## 8. רמות עבודה

| רמה | מה בונים | מוכן כש |
|-----|----------|---------|
| 1 | SPEC.md; מנוע חישוב פרמיה עם בדיקות; endpoint ‏`preview`; טופס בסיסי | טופס עם שני מוצרים ונוסחת פרמיה דמה שמכוסה בבדיקות |
| 2 | תבנית HTML שהופכת ל-PDF; שמירה במסד; Docker עם פונטים עבריים | PDF בעברית תקינה (RTL ופונט עברי) עם מספר הצעה ותוקף; ה-PDF נוצר תקין גם בתוך ה-Container |
| 3 | מספור הצעות; הורדה מאובטחת; בדיקת Snapshot; CI ירוק | הצעות נשמרות וניתנות להורדה חוזרת בקישור בעל תוקף; CI ירוק עם בדיקת Snapshot; README |

### מספור הצעות (רמה 3)
- פורמט `Q-YYYY-NNNNNN`, רץ ומתאפס בכל שנה.
- מונה בטבלה `quote_counters(year, last_value)` שמתעדכן בתוך טרנזקציה עם יצירת ההצעה — אין כפילויות גם בבקשות מקבילות (בדיקה עם בקשות מקבילות).

### בדיקת Snapshot (רמה 3)
- שעון מוקפא ו-UUID/טוקן קבועים בבדיקה כדי לקבל פלט דטרמיניסטי.
- Snapshot ראשי: ה-HTML המרונדר לכל מוצר.
- Snapshot משני: עמוד 1 של ה-PDF כ-PNG, השוואה עם סף סטייה קטן. רץ רק בתוך Docker (פונטים זהים).
- עדכון snapshot רק בכוונה, עם הסבר ב-commit.

### CI (רמה 3)
GitHub Actions: lint + בדיקות backend, lint + build + בדיקות frontend, build של שני ה-images והרצת בדיקת ה-Snapshot בתוך ה-image של ה-backend.

## 9. מחוץ להיקף

חתימה דיגיטלית · שליחה ללקוח · תמחור אמיתי · עורך תבניות · הזדהות סוכנים.

## 10. בונוס למהירים

- תבנית נפרדת לכל מוצר.
- השוואת שתי הצעות במסמך אחד.
- שליחה במייל מדומה (כתיבה ל-log / MailHog, בלי שליחה אמיתית).

## 11. שאלות פתוחות

- האם נדרשת הזדהות סוכנים בהמשך?
- האם יש מיתוג (לוגו, צבעים) ל-PDF או שמשתמשים בעיצוב דמה?