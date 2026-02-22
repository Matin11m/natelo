# Technical Documentation — `stock_no_negative` (v19)

## 1) Executive summary

این ماژول در نسخه 19، علاوه بر رفتار کلاسیک «جلوگیری از موجودی منفی»، یک لایه کنترلی جدید برای **اعتبارسنجی تاریخی موجودی** و یک قابلیت **تاریخ موثر (Effective Date)** روی Picking اضافه کرده است.

در نتیجه، معماری کنترل موجودی اکنون دو مرحله‌ای است:

1. **کنترل لحظه‌ای سطح Quant** (constraint روی `stock.quant`) برای جلوگیری از منفی شدن جاری.
2. **کنترل تاریخی سطح Move** (بازپخش زمانی حرکت‌ها) برای جلوگیری از منفی شدن در گذشته، به‌خصوص در سناریوهای back-date.

---

## 2) دامنه ماژول و وابستگی‌ها

- نام ماژول: `stock_no_negative`
- وابستگی اصلی: `stock`
- نسخه: `19.0.1.0.0`

### فایل‌های کلیدی

- `models/stock_quant.py` → کنترل کلاسیک سطح کوانت.
- `models/stock_move.py` → هوک `_action_done` + کنترل تاریخی + همگام‌سازی تاریخ/لوکیشن.
- `models/stock_picking.py` → افزودن فیلد `effective_date_time`.
- `models/product.py` و `models/stock_location.py` → تنظیمات استثنا (`allow_negative_stock`).
- `views/*.xml` → نمایش فیلدها در UI.

---

## 3) مدل داده و تنظیمات

## 3.1) پرچم‌های کسب‌وکاری

### Product Template / Product Category
- `allow_negative_stock` روی محصول و دسته‌بندی.
- منطق: اگر هر دو False باشند، محصول از نظر «ممنوعیت موجودی منفی» در حالت سخت‌گیرانه است.

### Stock Location
- `allow_negative_stock` روی لوکیشن.
- فقط برای لوکیشن‌های `internal` و `transit` در UI معنی‌دار نمایش داده می‌شود.

## 3.2) فیلد تاریخ موثر

### Stock Picking
- `effective_date_time` (Datetime)
- نقش: در زمان Validate، اگر مقدار داشته باشد به‌عنوان تاریخ موثر روی Picking/Move/MoveLine اعمال می‌شود.
- سازگاری عقب‌رو: اگر فیلد استودیویی `x_studio_effective_date_time` وجود داشته باشد و `effective_date_time` خالی باشد، از آن استفاده می‌شود.

---

## 4) جریان اجرای اصلی (Runtime Flow)

نقطه ورود اصلی در زمان انجام حرکت‌ها، override متد زیر است:

- `stock.move._action_done()`

ترتیب اجرا:

1. استخراج تاریخ موثر به تفکیک Picking (`_get_effective_date_by_picking`).
2. همگام‌سازی لوکیشن move و move line با مقادیر Picking (`_sync_locations_from_picking`).
3. اجرای کنترل تاریخی منفی‌شدن موجودی (`_check_negative_stock_history_on_done_candidates`).
4. اجرای منطق اصلی Odoo با `super()`.
5. اعمال مجدد تاریخ موثر پس از done (`_apply_effective_dates_after_done`) برای جلوگیری از overwrite داخلی Odoo.

این ترتیب، هم **Consistency داده‌ها قبل از Validate** و هم **پایداری تاریخ موثر بعد از Validate** را پوشش می‌دهد.

---

## 5) کنترل سطح Quant (Constraint کلاسیک)

پیاده‌سازی در `stock_quant.check_negative_qty`:

- Trigger: constraint روی `product_id` و `quantity`.
- Skip context:
  - `skip_negative_qty_check` → غیرفعال کردن کنترل در شرایط خاص.
  - در حالت تست Odoo، فقط با context `test_stock_no_negative` فعال می‌شود.
- شرایط خطا:
  - `quantity < 0`
  - محصول `is_storable`
  - usage لوکیشن در `internal` یا `transit`
  - اجازه منفی روی محصول/دسته/لوکیشن فعال نباشد.
- خروجی: `ValidationError` با پیام دقیق شامل محصول، لوکیشن، مقدار، و lot (در صورت وجود).

نکته: این کنترل وضعیت «همین لحظه» را می‌بیند، نه لزوماً سیر تاریخی حرکت‌ها.

---

## 6) کنترل تاریخی سطح Move (قابلیت جدید)

پیاده‌سازی در `_check_negative_stock_history_on_done_candidates`:

### ایده

برای moveهایی که قرار است done شوند، سیستم یک بازپخش زمانی انجام می‌دهد:

