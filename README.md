<div align="center">

<img src="panel/static/brand/aras-mark.svg" width="96" height="96" alt="Aras-GP">

# Aras-GP

### پنل مدیریت وب برای عبور از فیلترینگ با Domain Fronting

پنلی فارسی، راست‌چین و کاملاً آفلاین برای پیکربندی، دیپلوی، اجرا و پایش
یک رله‌ی Domain Fronting روی Google Apps Script و Cloudflare Workers.

<img src="docs/screenshots/dashboard.png" width="880" alt="داشبورد Aras-GP">

</div>

---

## فهرست

- [این چیست](#این-چیست)
- [نمای پنل](#نمای-پنل)
- [نصب](#نصب)
- [راه‌اندازی در شش قدم](#راهاندازی-در-شش-قدم)
- [اجرای دائمی](#اجرای-دائمی)
- [کاربران و سهمیه](#کاربران-و-سهمیه)
- [ChatGPT و IP ثابت](#chatgpt-و-ip-ثابت)
- [سوییچ خودکار بین رله‌ها](#سوییچ-خودکار-بین-رلهها)
- [پشتیبان‌گیری](#پشتیبانگیری)
- [عیب‌یابی](#عیبیابی)
- [امنیت و شفافیت شبکه](#امنیت-و-شفافیت-شبکه)
- [معماری](#معماری)
- [لایسنس](#لایسنس)

---

## این چیست

**Aras-GP** کل چرخه‌ی راه‌اندازی یک رله‌ی عبور از فیلترینگ را از خط فرمان به یک
رابط گرافیکی می‌آورد.

روش کار: ترافیک شما از یک Google Apps Script که پشت `www.google.com` پنهان شده
به یک Cloudflare Worker می‌رود و از آنجا به مقصد. آنچه ISP می‌بیند فقط یک اتصال
TLS به گوگل است — نه مقصد واقعی.

| بخش | کار |
|---|---|
| **داشبورد** | آمار زنده مستقیماً از موتور در حال اجرا، نمودار سرعت، جدول میزبان‌ها |
| **وضعیت** | اجرای رله، آخرین اتصال موفق، اعتماد سیستم به CA، لاگ زنده |
| **دیپلوی** | آپلود خودکار Worker با REST API + تولید `Code.gs` + ذخیره‌ی رله |
| **ساخت کانفیگ** | فرم کامل همه‌ی کلیدها + تولید کلید قوی + پروفایل‌ها |
| **کاربران** | احراز هویت per-connection، سهمیه، انقضا، قطع خودکار |
| **تنظیمات** | خروجی AI، پشتیبان‌گیری، سوییچ خودکار، رمز پنل |
| **راهنما** | آموزش گام‌به‌گام با چک‌لیست پیشرفت واقعی شما |

---

## نمای پنل

<details open>
<summary><b>داشبورد</b> — آمار زنده و نمودار سرعت</summary>
<img src="docs/screenshots/dashboard.png" alt="داشبورد">
</details>

<details>
<summary><b>کاربران</b> — سهمیه، انقضا، وضعیت لحظه‌ای</summary>
<img src="docs/screenshots/users.png" alt="کاربران">
</details>

<details>
<summary><b>دیپلوی</b> — Worker خودکار، Code.gs، ذخیره‌ی رله</summary>
<img src="docs/screenshots/deploy.png" alt="دیپلوی">
</details>

<details>
<summary><b>وضعیت</b> — سلامت زنجیره، گواهی CA، لاگ زنده</summary>
<img src="docs/screenshots/status.png" alt="وضعیت">
</details>

<details>
<summary><b>ساخت کانفیگ</b> — همه‌ی کلیدها در یک فرم</summary>
<img src="docs/screenshots/config.png" alt="ساخت کانفیگ">
</details>

<details>
<summary><b>تنظیمات</b> — خروجی AI، پشتیبان‌گیری، سوییچ خودکار</summary>
<img src="docs/screenshots/settings.png" alt="تنظیمات">
</details>

<details>
<summary><b>راهنما</b> — آموزش داخل پنل با چک‌لیست</summary>
<img src="docs/screenshots/guide.png" alt="راهنما">
</details>

<details>
<summary><b>ورود</b> و <b>موبایل</b></summary>
<p align="center">
<img src="docs/screenshots/login.png" width="55%" alt="ورود">
<img src="docs/screenshots/mobile.png" width="28%" alt="موبایل">
</p>
</details>

---

## نصب

### پیش‌نیازها

| مورد | لازم برای |
|---|---|
| Python 3.10+ | همه‌چیز |
| حساب Google | استقرار Apps Script |
| توکن API کلودفلر | دیپلوی خودکار Worker — پنل لینک ساختش را می‌دهد |
| یک VPS ارزان | فقط اگر ChatGPT یا IP ثابت می‌خواهید — اختیاری |

### لینوکس / مک

```bash
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r panel/requirements.txt

python -m panel
```

> **مک:** دستور `python` روی macOS وجود ندارد. برای ساخت venv حتماً `python3`
> بزنید؛ بعد از `source .venv/bin/activate` دستور `python` داخل venv کار می‌کند.

### ویندوز

```powershell
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r panel\requirements.txt

python -m panel
```

> اگر PowerShell اجرای اسکریپت را مسدود کرد:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

سپس **<http://127.0.0.1:8600>** را باز کنید. بار اول یک رمز عبور برای پنل تعیین
می‌کنید (با PBKDF2 هش می‌شود).

### متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `ARAS_PANEL_HOST` | `127.0.0.1` | آدرس شنود پنل |
| `ARAS_PANEL_PORT` | `8600` | پورت پنل |
| `ARAS_DATA_DIR` | `panel/data` | محل نگهداری وضعیت پنل |
| `DFT_CONFIG` | `config.json` | مسیر کانفیگ رله |
| `ARAS_LICENSE_PUBKEY` | — | فعال‌سازی قفل لایسنس آفلاین |

---

## راه‌اندازی در شش قدم

بعد از ورود، صفحه‌ی **راهنما** داخل پنل همین مراحل را با چک‌لیست پیشرفت واقعی
شما نشان می‌دهد.

**۱ — کلید احراز هویت.** در صفحه‌ی دیپلوی روی دکمه‌ی تولید کلید بزنید. این رمز
مشترک بین رله و Apps Script شماست.

**۲ — Cloudflare Worker.** دکمه‌ی «ساخت توکن با دسترسی آماده» صفحه‌ی کلودفلر را
با دسترسی‌های لازم از پیش تیک‌خورده باز می‌کند؛ فقط Continue و Create Token.
توکن **فقط یک بار** نمایش داده می‌شود. آن را در پنل بگذارید و «دیپلوی Worker».

**۳ — Apps Script.** «تولید Code.gs» را بزنید، کد را در
[script.google.com](https://script.google.com) جای‌گذاری کنید، بعد
Deploy → New deployment → **Web app** با:

- Execute as: **Me**
- Who has access: **Anyone** ← اگر اشتباه باشد رله وصل نمی‌شود

آدرس نهایی (`.../macros/s/XXXX/exec`) را در پنل ثبت کنید.

**۴ — گواهی CA.** صفحه‌ی وضعیت → «نصب گواهی». روی macOS معمولاً یک دستور
`sudo` هم لازم است که پنل همان‌جا نشان می‌دهد. بعد مرورگر را **کامل** ببندید
(⌘Q) و باز کنید.

**۵ — روشن‌کردن رله.** از نوار کناری. بعد «تست اتصال رله» در داشبورد.

**۶ — تنظیم مرورگر.** پروکسی روی `127.0.0.1:8085` (HTTP) یا `127.0.0.1:1080`
(SOCKS5). برای تست به `https://ip.me` بروید — باید IP دیگری ببینید.

---

## اجرای دائمی

اجرای `python -m panel` در ترمینال، رله را به آن ترمینال وابسته می‌کند: با بستن
پنجره تونل هم قطع می‌شود. برای اجرای مستقل:

```bash
./scripts/aras-panel.sh start      # لینوکس / مک
./scripts/aras-panel.sh status
./scripts/aras-panel.sh logs
./scripts/aras-panel.sh stop
```

```powershell
.\scripts\aras-panel.ps1 start     # ویندوز
.\scripts\aras-panel.ps1 stop
```

---

## کاربران و سهمیه

پروکسی به‌صورت پیش‌فرض تک‌کاربره و بدون رمز است. برای اشتراک با دیگران، در
صفحه‌ی **کاربران** سوییچ احراز هویت را روشن کنید:

- **Basic Auth** روی پروکسی HTTP (RFC 7235)
- **نام‌کاربری/رمز** روی SOCKS5 (RFC 1929)
- شمارش بایت جداگانه برای هر کاربر، با **قطع خودکار اتصال زنده** در سقف سهمیه
- تاریخ انقضا برای هر کاربر
- رمزها با PBKDF2-HMAC-SHA256 (۱۲۰٬۰۰۰ دور) — هرگز متن ساده ذخیره نمی‌شوند
- تغییرات **بلافاصله** اعمال می‌شوند، بدون ری‌استارت

> ⚠️ اگر `lan_sharing` را روشن می‌کنید حتماً احراز هویت را هم روشن کنید، وگرنه
> هر دستگاهی در شبکه بدون رمز از پروکسی شما استفاده می‌کند. پنل هشدار می‌دهد.

---

## ChatGPT و IP ثابت

ترافیکی که از Cloudflare Workers خارج می‌شود با IP رنج کلودفلر به مقصد می‌رسد و
OpenAI آن رنج را مسدود کرده:

```
Unable to load site — [IP:2a06:98c0:3600::103 | Ray ID:…]
```

این داخل رله قابل حل نیست. راهش یک **خروجی دیگر** است: یک VPS که شما کنترلش
می‌کنید. پنل دو روش می‌دهد.

### روش امن — از مسیر گوگل (پیشنهادی)

```
مرورگر → رله → TLS(SNI=google.com) → Apps Script → Worker → HTTPS → VPS شما → مقصد
```

ISP همچنان فقط گوگل می‌بیند و مقصد IP ثابت VPS شما را.

```bash
# روی VPS، با دامنه‌ی خودتان (Caddy گواهی را خودکار می‌گیرد)
sudo bash scripts/install-forwarder.sh --domain fwd.example.com

# یا بدون دامنه، با Cloudflare Tunnel
sudo bash scripts/install-forwarder.sh --tunnel
```

### روش سریع — مستقیم

```
مرورگر → رله → SOCKS5 روی VPS شما → مقصد
```

دو هاپ کمتر و سریع‌تر، ولی اتصال به VPS برای ISP قابل دیدن است و Domain Fronting
ندارد.

```bash
sudo bash scripts/install-exit-node.sh
```

هر دو اسکریپت آخر کارشان یک خط به شما می‌دهند که در **تنظیمات** پنل وارد
می‌کنید. فقط دامنه‌های فهرست‌شده از این مسیر می‌روند؛ بقیه از رله. اگر VPS خاموش
شود، آن میزبان‌ها خودکار به رله برمی‌گردند.

---

## سوییچ خودکار بین رله‌ها

هر زنجیره‌ی کارکرده را می‌توانید در صفحه‌ی دیپلوی با یک نام **ذخیره** کنید.
دفعه‌ی بعد به‌جای دیپلوی دوباره، یک کلیک سوییچ می‌کنید.

با روشن‌کردن «سوییچ خودکار» در تنظیمات، اگر رله‌ی فعال بیش از آستانه (پیش‌فرض ۶۰
ثانیه) پیوسته خطا بدهد، پنل خودش به رله‌ی بعدی می‌رود.

تشخیص **کاملاً منفعل** است: از روی شمارنده‌های ترافیک واقعی خوانده می‌شود، نه
پینگ دوره‌ای. رله‌ی بی‌کار هرگز «خراب» حساب نمی‌شود و اگر اخیراً موفقیتی بوده
باشد سوییچ نمی‌کند — یعنی یک سایت خراب کل تونل را جابه‌جا نمی‌کند.

---

## پشتیبان‌گیری

در **تنظیمات**:

- **پشتیبان کامل** — کانفیگ، کاربران، رله‌ها، پروفایل‌ها، تنظیمات
- **بدون رمزها** — همان فایل بدون کلید احراز هویت و هش رمز کاربران، برای وقتی
  که می‌خواهید فایل را برای پشتیبانی بفرستید
- **بازگردانی** از فایل
- **پاک‌کردن همه‌ی داده‌ها** با تأیید تایپی

توکن Cloudflare **هرگز** داخل فایل پشتیبان نوشته نمی‌شود.

---

## عیب‌یابی

| نشانه | علت معمول | راه حل |
|---|---|---|
| `ERR_CERT_AUTHORITY_INVALID` | گواهی در System keychain نیست یا مرورگر restart نشده | وضعیت → نصب گواهی + دستور `sudo` که نشان می‌دهد، بعد ⌘Q روی مرورگر |
| «تست اتصال» ناموفق | Deployment ID اشتباه، یا `Who has access` روی Anyone نیست، یا `auth_key` با `Code.gs` یکی نیست | کد را دوباره تولید و جای‌گذاری کنید و یک deployment تازه بسازید |
| اولین درخواست ۳ تا ۵ ثانیه | Apps Script باید container را بیدار کند | چند Deployment ID اضافه کنید و `parallel_relay` را ۲ یا ۳ بگذارید |
| ChatGPT باز نمی‌شود، بقیه کار می‌کنند | IP خروجی کلودفلر بلاک شده | بخش [ChatGPT و IP ثابت](#chatgpt-و-ip-ثابت) |
| با بستن ترمینال قطع می‌شود | پنل وابسته به ترمینال اجرا شده | `./scripts/aras-panel.sh start` |
| رمز پنل فراموش شده | — | `panel/data/panel.json` را پاک کنید؛ کانفیگ و کاربران می‌مانند |
| پورت اشغال است | نمونه‌ی دیگری در حال اجراست | `./scripts/aras-panel.sh stop` یا پورت‌ها را عوض کنید |

اول از همه: **وضعیت → لاگ زنده‌ی رله**. لاگ فقط در حافظه است، روی دیسک نوشته
نمی‌شود، و هرگز `auth_key` یا رمز کاربران را نشان نمی‌دهد.

---

## امنیت و شفافیت شبکه

این ابزار برای عبور از سانسور ساخته شده، پس پنل **عمداً** فاقد این موارد است:

- **بدون تله‌متری یا phone-home** — هیچ IP، آمار ترافیک یا هویتی به هیچ سرور
  مرکزی نمی‌رود
- **بدون کیل‌سوییچ از راه دور** — هیچ کانالی برای غیرفعال‌کردن رله‌ی شما نیست
- **بدون کد مبهم‌سازی‌شده** — همه‌چیز قابل حسابرسی است
- **بدون CDN خارجی** — فونت، آیکون، CSS و نمودار همگی محلی‌اند، پس پنل روی
  شبکه‌ی فیلترشده هم کامل رندر می‌شود و صرفِ باز کردنش چیزی لو نمی‌دهد

کل مقصدهای خروجی این پروسه:

1. `api.cloudflare.com` — فقط هنگام بررسی توکن یا دیپلوی Worker
2. هرچه خودِ موتور رله با آن حرف می‌زند (Apps Script و Worker **خود شما**)

همین فهرست در صفحه‌ی تنظیمات پنل هم به کاربر نشان داده می‌شود.

**سایر تدابیر:** لاگین با PBKDF2 · کوکی `HttpOnly` + `SameSite=Lax` · توکن CSRF
روی همه‌ی درخواست‌های غیر-GET · rate limit روی لاگین، دیپلوی و تست‌ها · هدر CSP
سخت‌گیرانه بدون `unsafe-inline` (هر بلاک inline یک nonce یکبارمصرف دارد) ·
`config.json` و فایل‌های حالت با دسترسی `0600` و نوشتن اتمیک.

> پنل پیش‌فرض روی `127.0.0.1` گوش می‌دهد. اگر `ARAS_PANEL_HOST` را عوض کردید،
> حتماً پشت VPN یا reverse proxy با TLS قرارش دهید — پنل `auth_key` و توکن
> کلودفلر را در اختیار دارد.

---

## معماری

```
Aras-GP/
├── panel/          لایه‌ی مدیریت — Flask، UI، دیپلوی، کاربران، بکاپ
├── engine/         موتور رله — Domain Fronting، چرخش SNI، MITM محلی، HTTP/2
├── scripts/        اجرای پس‌زمینه + نصب خروجی روی VPS
├── deploy/         کد Worker و Apps Script
└── docs/           اسکرین‌شات‌ها
```

پنل موتور را در یک **ترد جداگانه با event loop اختصاصی** اجرا می‌کند، نه به‌صورت
subprocess. دلیلش این است که داشبورد باید واقعاً زنده باشد: آمار مستقیماً از شیء
در حال اجرا خوانده می‌شود، نه از روی pars کردن لاگ. هر فراخوانی که به وضعیت رله
دست می‌زند با `run_coroutine_threadsafe` به همان event loop برگردانده می‌شود، پس
دیکشنری‌های داخلی فقط از تردی خوانده می‌شوند که آن‌ها را تغییر می‌دهد.

**بهینه‌سازی مصرف:** پنل هیچ ترد اضافه‌ای نمی‌سازد — فیل‌اوور و ذخیره‌ی سهمیه روی
همان تیک نمونه‌برداری موجود سوارند. پولینگ داشبورد وقتی تب مخفی است **کاملاً
متوقف** می‌شود و وقتی رله خاموش است کندتر می‌شود.

---

## لایسنس

| بخش | پروانه |
|---|---|
| `panel/` | **اختصاصی** — [`panel/LICENSE`](panel/LICENSE) |
| `engine/`, `deploy/`, `main.py`, `setup.py` | **MIT** — [`LICENSE`](LICENSE) |

پروانه‌ی پنل اجرای خصوصی نامحدود و حسابرسی امنیتی را کاملاً آزاد می‌گذارد؛ ولی
ری‌برندسازی و فروش مجدد بدون اجازه‌ی کتبی مجاز نیست.

موتور رله از کد متن‌باز [denuitt1/mhr-cfw](https://github.com/denuitt1/mhr-cfw)
مشتق شده که تحت **MIT** منتشر شده. متن کامل آن پروانه در [`LICENSE`](LICENSE)
نگه داشته شده، همان‌طور که MIT الزام می‌کند.

---

## سلب مسئولیت

این نرم‌افزار فقط برای اهداف آموزشی، تحقیقاتی و تست ارائه شده است.

- نرم‌افزار «همان‌طور که هست» (AS IS) ارائه می‌شود، بدون هیچ ضمانتی.
- توسعه‌دهندگان مسئولیتی در قبال خسارات احتمالی ندارند.
- رعایت قوانین محلی، ملی و بین‌المللی بر عهده‌ی کاربر است.
- رعایت شرایط استفاده از سرویس‌های Google و Cloudflare بر عهده‌ی کاربر است.

---

<div align="center">

## English

**Aras-GP** is a Persian, RTL web control panel for a Domain Fronting relay that
tunnels traffic through Google Apps Script (fronted by `www.google.com`) to a
Cloudflare Worker.

</div>

It provides a live dashboard fed directly from the running relay object,
automated Cloudflare Worker deployment via the REST API, an Apps Script code
generator, a complete configuration builder, saved relays with passive
automatic failover, and a real per-connection authentication layer
(HTTP Basic + SOCKS5 RFC 1929) with per-user traffic quotas and automatic
cut-off.

For services that reject Cloudflare Workers egress (OpenAI and friends), two
installers set up an exit on your own VPS — one that keeps domain fronting
intact by routing through the Worker, and a faster direct SOCKS5 one. Both give
you a stable outbound IP.

The panel is fully offline: no external CDN, no telemetry, no phone-home, no
remote kill switch. Its only outbound call is `api.cloudflare.com` during a
deploy. A censorship-circumvention tool must not become the surveillance
chokepoint it exists to avoid.

```bash
git clone https://github.com/ArasTey/Aras-GP.git && cd Aras-GP
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r panel/requirements.txt
python -m panel          # → http://127.0.0.1:8600
```

Licensing: `panel/` is proprietary ([`panel/LICENSE`](panel/LICENSE)) and
permits unlimited private use and security auditing but not rebranding or
resale. The relay engine under `engine/` derives from MIT-licensed code; the
full licence text is kept in [`LICENSE`](LICENSE) as MIT requires.
