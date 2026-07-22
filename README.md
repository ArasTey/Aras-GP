<div align="center">

<img src="panel/static/brand/aras-mark.svg" width="88" height="88" alt="Aras-GP">

# Aras-GP

### پنل مدیریت وب برای عبور از فیلترینگ با Domain Fronting

پنلی فارسی، راست‌چین و کاملاً آفلاین برای پیکربندی، دیپلوی، اجرا و پایش
یک رله‌ی Domain Fronting روی Google Apps Script و Cloudflare Workers.

</div>

---

## معرفی

**Aras-GP** یک پنل مدیریت تحت وب است که کل چرخه‌ی راه‌اندازی یک رله‌ی عبور از
فیلترینگ را از خط فرمان به یک رابط گرافیکی می‌آورد: از ساخت کانفیگ و کلید
احراز هویت، تا دیپلوی خودکار Cloudflare Worker، تولید کد Apps Script، مدیریت
کاربران با سهمیه‌ی ترافیک، و پایش زنده‌ی ترافیک.

روش کار رله: ترافیک از طریق Google Apps Script که پشت `www.google.com` پنهان
شده به یک Cloudflare Worker می‌رود. در دست ISP فقط SNI مربوط به گوگل دیده
می‌شود، نه مقصد واقعی.

## امکانات

| بخش | کار |
|---|---|
| **داشبورد** | آمار زنده مستقیماً از موتور در حال اجرا، نمودار سرعت لحظه‌ای، جدول پرترافیک‌ترین میزبان‌ها |
| **وضعیت** | اجرای رله، آخرین اتصال موفق، اعتماد سیستم‌عامل به گواهی CA، لاگ زنده |
| **دیپلوی** | آپلود کاملاً خودکار Worker با REST API کلودفلر + تولید `Code.gs` با مقادیر شما |
| **ساخت کانفیگ** | فرم کامل تمام کلیدهای کانفیگ + تولید `auth_key` قوی + پروفایل‌های ذخیره‌شده |
| **کاربران** | احراز هویت واقعی به‌ازای هر اتصال، سهمیه‌ی ترافیک، تاریخ انقضا، قطع خودکار |
| **تنظیمات** | رمز پنل، ویرایش `.env` فورواردر، وضعیت لایسنس، شفافیت شبکه |

### احراز هویت چندکاربره

- **Basic Auth** روی پروکسی HTTP (RFC 7235)
- **نام‌کاربری/رمز** روی SOCKS5 (RFC 1929)
- شمارش بایت جداگانه برای هر کاربر، با **قطع خودکار اتصال زنده** در سقف سهمیه
- رمزها با PBKDF2-HMAC-SHA256 (۱۲۰٬۰۰۰ دور) — هرگز به‌صورت متن ساده ذخیره نمی‌شوند
- تغییر کاربران **بلافاصله** روی رله‌ی در حال اجرا اعمال می‌شود، بدون ری‌استارت

کاملاً اختیاری است: بدون `proxy_auth.enabled` پروکسی بدون رمز کار می‌کند.

---

## نصب و اجرا

```bash
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

# لینوکس / مک
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r panel/requirements.txt
python -m panel
```

