# Workflow Test Documentation — `stock_no_negative` (v19)

این سند، برنامه‌ی تست کامل ورک‌فلوهای ماژول را پوشش می‌دهد؛ شامل تست‌های دستی (UAT)، تست‌های فنی، و چک‌های رگرسیون.

## 1) هدف و دامنه

هدف تست‌ها:

1. اطمینان از جلوگیری صحیح موجودی منفی در حالت پیش‌فرض.
2. اطمینان از اعمال صحیح استثناها (محصول/دسته/لوکیشن).
3. اعتبارسنجی همگام‌سازی تاریخ موثر و لوکیشن‌ها.
4. اعتبارسنجی کنترل تاریخی موجودی (back-date consistency).

دامنه فرآیندها:

- Delivery
- Internal Transfer
- Receipt
- سناریوهای ترکیبی تاریخ‌دار (back-dated)
- محصولات lot-tracked

---

## 2) پیش‌نیاز محیط تست

- Odoo 19 با ماژول `stock_no_negative` نصب/آپدیت شده.
- یک دیتابیس تمیز برای تست خودکار + یک دیتابیس staging برای UAT.
- فعال بودن اپ Inventory.
- دسترسی کاربر تست به عملیات انبار و تنظیمات.

### داده پایه پیشنهادی

- محصول `P-STORABLE` (Storable)
- محصول `P-LOT` (Storable + Tracking by Lots)
- دسته `CAT-STRICT` (allow_negative_stock=False)
- لوکیشن داخلی `WH/Stock` (allow_negative_stock=False)
- لوکیشن داخلی `WH/Overflow` (allow_negative_stock=True برای سناریو استثنا)
- یک مشتری تست و یک تامین‌کننده تست

---

## 3) ماتریس تست ورک‌فلوها

## WF-01 — Delivery با موجودی ناکافی (حالت پیش‌فرض)

**هدف:** باید خطای جلوگیری از موجودی منفی دریافت شود.

مراحل:
1. موجودی `P-STORABLE` در `WH/Stock` را صفر نگه دارید.
2. یک Delivery با مقدار 10 ثبت کنید.
3. Validate کنید.

انتظار:
- عملیات Fail شود.
- خطای `ValidationError` از لایه quant نمایش داده شود.

---

## WF-02 — Delivery با استثنا روی محصول

**هدف:** فعال‌سازی `allow_negative_stock` روی محصول باید مجوز خروج منفی بدهد.

مراحل:
1. `P-STORABLE.allow_negative_stock=True`.
2. دوباره Delivery با مقدار 10 روی موجودی صفر Validate شود.

انتظار:
- عملیات Pass.
- Quant منفی ثبت شود.

---

## WF-03 — Delivery با استثنا روی دسته‌بندی

**هدف:** استثنای دسته‌بندی باید رفتار محصولات آن دسته را تغییر دهد.

مراحل:
1. `P-STORABLE.allow_negative_stock=False`.
2. `CAT-STRICT.allow_negative_stock=True`.
3. Delivery منفی را Validate کنید.

انتظار:
- عملیات Pass.

---

## WF-04 — Delivery با استثنا روی لوکیشن

**هدف:** استثنای لوکیشن داخلی باید مجوز موجودی منفی بدهد.

مراحل:
1. محصول و دسته strict باشند.
2. سورس Delivery را روی `WH/Overflow` با `allow_negative_stock=True` قرار دهید.
3. Validate.

انتظار:
- عملیات Pass.

---

## WF-05 — محصول Lot-tracked

**هدف:** رفتار ماژول با lot tracking صحیح باشد.

مراحل:
1. Delivery برای `P-LOT` بسازید.
2. قبل از Validate، move line با lot معتبر ثبت کنید.
3. با تنظیم strict Validate کنید.

انتظار:
- در strict mode خطا دهد.
- با فعال‌سازی استثنا (محصول/دسته/لوکیشن) Pass شود.

---

## WF-06 — Effective Date Sync

**هدف:** `effective_date_time` روی Picking به Move/MoveLine/date_done اعمال شود.