- داده‌های done قبلی (از دیتابیس)
- به‌علاوه moveهای کاندید فعلی
- مرتب‌شده بر اساس `(effective_date یا date, id)`

و سپس برای هر `(product, location)` یک بالانس تجمعی نگه می‌دارد.

### قوانین مهم

- فقط برای محصولات storable.
- اگر روی محصول یا دسته، اجازه منفی فعال باشد، آن محصول از کنترل تاریخی رد می‌شود.
- لوکیشن‌های با usage زیر از کنترل کنار گذاشته می‌شوند:
  - `supplier`, `view`, `customer`, `production`
- لوکیشن‌هایی که `allow_negative_stock=True` دارند، در scope کنترل تاریخی وارد نمی‌شوند.
- tolerance عددی با `balance_floor = -1e-7` برای نویز ممیز شناور.

### خطا

در صورت عبور بالانس از کف مجاز، `UserError` با پیام فارسی شامل:
- کالا
- انبار
- تاریخ
- مقدار حرکت
- موجودی جدید

### ارزش کسب‌وکاری

این لایه، خلأ سناریوهای back-date را که ممکن است از کنترل صرفاً quant عبور کنند، پوشش می‌دهد.

---

## 7) همگام‌سازی لوکیشن و تاریخ

## 7.1) Sync لوکیشن از Picking

قبل از done شدن، لوکیشن مبدأ/مقصد move و move line با Picking همسان‌سازی می‌شود. این موضوع برای جلوگیری از ناهماهنگی بین فرم Picking و خطوط موثر است.

## 7.2) Sync تاریخ موثر

بعد از done:

- `picking.date_done = effective_date`
- `picking.effective_date_time = effective_date`
- `stock.move.date = effective_date`
- `stock.move.line.date = effective_date`

این re-apply برای مقابله با رفتار پیش‌فرض Odoo (overwrite تاریخ در فرآیند done) انجام می‌شود.

---

## 8) UI و تجربه کاربری

- فرم Product Template: فیلد `allow_negative_stock` کنار دسته‌بندی.
- فرم Product Category: فیلد `allow_negative_stock`.
- فرم Stock Location: فیلد `allow_negative_stock` (برای internal/transit).
- فرم Stock Picking: فیلد `effective_date_time` بعد از `scheduled_date`.

---

## 9) پوشش تست فعلی و شکاف‌ها

### تست‌های موجود

فایل `tests/test_stock_no_negative.py` موارد زیر را پوشش می‌دهد:

- جلوگیری از منفی شدن پیش‌فرض.
- سناریوی محصول lot-tracked.
- استثنا در سطح محصول.
- استثنا در سطح لوکیشن.

### شکاف‌های مهم

در تست فعلی، برای توسعه نسخه 19 هنوز تست خودکار مجزا برای این موارد دیده نمی‌شود:

1. اعتبارسنجی تاریخی back-date.
2. اعمال `effective_date_time` روی move/move-line/date_done.
3. fallback به `x_studio_effective_date_time`.
4. صحت sync لوکیشن move/move-line از Picking در حالات edge.

پیشنهاد: افزودن کلاس تست جدید برای منطق `stock_move.py`.

---

## 10) ریسک‌ها و نکات عملکردی

- کنترل تاریخی به ازای هر محصول، query روی done moves انجام می‌دهد. روی دیتاست‌های بزرگ باید عملکرد بررسی شود.
- چون ترتیب replay بر اساس تاریخ و id است، هر نوع دست‌کاری تاریخ بدون سیاست مشخص می‌تواند رفتار Validate را تغییر دهد.
- پیام خطا در لایه تاریخی فارسی است؛ اگر محیط چندزبانه باشد، ممکن است نیاز به i18n اضافه باشد.

---

## 11) توصیه‌های اجرایی برای Production

1. قبل از roll-out، داده‌های واقعی (حداقل 1 ماه) در staging replay شود.
2. سیاست `allow_negative_stock` برای محصولات/لوکیشن‌های استثنایی به‌صورت کنترل‌شده تعریف شود.
3. برای تیم عملیات، آموزش تفاوت «خطای لحظه‌ای quant» و «خطای تاریخی move» ارائه شود.
4. در مانیتورینگ، نرخ خطاهای `UserError` مربوط به historical check ثبت و تحلیل شود.

---

## 12) نتیجه‌گیری

پیاده‌سازی نسخه 19 از حالت «جلوگیری ساده از موجودی منفی» به یک کنترل ترکیبی و دقیق‌تر ارتقا پیدا کرده است. با افزودن تست‌های خودکار برای مسیرهای تاریخی/تاریخ موثر، این ماژول می‌تواند برای سناریوهای واقعی با back-date نیز قابل اتکا و پایدار باشد.