<details>
<summary>ویندوز</summary>

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r panel/requirements.txt
python -m panel
```
</details>

> **نکته برای مک:** روی macOS دستور `python` وجود ندارد و باید `python3` بزنید.
> بعد از فعال‌شدن venv (`source .venv/bin/activate`)، داخل آن `python` کار می‌کند.

سپس <http://127.0.0.1:8600> را باز کنید. بار اول یک رمز عبور برای پنل تعیین
می‌کنید (با PBKDF2 هش می‌شود).

راهنمای کامل و گام‌به‌گام: **[`panel/README.md`](panel/README.md)**

### پیش‌نیازها

- Python 3.10+
- توکن API کلودفلر با دسترسی `Account → Workers Scripts → Edit` (برای دیپلوی خودکار)
- یک حساب گوگل (برای استقرار Apps Script)

---

## معماری

پنل با Flask نوشته شده و موتور رله را در یک **ترد جداگانه با event loop
اختصاصی** اجرا می‌کند، نه به‌صورت subprocess. دلیلش این است که داشبورد باید
واقعاً زنده باشد: آمار مستقیماً از شیء در حال اجرا خوانده می‌شود، نه از روی
pars کردن لاگ.

کد پروژه در دو لایه‌ی مستقل چیده شده است:

| پوشه | نقش |
|---|---|
| `panel/` | لایه‌ی مدیریت — Flask، رابط کاربری، دیپلوی، کاربران، بکاپ |
| `engine/` | موتور رله — Domain Fronting، چرخش SNI، MITM محلی، HTTP/2 |
| `scripts/` | اجرای پس‌زمینه و نصب برای هر سه سیستم‌عامل |

موتور رله بر پایه‌ی کد متن‌باز با پروانه‌ی MIT ساخته شده است (بخش Credits).

---

## امنیت و شفافیت شبکه

این ابزار برای عبور از سانسور ساخته شده، پس پنل **عمداً** فاقد این موارد است:

- **بدون تله‌متری یا phone-home** — هیچ IP، آمار ترافیک یا هویتی به هیچ سرور مرکزی نمی‌رود
- **بدون کیل‌سوییچ از راه دور** — هیچ کانالی برای غیرفعال‌کردن رله‌ی کاربر وجود ندارد
- **بدون کد مبهم‌سازی‌شده** — همه‌چیز قابل حسابرسی است
- **بدون CDN خارجی** — فونت، آیکون، CSS و نمودار همگی محلی‌اند

کل مقصدهای خروجی این پروسه:

1. `api.cloudflare.com` — فقط هنگام بررسی توکن یا دیپلوی Worker
2. هرچه خودِ موتور رله با آن حرف می‌زند (Apps Script و Worker **خود شما**)

همین. این فهرست در صفحه‌ی «تنظیمات» پنل هم به کاربر نشان داده می‌شود.

سایر تدابیر: لاگین با PBKDF2، توکن CSRF روی همه‌ی فرم‌ها، rate limit، هدر
CSP سخت‌گیرانه بدون `unsafe-inline`، و نوشتن `config.json` و فایل‌های حالت
با دسترسی `0600` به‌صورت اتمیک.

---

## لایسنس

| بخش | پروانه |
|---|---|
| `panel/` | **اختصاصی** — [`panel/LICENSE`](panel/LICENSE) |
| `engine/`, `deploy/`, `main.py`, `setup.py` | **MIT** — [`LICENSE`](LICENSE) |

پروانه‌ی پنل، اجرای خصوصی نامحدود و حسابرسی امنیتی را کاملاً آزاد می‌گذارد؛
ولی ری‌برندسازی و فروش مجدد بدون اجازه‌ی کتبی مجاز نیست.

---

## سلب مسئولیت

این نرم‌افزار فقط برای اهداف آموزشی، تحقیقاتی و تست ارائه شده است.

- نرم‌افزار «همان‌طور که هست» (AS IS) ارائه می‌شود، بدون هیچ ضمانتی.
- توسعه‌دهندگان مسئولیتی در قبال خسارات احتمالی ندارند.
- رعایت قوانین محلی، ملی و بین‌المللی بر عهده‌ی کاربر است.
- رعایت شرایط استفاده از سرویس‌های Google و Cloudflare بر عهده‌ی کاربر است.

---

## English

**Aras-GP** is a Persian, RTL web control panel for a Domain Fronting relay that
tunnels traffic through Google Apps Script (fronted by `www.google.com`) to a
Cloudflare Worker.

It provides a live dashboard fed directly from the running relay object,
automated Cloudflare Worker deployment via the REST API, an Apps Script code
generator, a complete configuration builder, and a real per-connection
authentication layer (HTTP Basic + SOCKS5 RFC 1929) with per-user traffic
quotas and automatic cut-off.

The panel is fully offline — no external CDN, no telemetry, no phone-home, no
remote kill switch. Its only outbound call is `api.cloudflare.com` during a
deploy. A censorship-circumvention tool must not become the surveillance
chokepoint it exists to avoid.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r panel/requirements.txt
python -m panel          # → http://127.0.0.1:8600
```

Full documentation: [`panel/README.md`](panel/README.md).

The relay engine under `engine/` derives from MIT-licensed open-source code;
the full licence text is kept in [`LICENSE`](LICENSE) as MIT requires.

---

## Credits

موتور رله‌ی این پروژه از کد متن‌باز
[denuitt1/mhr-cfw](https://github.com/denuitt1/mhr-cfw) مشتق شده که تحت
پروانه‌ی **MIT** منتشر شده است. متن کامل آن پروانه در فایل
[`LICENSE`](LICENSE) نگه داشته شده — همان‌طور که MIT الزام می‌کند.

- با تشکر از [onlymaj](https://github.com/onlymaj)