مراحل:
1. Picking بسازید.
2. `effective_date_time` را روی یک تاریخ گذشته بگذارید.
3. عملیات را Validate کنید.
4. مقادیر `picking.date_done`، `move.date` و `move_line.date` را بررسی کنید.

انتظار:
- هر سه مقدار برابر تاریخ موثر باشند.

---

## WF-07 — Fallback به `x_studio_effective_date_time`

**هدف:** اگر فیلد سفارشی استودیو وجود دارد و فیلد اصلی خالی است، fallback عمل کند.

مراحل:
1. در محیطی که فیلد `x_studio_effective_date_time` موجود است، روی Picking مقدار دهید.
2. `effective_date_time` را خالی بگذارید.
3. Validate و تاریخ‌های نهایی را بررسی کنید.

انتظار:
- تاریخ‌ها از فیلد Studio خوانده شوند.

---

## WF-08 — Back-dated historical check

**هدف:** جلوگیری از منفی شدن تاریخی حتی اگر موجودی نهایی منفی نباشد.

سناریو نمونه:
1. Receipt +100 با تاریخ `2026-01-10`.
2. Delivery -20 با تاریخ `2026-01-05`.
3. تلاش برای Validate Delivery.

انتظار:
- `UserError` از لایه historical check دریافت شود.

---

## WF-09 — Internal Transfer

**هدف:** انتقال بین لوکیشن‌های داخلی باید با همان قوانین منفی کنترل شود.

مراحل:
1. انتقال `WH/Stock -> WH/Overflow` را با موجودی ناکافی بسازید.
2. Validate.

انتظار:
- اگر `WH/Stock` strict باشد، بلاک شود.
- اگر لوکیشن/محصول استثنا داشته باشد، Pass شود.

---

## WF-10 — Location Usage Exclusions

**هدف:** usageهای مستثنی (`supplier/view/customer/production`) وارد historical scope نشوند.

مراحل:
1. سناریوهایی بسازید که فقط این usageها درگیر باشند.
2. Validate کنید.

انتظار:
- historical check روی این usageها دخالت مستقیم نداشته باشد.

---

## 4) تست‌های خودکار فعلی

تست‌های فعلی در `tests/test_stock_no_negative.py`:

- `test_check_constrains`
- `test_check_constrains_with_lot`
- `test_true_allow_negative_stock_product`
- `test_true_allow_negative_stock_location`
- `test_true_allow_negative_stock_product_with_lot`

این‌ها هسته رفتار کلاسیک را پوشش می‌دهند.

---

## 5) پیشنهاد تست خودکار تکمیلی (برای نسخه 19)

پیشنهاد افزودن تست‌های جدید:

1. `test_effective_date_time_is_applied_to_done_records`
2. `test_fallback_to_x_studio_effective_date_time`
3. `test_historical_check_blocks_backdated_negative`
4. `test_move_and_move_line_locations_synced_from_picking`

---

## 6) فرمان‌های اجرای تست

```bash
odoo -d <test_db> -i stock_no_negative --test-enable --stop-after-init
```

یا برای آپدیت ماژول:

```bash
odoo -d <test_db> -u stock_no_negative --test-enable --stop-after-init
```

---

## 7) چک‌لیست پذیرش نهایی (UAT Sign-off)

- [ ] WF-01 تا WF-05 پاس شدند.
- [ ] Effective date sync تایید شد.
- [ ] Historical check در سناریوی back-date خطای درست داد.
- [ ] پیام‌های خطا برای کاربر عملیاتی قابل فهم هستند.
- [ ] موارد استثنا (محصول/دسته/لوکیشن) طبق سیاست سازمان تایید شدند.

---

## 8) خروجی مورد انتظار از تیم QA

برای هر WF حداقل این موارد ثبت شود:

- شناسه سناریو (WF-xx)
- نتیجه (Pass/Fail)
- شماره سند (Picking/Move)
- اسکرین‌شات خطا یا تایید Validate
- توضیح انحراف احتمالی

این خروجی، هم برای تایید داخلی و هم برای تحلیل رگرسیون نسخه‌های بعدی کافی خواهد بود.
