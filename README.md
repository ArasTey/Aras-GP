# Aras-GP

### پنل مدیریت وب برای رله‌ی Domain Fronting

| [فارسی](#معرفی) | [English](#english) |
| :---: | :---: |

---

> **این پروژه یک fork از [MHR-CFW](https://github.com/denuitt1/mhr-cfw) است.**
>
> موتور رله (`src/`, `deploy/`, `main.py`, `setup.py`) کار تیم اصلی است و تحت
> پروانه‌ی **MIT** باقی می‌ماند. مستندات اصلی پروژه در
> [`README_ORIGINAL.md`](README_ORIGINAL.md) و [`README_FA.md`](README_FA.md)
> دست‌نخورده نگه داشته شده‌اند.
>
> چیزی که در این fork اضافه شده، پوشه‌ی `panel/` است: یک پنل مدیریت تحت وب.

---

## معرفی

`MHR-CFW` یک ابزار عبور از فیلترینگ است که با روش **Domain Fronting** کار می‌کند:
ترافیک از طریق Google Apps Script که پشت `www.google.com` پنهان شده به یک
Cloudflare Worker می‌رود. موتور آن کامل و کاراست، ولی فقط از خط فرمان کنترل
می‌شد.

**Aras-GP Panel** آن لایه‌ی گمشده است — یک رابط وب فارسی و راست‌چین برای
پیکربندی، دیپلوی، اجرا و پایش همان موتور.

## پنل چه می‌کند

| بخش | کار |
|---|---|
| **داشبورد** | آمار زنده مستقیماً از موتور در حال اجرا (`stats_snapshot()`)، نمودار سرعت، جدول میزبان‌ها |
| **وضعیت** | اجرای رله، آخرین اتصال موفق، اعتماد سیستم به گواهی CA، لاگ زنده |
| **دیپلوی** | آپلود خودکار Worker به Cloudflare + تولید `Code.gs` با مقادیر شما |
| **ساخت کانفیگ** | فرم کامل تمام کلیدهای `config.example.json` + تولید `auth_key` قوی |
| **کاربران** | احراز هویت واقعی per-connection، سهمیه‌ی ترافیک، انقضا |
| **تنظیمات** | رمز پنل، ویرایش `.env` فورواردر، وضعیت لایسنس، شفافیت شبکه |

### احراز هویت چندکاربره

موتور اصلی یک پروکسی شخصی تک‌کاربره بود. این fork یک لایه‌ی واقعی اضافه می‌کند:

- **Basic Auth** روی پروکسی HTTP (RFC 7235)
- **نام‌کاربری/رمز** روی SOCKS5 (RFC 1929)
- شمارش بایت جداگانه برای هر کاربر، با **قطع خودکار** در سقف سهمیه
- رمزها با PBKDF2-HMAC-SHA256 (۱۲۰٬۰۰۰ دور) ذخیره می‌شوند

کاملاً **اختیاری** است: بدون `proxy_auth.enabled`، پروکسی دقیقاً مثل قبل بدون
رمز کار می‌کند و رفتار اصلی پروژه دست‌نخورده می‌ماند.

---

## اجرا

```bash
python -m venv .venv
source .venv/bin/activate          # ویندوز: .venv\Scripts\activate
pip install -r requirements.txt -r panel/requirements.txt

python -m panel
```

سپس <http://127.0.0.1:8600> را باز کنید. بار اول یک رمز عبور برای پنل تعیین می‌کنید.

راهنمای کامل: **[`panel/README.md`](panel/README.md)**

### پیش‌نیازها

- Python 3.10+
- یک توکن API کلودفلر با دسترسی `Account → Workers Scripts → Edit` (برای دیپلوی خودکار)
- یک حساب گوگل (برای استقرار Apps Script)

---

## شفافیت شبکه

این ابزار برای عبور از سانسور ساخته شده، پس پنل عمداً فاقد این موارد است:

- **بدون تله‌متری یا phone-home** — هیچ IP، آماری یا هویتی به هیچ سرور مرکزی نمی‌رود
- **بدون کیل‌سوییچ از راه دور**
- **بدون کد مبهم‌سازی‌شده** — همه‌چیز قابل حسابرسی است
- **بدون CDN خارجی** — فونت، آیکون، CSS و JS همگی محلی‌اند

کل مقصدهای خروجی این پروسه:

1. `api.cloudflare.com` — فقط هنگام بررسی توکن یا دیپلوی Worker
2. هرچه خودِ موتور رله با آن حرف می‌زند (Apps Script و Worker **خود شما**)

همین. این فهرست در صفحه‌ی «تنظیمات» پنل هم به کاربر نشان داده می‌شود.

---

## لایسنس

این مخزن دو پروانه دارد:

| بخش | پروانه |
|---|---|
| `src/`, `deploy/`, `main.py`, `setup.py` | **MIT** — [`LICENSE`](LICENSE) (کار پروژه‌ی اصلی) |
| `panel/` | **اختصاصی** — [`panel/LICENSE`](panel/LICENSE) |

`src/account_manager.py` و تغییرات `src/proxy_server.py` هم چون از کد MIT مشتق
شده‌اند، تحت **MIT** باقی می‌مانند.

پروانه‌ی پنل حسابرسی امنیتی، انتشار نتایج بررسی و اجرای خصوصی نامحدود را آزاد
می‌گذارد؛ ولی ری‌برندسازی و فروش مجدد بدون اجازه‌ی کتبی مجاز نیست.

---

## سلب مسئولیت

این نرم‌افزار فقط برای اهداف آموزشی، تحقیقاتی و تست ارائه شده است.

- نرم‌افزار «همان‌طور که هست» (AS IS) ارائه می‌شود، بدون هیچ ضمانتی.
- توسعه‌دهندگان مسئولیتی در قبال خسارات احتمالی ندارند.
- رعایت قوانین محلی، ملی و بین‌المللی بر عهده‌ی کاربر است.
- رعایت شرایط استفاده از سرویس‌های Google و Cloudflare بر عهده‌ی کاربر است.

---

## English

**This is a fork of [MHR-CFW](https://github.com/denuitt1/mhr-cfw).** The relay
engine is the original team's work and stays under the **MIT** licence; the
original documentation is preserved in
[`README_ORIGINAL.md`](README_ORIGINAL.md).

What this fork adds is `panel/` — **Aras-GP Panel**, a Persian, RTL web control
surface for that engine: live dashboard fed directly from the running
`DomainFronter`, automated Cloudflare Worker deployment, an Apps Script
generator, a full `config.json` builder, and a real per-connection
authentication layer (HTTP Basic + SOCKS5 RFC 1929) with per-user traffic
quotas and automatic cut-off.

The panel makes **no** outbound request other than `api.cloudflare.com` during a
deploy. No telemetry, no phone-home, no remote kill switch, no external CDN — a
censorship-circumvention tool must not become the surveillance chokepoint it
exists to avoid.

Run it:

```bash
pip install -r requirements.txt -r panel/requirements.txt
python -m panel          # → http://127.0.0.1:8600
```

Full documentation: [`panel/README.md`](panel/README.md).

Licensing: relay = MIT ([`LICENSE`](LICENSE)); panel = proprietary
([`panel/LICENSE`](panel/LICENSE)), which permits unlimited private use and
security auditing but not rebranding or resale.

---

### Credits

- Original project: [denuitt1/mhr-cfw](https://github.com/denuitt1/mhr-cfw)
- Special thanks to [onlymaj](https://github.com/onlymaj)
