<div align="center">

<img src="panel/static/brand/aras-mark.svg" width="104" height="104" alt="Aras-GP">

# Aras-GP

### پنل مدیریت وب برای عبور از فیلترینگ با Domain Fronting

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-Workers-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://workers.cloudflare.com/)
[![Google](https://img.shields.io/badge/Google-Apps%20Script-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://script.google.com/)

[![Platform](https://img.shields.io/badge/Linux%20%7C%20macOS%20%7C%20Windows-2ea043?style=flat-square)](#install)
[![RTL](https://img.shields.io/badge/رابط-فارسی%20راست%E2%80%8Cچین-7C5CFF?style=flat-square)](#)
[![Offline](https://img.shields.io/badge/بدون%20CDN%20خارجی-100%25%20آفلاین-22c58c?style=flat-square)](#security)
[![Telemetry](https://img.shields.io/badge/تله%E2%80%8Cمتری-صفر-f4536f?style=flat-square)](#security)

<img src="docs/screenshots/dashboard.png" width="900" alt="داشبورد Aras-GP">

</div>

---

## 📑 فهرست

| | | |
|---|---|---|
| [🎯 این چیست](#what) | [🖼️ نمای پنل](#gallery) | [⚙️ نصب](#install) |
| [🚀 راه‌اندازی](#setup) | [🔁 اجرای دائمی](#daemon) | [👥 کاربران](#users) | [🔗 دوستان](#setup) |
| [🔀 سوییچ خودکار](#failover) | [💾 پشتیبان‌گیری](#backup) |
| [🧩 مرجع کانفیگ](#config-ref) | [🔌 مرجع API](#api-ref) | [📜 مرجع اسکریپت‌ها](#scripts-ref) |
| [🩺 عیب‌یابی](#troubleshooting) | [🔐 امنیت](#security) | [🏗️ معماری](#architecture) |
| [🧪 توسعه و تست](#dev) | [📄 لایسنس](#license) | [⚠️ سلب مسئولیت](#disclaimer) |

---

<a id="what"></a>

## 🎯 این چیست

**Aras-GP** کل چرخه‌ی راه‌اندازی یک رله‌ی عبور از فیلترینگ را از خط فرمان به یک
رابط گرافیکی می‌آورد.

```mermaid
flowchart LR
    A["🖥️ مرورگر شما"] -->|"پروکسی محلی"| B["⚙️ موتور رله"]
    B -->|"TLS با SNI=www.google.com"| C["📄 Google Apps Script"]
    C -->|"HTTPS"| D["☁️ Cloudflare Worker"]
    D --> E["🌐 مقصد"]
    F -.-> E
    style A fill:#7C5CFF,stroke:#9B81FF,color:#fff
    style B fill:#2F83F6,stroke:#57A5FF,color:#fff
    style C fill:#4285F4,stroke:#8EC5FF,color:#fff
    style D fill:#F38020,stroke:#FFA257,color:#fff
    style E fill:#22c58c,stroke:#43E0A8,color:#fff
    style F fill:#f4536f,stroke:#FF7A90,color:#fff
```

آنچه ISP می‌بیند فقط یک اتصال TLS به گوگل است — نه مقصد واقعی.

### امکانات

| بخش | کار |
|:--|:--|
| 📊 **داشبورد** | آمار زنده مستقیماً از موتور در حال اجرا، نمودار سرعت، جدول میزبان‌ها |
| 🩺 **وضعیت** | اجرای رله، آخرین اتصال موفق، اعتماد سیستم به CA، لاگ زنده |
| 🚀 **دیپلوی** | آپلود خودکار Worker + تولید `Code.gs` + ذخیره‌ی رله برای استفاده‌ی مجدد |
| 🎛️ **ساخت کانفیگ** | فرم کامل همه‌ی کلیدها + تولید کلید قوی + پروفایل‌ها |
| 👥 **کاربران** | احراز هویت per-connection، سهمیه‌ی حجمی، تاریخ انقضا، قطع خودکار |
| 🔗 **دوستان** | لینک `vless://` برای هر نفر، لینک اشتراک، ابطال آنی |
| ⚙️ **تنظیمات** | پشتیبان‌گیری، سوییچ خودکار، رمز پنل |
| 📖 **راهنما** | آموزش گام‌به‌گام داخل پنل با چک‌لیست پیشرفت واقعی شما |

---

<a id="gallery"></a>

## 🖼️ نمای پنل

<details open>
<summary><b>📊 داشبورد</b> — آمار زنده، نمودار سرعت، سلامت مسیر</summary>
<br><img src="docs/screenshots/dashboard.png" alt="داشبورد">
</details>

<details>
<summary><b>🔗 دوستان</b> — لینک VLESS برای موبایل، لینک اشتراک</summary>
<br><img src="docs/screenshots/friends.png" alt="دوستان">
</details>

<details>
<summary><b>👥 کاربران</b> — سهمیه، انقضا، وضعیت لحظه‌ای، قطع اتصال</summary>
<br><img src="docs/screenshots/users.png" alt="کاربران">
</details>

<details>
<summary><b>🚀 دیپلوی</b> — Worker خودکار، Code.gs، ذخیره‌ی رله</summary>
<br><img src="docs/screenshots/deploy.png" alt="دیپلوی">
</details>

<details>
<summary><b>🩺 وضعیت</b> — سلامت زنجیره، گواهی CA، لاگ زنده</summary>
<br><img src="docs/screenshots/status.png" alt="وضعیت">
</details>

<details>
<summary><b>🎛️ ساخت کانفیگ</b> — همه‌ی کلیدها در یک فرم</summary>
<br><img src="docs/screenshots/config.png" alt="ساخت کانفیگ">
</details>

<details>
<summary><b>⚙️ تنظیمات</b> — پشتیبان‌گیری، سوییچ خودکار</summary>
<br><img src="docs/screenshots/settings.png" alt="تنظیمات">
</details>

<details>
<summary><b>📖 راهنما</b> — آموزش داخل پنل با چک‌لیست پیشرفت</summary>
<br><img src="docs/screenshots/guide.png" alt="راهنما">
</details>

<details>
<summary><b>📱 روی موبایل</b> — کل پنل روی گوشی کار می‌کند</summary>
<br>
<p align="center">
<img src="docs/screenshots/mobile.png" width="30%" alt="داشبورد موبایل">
<img src="docs/screenshots/mobile-friends.png" width="30%" alt="دوستان موبایل">
<img src="docs/screenshots/mobile-status.png" width="30%" alt="وضعیت موبایل">
</p>
</details>

<details>
<summary><b>🔐 ورود</b></summary>
<br><p align="center"><img src="docs/screenshots/login.png" width="70%" alt="ورود"></p>
</details>

---

<a id="install"></a>

## ⚙️ نصب

### پیش‌نیازها

| مورد | لازم برای | اجباری؟ |
|:--|:--|:--:|
| Python 3.10+ | همه‌چیز | ✅ |
| حساب Google | استقرار Apps Script | ✅ |
| توکن API کلودفلر | دیپلوی خودکار Worker (پنل لینک ساختش را می‌دهد) | ✅ |

### 🐧 لینوکس

**ساده‌ترین راه (یک دستور):**

```bash
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP
./run.sh panel          # venv می‌سازد، وابستگی‌ها را نصب می‌کند، پنل را بالا می‌آورد
```

**یا دستی:**

```bash
# ۱. کلون
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

# ۲. محیط مجازی
python3 -m venv .venv
source .venv/bin/activate

# ۳. وابستگی‌ها
pip install -r requirements.txt

# ۴. اجرا
python -m panel
```

اگر `python3-venv` نصب نیست:
```bash
sudo apt install python3-venv python3-pip     # دبیان / اوبونتو
sudo dnf install python3-virtualenv           # فدورا
```

### 🍎 مک

```bash
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

python3 -m venv .venv          # ⚠️ روی مک حتماً python3، نه python
source .venv/bin/activate
pip install -r requirements.txt

python -m panel
```

> **چرا `python3`؟** روی macOS دستور `python` اصلاً وجود ندارد. اگر `python -m venv`
> بزنید venv ساخته نمی‌شود و pip بسته‌ها را روی پایتون سیستم نصب می‌کند.
> بعد از `source .venv/bin/activate` دستور `python` داخل venv در دسترس است.

### 🪟 ویندوز

**بدون git (اگر git نصب نیست):**

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/ArasTey/Aras-GP/main/scripts/get-aras.ps1 | iex"
```

خودش زیپ را دانلود می‌کند، باز می‌کند و پنل را بالا می‌آورد. اگر پوشه‌ی
`Aras-GP` از قبل باشد دست نمی‌زند (تا `config.json` و `ca\` شما پاک نشود).

یا دستی: از GitHub دکمه‌ی **Code → Download ZIP**، بعد اکسترکت و `run.bat panel`.

**با git:**

```bat
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP
run.bat panel
```

**یا دستی:**

```powershell
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m panel
```

اگر PowerShell اجرای اسکریپت را مسدود کرد:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

سپس **<http://127.0.0.1:8600>** را باز کنید. بار اول یک رمز عبور برای پنل تعیین
می‌کنید (با PBKDF2 هش می‌شود، هرگز متن ساده ذخیره نمی‌شود).

### 🐳 داکر

```bash
docker compose up -d          # از docker-compose.yml موجود
docker compose logs -f
```

### متغیرهای محیطی

| متغیر | پیش‌فرض | توضیح |
|:--|:--|:--|
| `ARAS_PANEL_HOST` | `127.0.0.1` | آدرس شنود پنل. تغییرش یعنی پنل روی شبکه باز می‌شود |
| `ARAS_PANEL_PORT` | `8600` | پورت پنل |
| `ARAS_DATA_DIR` | `panel/data` | محل نگهداری وضعیت پنل (رمز، رله‌ها، تنظیمات) |
| `DFT_CONFIG` | `config.json` | مسیر کانفیگ رله |
| `ARAS_LICENSE_PUBKEY` | — | فعال‌سازی قفل لایسنس آفلاین |

```bash
# مثال: پنل روی پورت دیگر با داده‌ی جدا
ARAS_PANEL_PORT=9000 ARAS_DATA_DIR=~/aras-data python -m panel
```

---

<a id="setup"></a>

## 🚀 راه‌اندازی از صفر تا صد

> صفحه‌ی **راهنما** داخل پنل همین مراحل را با چک‌لیست پیشرفت واقعی شما نشان می‌دهد.

```mermaid
flowchart TD
    S0["0️⃣ پیش‌نیازها"] --> S1["1️⃣ کلید احراز هویت"]
    S1 --> S2["2️⃣ دیپلوی Worker"]
    S2 --> S3["3️⃣ Apps Script"]
    S3 --> S4["4️⃣ نصب گواهی CA"]
    S4 --> S5["5️⃣ روشن‌کردن رله"]
    S5 --> S6["6️⃣ تنظیم مرورگر"]
    S6 --> S7["7️⃣ کانفیگ برای دوستان"]
    style S0 fill:#555,color:#fff
    style S1 fill:#7C5CFF,color:#fff
    style S2 fill:#F38020,color:#fff
    style S3 fill:#4285F4,color:#fff
    style S4 fill:#f4536f,color:#fff
    style S5 fill:#2F83F6,color:#fff
    style S6 fill:#22c58c,color:#fff
    style S7 fill:#7C5CFF,color:#fff
```

### ۰️⃣ قبل از شروع — چه چیزهایی لازم دارید

| مورد | چرا | اگر نداشته باشید |
|:--|:--|:--|
| **Python 3.10 یا بالاتر** | کل پروژه با پایتون است | از [python.org](https://www.python.org/downloads/) نصب کنید. روی ویندوز حتماً تیک **Add python.exe to PATH** |
| **یک حساب Google** | Apps Script روی آن اجرا می‌شود | حساب جدید بسازید. توصیه: یک حساب جدا، نه حساب اصلی‌تان |
| **یک حساب Cloudflare (رایگان)** | Worker روی آن دیپلوی می‌شود | ثبت‌نام رایگان است و کارت بانکی نمی‌خواهد |
| **حدود ۱۵ دقیقه وقت** | مرحله‌ی Apps Script دستی است | — |

> کلید احراز هویت و Account ID کلودفلر **هیچ‌کدام** را لازم نیست خودتان بسازید یا پیدا کنید؛ پنل هر دو را خودکار انجام می‌دهد.
| **git** | فقط برای کلون؛ اجباری نیست | روی ویندوز از راه بدون git استفاده کنید (بخش نصب) |

> ⚠️ **مهم — از این سه فایل بکاپ بگیرید:** `ca/`، `config.json` و `panel/data/`.
> این‌ها داخل git نیستند (عمداً، چون رمز و کلید دارند) و اگر پروژه را دوباره
> کلون کنید **پاک می‌شوند**: گواهی CA از نو ساخته می‌شود و باید دوباره نصبش
> کنید، و کانفیگ و رمز پنل از دست می‌رود.

### ۱️⃣ کلید احراز هویت — کاری ندارید

**خودکار است.** پنل خودش یک کلید تصادفی ۴۰ کاراکتری می‌سازد و داخل `Code.gs`ای
که تولید می‌کند می‌گذارد. نه جایی نمایش داده می‌شود، نه لازم است کپی یا وارد
کنید. کلید ساخته‌شده هیچ‌وقت خودبه‌خود عوض نمی‌شود، چون عوض‌شدنش یعنی
Apps Script قبلی شما دیگر کار نمی‌کند.

### ۲️⃣ Cloudflare Worker

دکمه‌ی **«ساخت توکن با دسترسی آماده»** صفحه‌ی کلودفلر را با دسترسی‌های زیر
از پیش تیک‌خورده باز می‌کند:

| دسترسی | چرا |
|:--|:--|
| `Account → Workers Scripts → Edit` | آپلود اسکریپت و فعال‌سازی workers.dev |
| `Account → Account Settings → Read` | فهرست‌کردن حساب‌ها تا Account ID خودکار پر شود |

فقط **Continue to summary** → **Create Token**.

> ⚠️ توکن **فقط یک بار** نمایش داده می‌شود. همان لحظه کپی کنید.

بعد در پنل: فقط توکن را پیست کنید و **دیپلوی Worker** را بزنید.
**Account ID لازم نیست** — از روی خود توکن خوانده می‌شود. اگر توکن شما به چند
حساب کلودفلر دسترسی داشته باشد، پنل فهرست را نشان می‌دهد تا یکی را انتخاب کنید.

پنل این پنج کار را انجام می‌دهد:

```
1. GET  /user/tokens/verify                                   بررسی توکن
1b. GET /accounts                                             یافتن خودکار Account ID
2. GET  /accounts/{id}/workers/subdomain                      یافتن زیردامنه
3.      جایگزینی WORKER_URL داخل worker.js با نام واقعی      محافظ حلقه
4. PUT  /accounts/{id}/workers/scripts/{name}                 آپلود ES module
5. POST /accounts/{id}/workers/scripts/{name}/subdomain       فعال‌سازی workers.dev
```

### ۳️⃣ Google Apps Script

**«تولید Code.gs»** را بزنید — کد با `AUTH_KEY` و `WORKER_URL` شما آماده می‌شود.

۱. به [script.google.com](https://script.google.com) بروید → **New project**
۲. کل محتوای `Code.gs` را پاک و کد تولیدشده را جای‌گذاری کنید
۳. ذخیره (`Ctrl+S` / `⌘+S`)
۴. **Deploy** → **New deployment** → نوع: **Web app**
۵. تنظیمات حساس:

| فیلد | مقدار |
|:--|:--|
| Execute as | **Me** |
| Who has access | **Anyone** ← اگر اشتباه باشد رله وصل نمی‌شود |

۶. اولین بار Google اجازه می‌خواهد → **Advanced** → اجازه بدهید
۷. آدرس نهایی (`https://script.google.com/macros/s/XXXX/exec`) را در پنل ثبت کنید

> 💡 چند Deployment ID اضافه کنید و `parallel_relay` را ۲ یا ۳ بگذارید تا
> سرعت بیشتر شود.

### ۴️⃣ نصب گواهی CA

صفحه‌ی **وضعیت** → **نصب گواهی**.

روی macOS نصب خودکار در `login keychain` انجام می‌شود ولی کروم و سافاری فقط
`System keychain` را برای یک root CA می‌پذیرند. پنل دستور لازم را همان‌جا
نشان می‌دهد:

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain ~/Aras-GP/ca/ca.crt
```

<details>
<summary>لینوکس و ویندوز</summary>

```bash
# لینوکس (دبیان/اوبونتو)
sudo cp ca/ca.crt /usr/local/share/ca-certificates/aras-gp.crt
sudo update-ca-certificates

# لینوکس (فدورا/RHEL)
sudo cp ca/ca.crt /etc/pki/ca-trust/source/anchors/aras-gp.crt
sudo update-ca-trust

# یا با خود پروژه، روی هر سیستم‌عاملی
python main.py --install-cert
```

```powershell
# ویندوز — با دسترسی Administrator
certutil -addstore -f "ROOT" ca\ca.crt
```
</details>

> بعد از نصب، مرورگر را **کامل** ببندید (`⌘Q` روی مک) و باز کنید.

### ۵️⃣ روشن‌کردن رله

نوار کناری → **راه‌اندازی رله**. بعد داشبورد → **تست اتصال رله**.

### ۶️⃣ تنظیم مرورگر یا سیستم

| نوع | آدرس |
|:--|:--|
| HTTP proxy | `127.0.0.1:8085` |
| SOCKS5 | `127.0.0.1:1080` |

<details>
<summary>روش‌های مختلف تنظیم</summary>

**افزونه‌ی FoxyProxy** (کروم/فایرفاکس) — راحت‌ترین، فقط ترافیک مرورگر.

**کل سیستم روی مک:**
System Settings → Network → Wi-Fi → Details → Proxies → **SOCKS Proxy**
با `127.0.0.1` و `1080`.

**کل سیستم روی ویندوز:**
Settings → Network & Internet → Proxy → Manual proxy setup.

**خط فرمان:**
```bash
export http_proxy=http://127.0.0.1:8085
export https_proxy=http://127.0.0.1:8085
curl https://ip.me          # باید IP دیگری نشان دهد
```
</details>

**تست نهایی:** به `https://ip.me` بروید — باید IP دیگری غیر از IP خودتان ببینید.

### ۷️⃣ دادن کانفیگ به دوستان (اختیاری — VLESS روی موبایل)

اگر می‌خواهید دوستانتان هم استفاده کنند، صفحه‌ی **دوستان** برای هر نفر یک لینک
`vless://` می‌سازد که در **v2rayNG / NekoBox / Shadowrocket / sing-box** کار می‌کند.

> ⚠️ **قبل از استفاده حتماً بخوانید.** این قابلیت از Cloudflare Workers به‌عنوان
> سرور VLESS استفاده می‌کند. شرایط استفاده‌ی کلودفلر پروکسی عمومی را مجاز
> نمی‌داند و **ممکن است Worker یا کل حساب کلودفلر شما مسدود شود**. این را
> بدانید و خودتان تصمیم بگیرید.

**چرا اصلاً کار می‌کند و به VPS نیاز ندارد؟** چون خود Worker نقش سرور VLESS را
بازی می‌کند: اتصال WebSocket را می‌گیرد، هدر VLESS را می‌خواند، UUID را با
لیستی که موقع دیپلوی روی Worker بایند شده چک می‌کند، و از لبه‌ی کلودفلر به
مقصد وصل می‌شود. آدرس `workers.dev` از همه‌جای دنیا و از پشت NAT در دسترس است،
پس دوست شما فقط به لینک نیاز دارد.

**مراحل:**

۱. اول باید Worker دیپلوی شده باشد (قدم ۲). بدون آن این صفحه غیرفعال است.
۲. صفحه‌ی **دوستان** → نام دوست را بنویسید → **افزودن**
۳. لینک ساخته می‌شود. دکمه‌ی **کپی لینک** → برای دوستتان بفرستید
۴. دوست شما در برنامه‌ی موبایلش: **افزودن از کلیپ‌بورد** (Import from clipboard)

| کار | نتیجه |
|:--|:--|
| **غیرفعال** | لینک آن نفر بی‌اثر می‌شود، بقیه کار می‌کنند |
| **لینک جدید** | UUID عوض می‌شود؛ لینک قبلی همان لحظه باطل است |
| **حذف** | کامل پاک می‌شود |

**لینک اشتراک (Subscription):** یک آدرس واحد که همه‌ی لینک‌ها را می‌دهد و
برنامه‌ی موبایل خودش به‌روزش می‌کند. این آدرس روی IP شبکه‌ی محلی شماست، پس
**فقط از داخل شبکه‌ی خودتان** باز می‌شود — برای گوشی خودتان عالی است، برای
دوستی که جای دیگری است نه؛ به او خود لینک `vless://` را بدهید.

> 🔑 بعد از هر تغییر (افزودن/حذف/لینک جدید)، اگر توکن کلودفلر را ذخیره کرده
> باشید پنل خودش Worker را دوباره آپلود می‌کند. اگر ذخیره نکرده‌اید، یک بار از
> صفحه‌ی **دیپلوی** دوباره دیپلوی کنید وگرنه لینک جدید روی Worker شناخته نمی‌شود.


---

<a id="daemon"></a>

## 🔁 اجرای دائمی و مدیریت (دستور `agp`)

یک منوی واحد برای همه‌ی کارها — نصب، آپدیت، روشن/خاموش، تغییر پورت و رمز،
پشتیبان‌گیری و… درست مثل `x-ui`. چون با پایتون نوشته شده روی **لینوکس، مک و
ویندوز** یکسان کار می‌کند، و منوی آن **انگلیسی** است تا در ترمینال درست و مرتب
دربیاید (متن راست‌چین داخل کادر ترمینال به‌هم می‌ریزد). **نصب و اجرا در یک خط** (بعد از کلون یا آنزیپ):

```bash
./agp.sh install     # لینوکس / مک — نصب می‌کند و می‌پرسد که «agp» را سراسری کند
```
```bat
agp.bat install     :: ویندوز
```

از آن به بعد، **فقط `agp` را تایپ کنید** — از هرجای ترمینال:

```bash
agp                 # منو باز می‌شود
```

منو:

```
+----------------------------------------------+
|  Aras-GP  -  Panel Manager   v2.1.5          |
|  0. Exit                                     |
|----------------------------------------------|
|  1. Install     2. Update                    |
|  3. Use a specific version   4. Uninstall    |
|----------------------------------------------|
|  5. Start  6. Stop  7. Restart               |
|  8. Status  9. Logs                          |
|----------------------------------------------|
|  10. Change panel port                       |
|  11. Change panel password                   |
|  12. LAN access (localhost / network)        |
|  13. View settings                           |
|----------------------------------------------|
|  14. Backup   15. Export backup to a path    |
|  16. Restore from backup   17. Reset         |
|----------------------------------------------|
|  18. Enable autostart  19. Disable autostart |
|  20. Open the panel in a browser             |
+----------------------------------------------+
  Panel     : running   http://127.0.0.1:8600
  Autostart : on
```

دستور سراسری `agp` را نصب خودش (گزینه‌ی ۱) می‌سازد و در اولین پوشه‌ی نوشتنی
از `PATH` می‌گذارد (روی روت‌شل به‌طور معمول `/usr/local/bin`، روی مک با هوم‌برو
`/opt/homebrew/bin`)، پس بدون ویرایش هیچ فایلی همان لحظه در دسترس است. هر گزینه
هم به‌صورت مستقیم قابل اجراست:

```bash
agp start | stop | restart | status | install | version
```

- **اتواستارت** روی لینوکس با systemd، روی مک با launchd و روی ویندوز با Task
  Scheduler ساخته می‌شود تا پنل با روشن‌شدن سیستم بالا بیاید (روی لینوکس به sudo
  نیاز دارد).
- **تغییر رمز پنل** رمز ورود به پنل را عوض می‌کند (نه رمز کاربران پروکسی).
- **حذف** پنل را متوقف و اتواستارت و محیط مجازی را پاک می‌کند؛ داده‌های شما
  (config.json، ca/، رمز، رله‌ها) فقط با تأیید جداگانه پاک می‌شوند.
- **پشتیبان‌گیری / خروجی / بازگردانی** یک آرشیو `tar.gz` از هرچه با کلون دوباره
  از دست می‌رود می‌سازد: `config.json`، `panel/data/` (رمز، توکن، رله‌ها،
  دوستان) و `ca/`. **این دقیقاً همان سه چیزی است که باید قبل از کلون مجدد بکاپ
  بگیرید.** فایل پشتیبان رمز و کلید دارد؛ با دسترسی ۰۶۰۰ ساخته و در `backups/`
  (که در گیت نادیده گرفته می‌شود) گذاشته می‌شود. «خروجی» همان را به مسیر دلخواه
  (مثلاً برای scp به سرور دیگر) می‌سازد، و «بازگردانی» از فهرست یا یک مسیر
  برمی‌گرداند.
- **دسترسی از شبکه (LAN)** پنل را روی کل شبکه باز می‌کند تا از گوشی هم برسید
  (با هشدار امنیتی و ری‌استارت خودکار).

> دستور `agp` خودش وابستگی ندارد و بدون venv هم اجرا می‌شود؛ برای همین حتی روی
> یک ماشین تازه که هنوز چیزی نصب نشده، گزینه‌ی «Install» کار می‌کند.

### روش قدیمی (اسکریپت پس‌زمینه)

اجرای `python -m panel` در ترمینال، رله را به آن ترمینال وابسته می‌کند: با بستن
پنجره تونل هم قطع می‌شود.

### لینوکس و مک

```bash
./scripts/aras-panel.sh start     # اجرای مستقل از ترمینال
./scripts/aras-panel.sh status    # آیا در حال اجراست؟
./scripts/aras-panel.sh logs      # دنبال‌کردن لاگ زنده
./scripts/aras-panel.sh restart
./scripts/aras-panel.sh stop
```

### ویندوز

```powershell
.\scripts\aras-panel.ps1 start
.\scripts\aras-panel.ps1 status
.\scripts\aras-panel.ps1 logs
.\scripts\aras-panel.ps1 restart
.\scripts\aras-panel.ps1 stop
```

<details>
<summary>اجرای خودکار با بوت سیستم (systemd)</summary>

```ini
# /etc/systemd/system/aras-panel.service
[Unit]
Description=Aras-GP Panel
After=network-online.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/home/YOUR_USER/Aras-GP
ExecStart=/home/YOUR_USER/Aras-GP/.venv/bin/python -m panel
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aras-panel
```
</details>

---

<a id="users"></a>

## 👥 کاربران و سهمیه

پروکسی به‌صورت پیش‌فرض **تک‌کاربره و بدون رمز** است — دقیقاً مثل حالت شخصی.
برای اشتراک با دیگران، صفحه‌ی **کاربران** → سوییچ احراز هویت را روشن کنید.

| قابلیت | جزئیات |
|:--|:--|
| 🔑 احراز هویت HTTP | `Proxy-Authorization: Basic` — RFC 7235 |
| 🔑 احراز هویت SOCKS5 | نام‌کاربری/رمز — RFC 1929 |
| 📊 شمارش حجم | جداگانه برای هر کاربر، آپلود و دانلود |
| ✂️ قطع خودکار | اتصال **زنده** در سقف سهمیه قطع می‌شود، نه فقط اتصال بعدی |
| 📅 تاریخ انقضا | برای هر کاربر جداگانه |
| 🔐 ذخیره‌ی رمز | PBKDF2-HMAC-SHA256 با ۱۲۰٬۰۰۰ دور — هرگز متن ساده |
| ⚡ اعمال فوری | تغییرات بدون ری‌استارت روی رله‌ی در حال اجرا اعمال می‌شوند |

### اشتراک در شبکه‌ی محلی

```jsonc
// در صفحه‌ی «ساخت کانفیگ» یا مستقیم در config.json
"lan_sharing": true     // پروکسی روی 0.0.0.0 گوش می‌دهد
```

> ⚠️ **همیشه با هم:** اگر `lan_sharing` را روشن می‌کنید حتماً احراز هویت را هم
> روشن کنید، وگرنه هر دستگاهی در شبکه بدون رمز از پروکسی شما استفاده می‌کند.
> پنل این هشدار را خودش نشان می‌دهد.

### ساختار ذخیره‌سازی

```jsonc
"proxy_auth": {
  "enabled": true,
  "realm": "Aras-GP",
  "users": [
    {
      "username": "ali",
      "salt": "…", "hash": "…", "iterations": 120000,
      "quota_bytes": 5368709120,        // ۵ گیگابایت — ۰ یعنی نامحدود
      "expires_at": "2027-03-01",       // خالی یعنی بدون انقضا
      "enabled": true,
      "up_bytes": 0, "down_bytes": 0,
      "note": "موبایل"
    }
  ]
}
```

---

<a id="failover"></a>

## 🔀 سوییچ خودکار بین رله‌ها

هر زنجیره‌ی کارکرده را می‌توانید در صفحه‌ی دیپلوی با یک نام **ذخیره** کنید.
دفعه‌ی بعد به‌جای دیپلوی دوباره، یک کلیک سوییچ می‌کنید.

با روشن‌کردن **«سوییچ خودکار»** در تنظیمات، اگر رله‌ی فعال بیش از آستانه
(پیش‌فرض ۶۰ ثانیه) پیوسته خطا بدهد، پنل خودش به رله‌ی بعدی می‌رود.

```mermaid
stateDiagram-v2
    [*] --> سالم
    سالم --> مشکوک: همه‌ی درخواست‌ها خطا
    مشکوک --> سالم: یک درخواست موفق
    مشکوک --> سوییچ: بیش از ۶۰ ثانیه
    سوییچ --> سالم: رله‌ی بعدی
```

**تشخیص کاملاً منفعل است.** از روی شمارنده‌های ترافیک واقعی خوانده می‌شود، نه
پینگ دوره‌ای — چون یک ابزار عبور از سانسور که هر چند ثانیه heartbeat می‌فرستد،
هم سهمیه‌ی Apps Script را هدر می‌دهد و هم یک الگوی قابل‌شناسایی روی شبکه می‌سازد.

محافظت در برابر نوسان:

- رله‌ی **بی‌کار** هرگز «خراب» حساب نمی‌شود — بدون ترافیک، بدون قضاوت
- اگر **اخیراً موفقیتی** بوده، سوییچ نمی‌کند (یعنی یک سایت خراب کل تونل را جابه‌جا نمی‌کند)
- حداقل فاصله بین دو سوییچ: ۹۰ ثانیه
- با کمتر از دو رله‌ی ذخیره‌شده، اصلاً کاری نمی‌کند

---

<a id="backup"></a>

## 💾 پشتیبان‌گیری

در صفحه‌ی **تنظیمات**:

| دکمه | شامل |
|:--|:--|
| 📥 **پشتیبان کامل** | کانفیگ، کاربران، رله‌ها، پروفایل‌ها، تنظیمات |
| 👁️ **بدون رمزها** | همان فایل بدون `auth_key` و بدون هش رمز کاربران |
| 🔄 **بازگردانی** | از فایل پشتیبان |
| 🗑️ **پاک‌کردن همه** | با تأیید تایپی `DELETE` — رمز پنل حفظ می‌شود |

> 🔒 توکن Cloudflare **هرگز** داخل فایل پشتیبان نوشته نمی‌شود، حتی در نسخه‌ی کامل.

```bash
# پشتیبان‌گیری از خط فرمان
curl -b cookies.txt http://127.0.0.1:8600/api/backup/export -o backup.json
curl -b cookies.txt "http://127.0.0.1:8600/api/backup/export?secrets=0" -o backup-safe.json
```

---

<a id="config-ref"></a>

## 🧩 مرجع کامل config.json

<details>
<summary><b>کلیک برای دیدن همه‌ی کلیدها</b></summary>

### هویت و مسیر رله

| کلید | نوع | پیش‌فرض | توضیح |
|:--|:--|:--|:--|
| `mode` | str | `apps_script` | ثابت — همیشه همین |
| `auth_key` | str | — | رمز مشترک با `Code.gs`. حداقل ۱۶ کاراکتر |
| `script_id` | str \| list | — | یک یا چند Deployment ID |
| `front_domain` | str | `www.google.com` | دامنه‌ای که در SNI دیده می‌شود |
| `google_ip` | str | `216.239.38.120` | IP فرانت. با `python main.py --scan` سریع‌ترین را پیدا کنید |
| `parallel_relay` | int | `1` | تعداد اسکریپت هم‌زمان. نباید از تعداد Deployment ID بیشتر باشد |

### شنود محلی

| کلید | نوع | پیش‌فرض | توضیح |
|:--|:--|:--|:--|
| `listen_host` | str | `127.0.0.1` | `0.0.0.0` یعنی باز روی شبکه |
| `listen_port` | int | `8085` | پورت پروکسی HTTP |
| `socks5_enabled` | bool | `true` | فعال‌بودن شنونده‌ی SOCKS5 |
| `socks5_port` | int | `1080` | باید با `listen_port` فرق کند |
| `lan_sharing` | bool | `true` | اگر `listen_host` روی لوکال باشد، به `0.0.0.0` تغییرش می‌دهد |
| `verify_ssl` | bool | `true` | بررسی گواهی TLS. خاموش‌کردن فقط برای عیب‌یابی |
| `log_level` | str | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

### کارایی و تایم‌اوت

| کلید | نوع | پیش‌فرض | توضیح |
|:--|:--|:--|:--|
| `relay_timeout` | int | `25` | ثانیه — مهلت پاسخ رله |
| `tls_connect_timeout` | int | `15` | ثانیه — مهلت handshake |
| `tcp_connect_timeout` | int | `10` | ثانیه — مهلت اتصال TCP |
| `max_response_body_bytes` | int | `209715200` | ۲۰۰ مگابایت |

### دانلود تکه‌ای

| کلید | نوع | پیش‌فرض | توضیح |
|:--|:--|:--|:--|
| `chunked_download_extensions` | list | `[".zip", ".mp4", …]` | پسوندهای مشمول |
| `chunked_download_min_size` | int | `5242880` | حداقل ۵ مگابایت |
| `chunked_download_chunk_size` | int | `524288` | ۵۱۲ کیلوبایت هر تکه |
| `chunked_download_max_parallel` | int | `8` | تکه‌های هم‌زمان |
| `chunked_download_max_chunks` | int | `256` | حداکثر تعداد تکه |

### سیاست میزبان‌ها

| کلید | نوع | توضیح |
|:--|:--|:--|
| `block_hosts` | list | با ۴۰۳ رد می‌شوند |
| `bypass_hosts` | list | مستقیم، بدون MITM و بدون رله |
| `direct_google_exclude` | list | سرویس‌های گوگل که باید از رله بروند |
| `direct_google_allow` | list | سرویس‌های گوگل که مستقیم می‌روند |
| `youtube_via_relay` | bool | یوتیوب از رله (دور زدن SafeSearch اجباری) |
| `hosts` | dict | نگاشت DNS دستی: `{"example.com": "1.2.3.4"}` |

> الگوی با نقطه‌ی ابتدایی (مثل `.local`) همه‌ی زیردامنه‌ها را می‌گیرد.

### کش سیستمی

هر miss یک رفت‌وبرگشت کامل به Apps Script است — حدود دو ثانیه و یک واحد از
سهمیه‌ی روزانه. کش دو لایه دارد: یک LRU در حافظه و یک لایه‌ی **روی دیسک** که
بعد از ری‌استارت هم می‌ماند (اندازه‌گیری‌شده: ۴٫۵ ثانیه → ۲۱ میلی‌ثانیه برای
اولین درخواست بعد از ری‌استارت، و ۴ میلی‌ثانیه وقتی در حافظه باشد).

| کلید | نوع | پیش‌فرض | توضیح |
|:--|:--|:--|:--|
| `cache_enabled` | bool | `true` | خاموش‌کردن کل لایه‌ی دیسک |
| `cache_memory_mb` | int | `50` | سقف کش حافظه |
| `cache_disk_mb` | int | `512` | سقف کش دیسک (۰ = خاموش) |
| `cache_dir` | text | خودکار | پیش‌فرض: `~/Library/Caches/Aras-GP` روی مک |
| `dns_cache_ttl` | int | `300` | ثانیه‌ی نگه‌داری پاسخ DNS برای مسیر مستقیم |

فقط فایل‌های ایستا (تصویر، CSS، JS، فونت) و فقط `GET` بدون کوکی یا
`Authorization` کش می‌شوند. هدر `Set-Cookie` **قبل از ذخیره حذف می‌شود**، پس
کوکی هیچ‌وقت از کش به کاربر بعدی داده نمی‌شود؛ پاسخ‌های `no-store` و `private`
اصلاً ذخیره نمی‌شوند.

### اپلیکیشن‌ها، نه فقط سایت‌ها

وقتی پروکسی را روی کل سیستم ست می‌کنید، برنامه‌ها هم از آن رد می‌شوند و سه
رفتارشان با مرورگر فرق دارد — هر سه پشتیبانی می‌شود:

- **CONNECT به IP، درخواست گواهی برای یک نام دیگر.** گواهی حالا داخل خود
  handshake و از روی **SNI واقعی** انتخاب می‌شود، نه از روی مقصد CONNECT.
- **گواهی pin‌شده یا پروتکل غیر‌TLS روی ۴۴۳.** اولین ردِ handshake ثبت می‌شود
  و آن میزبان از آن به بعد **دست‌نخورده تونل می‌شود**. اگر مسیر مستقیم هم جواب
  ندهد (یعنی مقصد فیلتر است) یادداشت پاک می‌شود و دوباره از رله می‌رود.
- **WebSocket و هر `Upgrade` دیگر.** رله نمی‌تواند `101` را حمل کند؛ این
  اتصال‌ها مستقیم تونل می‌شوند تا چت، نوتیفیکیشن و کانال‌های realtime کار کنند.

### بخش‌های افزوده‌ی پنل

```jsonc
"proxy_auth": {                       // احراز هویت کاربران
  "enabled": false,
  "realm": "Aras-GP",
  "users": []
}
```
</details>

---

<a id="api-ref"></a>

## 🔌 مرجع API

همه‌ی مسیرها پشت لاگین‌اند و همه‌ی `POST`ها به توکن CSRF نیاز دارند
(هدر `X-CSRF-Token` یا فیلد `csrf_token`).

<details>
<summary><b>کلیک برای دیدن همه‌ی ۵۲ مسیر</b></summary>

### صفحات

| متد | مسیر | کار |
|:--|:--|:--|
| `GET` | `/` | داشبورد |
| `GET` | `/status` | وضعیت و لاگ |
| `GET` | `/deploy` | دیپلوی |
| `GET,POST` | `/config` | ساخت کانفیگ |
| `GET` | `/users` | کاربران |
| `GET,POST` | `/settings` | تنظیمات |
| `GET` | `/guide` | راهنما |
| `GET,POST` | `/login` · `/setup` | ورود و راه‌اندازی اولیه |
| `POST` | `/logout` | خروج |

### چرخه‌ی رله

| متد | مسیر | کار |
|:--|:--|:--|
| `POST` | `/api/relay/start` | روشن‌کردن |
| `POST` | `/api/relay/stop` | خاموش‌کردن |
| `POST` | `/api/relay/restart` | راه‌اندازی مجدد |
| `POST` | `/api/relay/test` | یک درخواست واقعی از مسیر رله |

### داده‌ی زنده

| متد | مسیر | کار |
|:--|:--|:--|
| `GET` | `/api/stats` | آمار + وضعیت + سری زمانی نمودار |
| `GET` | `/api/status` | فقط وضعیت |
| `GET` | `/api/logs` | لاگ رله. پارامتر `level` و `limit` |
| `POST` | `/api/logs/clear` | پاک‌کردن بافر لاگ |

### کانفیگ و پروفایل

| متد | مسیر | کار |
|:--|:--|:--|
| `POST` | `/api/config/auth-key` | تولید کلید. `{"save":"1"}` برای ذخیره |
| `GET` | `/api/config/download` | دانلود `config.json` |
| `POST` | `/api/profiles/save` · `load` · `delete` | مدیریت پروفایل |

### رله‌های ذخیره‌شده

| متد | مسیر | کار |
|:--|:--|:--|
| `GET` | `/api/relays` | فهرست (کلید احراز هویت نمایش داده نمی‌شود) |
| `POST` | `/api/relays/save` | ذخیره‌ی کانفیگ فعلی با یک نام |
| `POST` | `/api/relays/apply` | سوییچ به یک رله |
| `POST` | `/api/relays/delete` | حذف |

### دیپلوی

| متد | مسیر | کار |
|:--|:--|:--|
| `POST` | `/api/cloudflare/verify` | بررسی توکن + فهرست حساب‌ها |
| `POST` | `/api/cloudflare/deploy` | دیپلوی کامل Worker |
| `POST` | `/api/cloudflare/forget-token` | حذف توکن ذخیره‌شده |
| `POST` | `/api/gas/code` | تولید `Code.gs` |
| `POST` | `/api/gas/deployment-id` | ثبت Deployment ID |

### کاربران

| متد | مسیر | کار |
|:--|:--|:--|
| `GET` | `/api/users` | فهرست با مصرف زنده |
| `POST` | `/api/users/add` · `update` · `delete` | مدیریت |
| `POST` | `/api/users/auth-toggle` | روشن/خاموش احراز هویت |
| `POST` | `/api/users/reset-usage` | صفر کردن مصرف |
| `POST` | `/api/users/disconnect` | قطع اتصال‌های باز |

### دوستان (VLESS)

| متد | مسیر | کار |
|:--|:--|:--|
| `POST` | `/api/friends/add` | افزودن دوست (UUID ساخته می‌شود) |
| `POST` | `/api/friends/update` | تغییر نام یا فعال/غیرفعال |
| `POST` | `/api/friends/rotate` | UUID تازه — لینک قبلی باطل می‌شود |
| `POST` | `/api/friends/delete` | حذف |
| `POST` | `/api/friends/path` | تغییر مسیر WebSocket |
| `GET` | `/sub/<token>` | لینک اشتراک (بدون لاگین، با توکن محافظت می‌شود) |

### پشتیبان و گواهی

| متد | مسیر | کار |
|:--|:--|:--|
| `GET` | `/api/backup/export` | دانلود. `?secrets=0` برای نسخه‌ی بی‌رمز |
| `POST` | `/api/backup/import` | بازگردانی (multipart) |
| `POST` | `/api/reset` | پاک‌کردن همه. نیاز به `{"confirm":"DELETE"}` |
| `POST` | `/api/ca/install` | نصب گواهی |
| `GET` | `/api/ca/status` · `download` | وضعیت و دانلود گواهی |

### نمونه

```bash
# لاگین و نگه‌داشتن کوکی
curl -c c.txt -X POST -d "password=YOUR_PANEL_PASSWORD" http://127.0.0.1:8600/login

# استخراج توکن CSRF
TOK=$(curl -s -b c.txt http://127.0.0.1:8600/ | grep -o 'csrf-token" content="[^"]*"' | cut -d'"' -f3)

# روشن‌کردن رله
curl -b c.txt -X POST -H "X-CSRF-Token: $TOK" http://127.0.0.1:8600/api/relay/start

# آمار زنده
curl -b c.txt http://127.0.0.1:8600/api/stats | python3 -m json.tool
```
</details>

---

<a id="scripts-ref"></a>

## 📜 مرجع اسکریپت‌ها

### `scripts/aras-panel.sh` — اجرای پس‌زمینه (لینوکس/مک)

```bash
./scripts/aras-panel.sh start | stop | restart | status | logs
```

| موضوع | جزئیات |
|:--|:--|
| PID | `panel/data/panel.pid` |
| لاگ | `panel/data/panel.log` |
| پایتون | اول `.venv/bin/python`، بعد `python3` سیستم |
| جدا‌شدن | با `setsid` + `nohup` — پروسه PPID=1 می‌گیرد |

### `scripts/aras-panel.ps1` — اجرای پس‌زمینه (ویندوز)

```powershell
.\scripts\aras-panel.ps1 start | stop | restart | status | logs
```

از `pythonw.exe` استفاده می‌کند تا پنجره‌ی کنسول باز نشود.


---

<a id="troubleshooting"></a>

## 🩺 عیب‌یابی

| نشانه | علت معمول | راه حل |
|:--|:--|:--|
| `ERR_CERT_AUTHORITY_INVALID` | گواهی در System keychain نیست یا مرورگر restart نشده | وضعیت → نصب گواهی + دستور `sudo`، بعد `⌘Q` روی مرورگر |
| خطای گواهی با اینکه پنل می‌گوید «نصب شده» | **CA قدیمی**: پوشه‌ی `ca/` دوباره ساخته شده (کلون تازه یا ریست) ولی CAهای قبلی با همان نام `Aras-GP` هنوز در کیچین مانده‌اند؛ مرورگر ممکن است یکی از آن‌ها را برای بررسی امضا انتخاب کند | `python main.py --uninstall-cert --stale-only` بعد `python main.py --install-cert` و `⌘Q` روی مرورگر. کارت «وضعیت» حالا این CAها را با اثر انگشتشان فهرست می‌کند |
| رله بعد از مدتی از کار می‌افتد | معمولاً سهمیه‌ی روزانه‌ی Apps Script (هر درخواست یک UrlFetch است) | لاگ حالا دلیل دقیق را می‌نویسد؛ برای ظرفیت بیشتر چند Deployment ID (ترجیحاً روی اکانت‌های گوگل جدا) در `script_id` بگذارید |
| گوشی به پروکسی وصل نمی‌شود | `lan_sharing` روشن است ولی رله فقط روی ۱۲۷.۰.۰.۱ گوش می‌داد | برطرف شد — رله‌ای که از پنل استارت می‌شود هم `lan_sharing` را رعایت می‌کند. آدرسی که در «وضعیت» می‌بینید همان چیزی است که واقعاً bind شده |
| «تست اتصال» ناموفق | Deployment ID اشتباه، یا `Who has access` ≠ Anyone، یا `auth_key` با `Code.gs` یکی نیست | کد را دوباره تولید و جای‌گذاری کنید و deployment تازه بسازید |
| اولین درخواست ۳ تا ۵ ثانیه | Apps Script باید container را بیدار کند | چند Deployment ID + `parallel_relay: 2` |
| با بستن ترمینال قطع می‌شود | پنل وابسته به ترمینال اجرا شده | `./scripts/aras-panel.sh start` |
| `Address already in use` | نمونه‌ی دیگری در حال اجراست | `./scripts/aras-panel.sh stop` یا پورت را عوض کنید |
| رمز پنل فراموش شده | — | `panel/data/panel.json` را پاک کنید؛ کانفیگ و کاربران می‌مانند |
| `zsh: command not found: python` | روی مک `python` وجود ندارد | `python3` بزنید یا venv را فعال کنید |
| `ModuleNotFoundError: No module named 'flask'` | با پایتون سیستمی اجرا شده، نه venv پروژه؛ یا وابستگی‌ها نصب نشده‌اند | `run.bat panel` (ویندوز) یا `./run.sh panel` — خودش venv می‌سازد و همه‌چیز را نصب می‌کند. دستی: `pip install -r requirements.txt`. حالا خود برنامه هم دقیقاً همین را می‌گوید و دیگر traceback خام نمی‌دهد |
| روی ویندوز پنل بی‌صدا بالا نمی‌آید | `aras-panel.ps1` به پایتون سیستمی افتاده که Flask ندارد | اول `run.bat` را اجرا کنید تا `.venv` ساخته شود؛ اسکریپت حالا اول سراغ venv می‌رود و اگر مجبور شد از پایتون سیستمی استفاده کند هشدار می‌دهد |
| خطای `UnicodeEncodeError` در لاگ ویندوز | خروجی به فایل ریدایرکت شده و code page ویندوز فارسی را نمی‌پذیرد | برطرف شد — هر دو ورودی برنامه، stdout/stderr را روی UTF-8 تنظیم می‌کنند |
| SOCKS5 بالا نمی‌آید ولی HTTP کار می‌کند | پورت ۱۰۸۰ اشغال است | پنل در صفحه‌ی وضعیت هشدار می‌دهد؛ پورت را عوض کنید |
| کاربر با رمز درست وصل نمی‌شود | سهمیه تمام شده یا تاریخ انقضا گذشته | صفحه‌ی کاربران → ستون وضعیت |

| مشکل موقع دیپلوی Worker | چه‌کار کنید |
|:--|:--|
| `Account ID باید ۳۲ کاراکتر هگز باشد` | Account ID را از داشبورد کلودفلر کپی کنید، یا **بررسی توکن** را بزنید تا خودکار پر شود |
| `این حساب هنوز زیردامنه workers.dev ندارد` | یک بار از داشبورد کلودفلر بخش Workers را باز کنید تا زیردامنه ساخته شود، بعد دوباره تلاش کنید |
| توکن را گم کردید | توکن فقط یک بار نمایش داده می‌شود؛ توکن جدید بسازید |
| `Authentication error` از کلودفلر | دسترسی‌های توکن ناقص است — باید `Workers Scripts: Edit` و `Account Settings: Read` داشته باشد |

| مشکل موقع Apps Script | چه‌کار کنید |
|:--|:--|
| صفحه‌ی ورود گوگل به‌جای پاسخ | `Who has access` روی **Anyone** نیست. Deployment را ویرایش یا از نو بسازید |
| `Authorization is required` | همان مشکل بالا |
| `Sorry, unable to open the file` | Deployment ID اشتباه است یا آن deployment پاک شده |
| `Service invoked too many times for one day` | سهمیه‌ی روزانه تمام شد. تا نیمه‌شب وقت آمریکا (Pacific) صبر کنید یا Deployment ID دوم روی اکانت گوگل دیگر اضافه کنید |
| `Exceeded maximum execution time` | یک پاسخ خیلی بزرگ. `max_response_body_bytes` را کم کنید |
| کد را عوض کردید ولی اثر ندارد | بعد از هر تغییر باید **New deployment** بسازید؛ ویرایش deployment قبلی کافی نیست |

| مشکل VLESS / دوستان | چه‌کار کنید |
|:--|:--|
| صفحه‌ی دوستان می‌گوید Worker نداری | اول قدم ۲ (دیپلوی Worker) را کامل کنید |
| دوست وصل می‌شود ولی اینترنت ندارد | Worker با UUID جدید آپلود نشده. یک بار دوباره دیپلوی کنید |
| `not configured` از Worker | هیچ UUIDای روی Worker بایند نشده؛ بعد از افزودن دوست دوباره دیپلوی کنید |
| لینک اشتراک روی گوشی دوست باز نمی‌شود | طبیعی است — آن آدرس فقط داخل شبکه‌ی خودتان کار می‌کند. خود لینک `vless://` را بفرستید |
| Worker ناگهان مسدود شد | شرایط استفاده‌ی کلودفلر؛ همان ریسکی که بالا نوشته شده |

| مشکل نصب و اجرا | چه‌کار کنید |
|:--|:--|
| ویندوز: `git` ندارم | `powershell -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/ArasTey/Aras-GP/main/scripts/get-aras.ps1 \| iex"` — یا از GitHub دکمه‌ی Code → Download ZIP |
| ویندوز: PowerShell اجازه نمی‌دهد | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| ویندوز: `python` شناخته نمی‌شود | موقع نصب پایتون تیک **Add python.exe to PATH** را بزنید، یا `py` را امتحان کنید |
| لینوکس: `ensurepip is not available` | `sudo apt install python3-venv` |
| رله بالا می‌آید ولی هیچ سایتی باز نمی‌شود | پروکسی مرورگر روی `127.0.0.1:8085` تنظیم نشده، یا گواهی CA نصب نیست |
| بعد از کلون دوباره، همه‌چیز خراب شد | `ca/`, `config.json` و `panel/data/` در git نیستند و با کلون تازه پاک می‌شوند. **قبل از کلون مجدد از این سه بکاپ بگیرید** |

**اولین جایی که باید نگاه کنید:** وضعیت → **لاگ زنده‌ی رله**.
لاگ فقط در حافظه است (۴۰۰ سطر آخر)، روی دیسک نوشته نمی‌شود، و هرگز `auth_key`
یا رمز کاربران را نشان نمی‌دهد.

```bash
# لاگ اسکریپت پس‌زمینه
./scripts/aras-panel.sh logs
```

---

<a id="security"></a>

## 🔐 امنیت و شفافیت شبکه

این ابزار برای عبور از سانسور ساخته شده، پس پنل **عمداً** فاقد این موارد است:

| ❌ ندارد | چرا |
|:--|:--|
| تله‌متری یا phone-home | هیچ IP، آمار یا هویتی به هیچ سرور مرکزی نمی‌رود |
| کیل‌سوییچ از راه دور | هیچ کانالی برای غیرفعال‌کردن رله‌ی شما وجود ندارد |
| کد مبهم‌سازی‌شده | ابزاری که کاربرش نتواند حسابرسی‌اش کند، بدتر از نبودنش است |
| CDN خارجی | یک درخواست به CDN، خودِ اجرای این ابزار را لو می‌دهد |
| سرور لایسنس | قفل لایسنس کاملاً آفلاین است |

**کل مقصدهای خروجی این پروسه:**

1. `api.cloudflare.com` — فقط هنگام بررسی توکن یا دیپلوی Worker
2. هرچه خودِ موتور رله با آن حرف می‌زند (Apps Script و Worker **خود شما**)

همین فهرست در صفحه‌ی تنظیمات پنل هم به کاربر نشان داده می‌شود.

### تدابیر پیاده‌شده

| تدبیر | جزئیات |
|:--|:--|
| 🔑 لاگین | PBKDF2-HMAC-SHA256، ۱۲۰٬۰۰۰ دور |
| 🍪 نشست | `HttpOnly` + `SameSite=Lax`، انقضای ۱۲ ساعت |
| 🛡️ CSRF | روی همه‌ی درخواست‌های غیر-GET |
| ⏱️ Rate limit | لاگین ۸/۵دقیقه · دیپلوی ۶/۵دقیقه · تست‌ها ۱۰/دقیقه · ریست ۳/۱۰دقیقه |
| 📜 CSP | `default-src 'self'`، بدون `unsafe-inline` — هر بلاک inline یک nonce یکبارمصرف دارد |
| 📁 مجوز فایل | `config.json` و `panel/data/*` با `0600`، پوشه با `0700`، نوشتن اتمیک |
| 🙈 اسرار | توکن کلودفلر پیش‌فرض ذخیره نمی‌شود؛ هیچ رمزی در لاگ یا پاسخ API ظاهر نمی‌شود |

> ⚠️ پنل پیش‌فرض روی `127.0.0.1` گوش می‌دهد. اگر `ARAS_PANEL_HOST` را عوض کردید،
> حتماً پشت VPN یا reverse proxy با TLS قرارش دهید — پنل `auth_key` و توکن
> کلودفلر را در اختیار دارد. پنل هنگام bind روی آدرس غیر-loopback هشدار می‌دهد.

---

<a id="architecture"></a>

## 🏗️ معماری

```
Aras-GP/
├── panel/                  لایه‌ی مدیریت
│   ├── app.py              Flask و همه‌ی ۵۲ مسیر
│   ├── relay_manager.py    پل بین Flask و موتور (ترد + event loop اختصاصی)
│   ├── failover.py         تشخیص منفعل خرابی و سوییچ
│   ├── configgen.py        ساخت و اعتبارسنجی config.json
│   ├── users.py            مدیریت کاربران پروکسی
│   ├── cloudflare.py       دیپلوی واقعی Worker
│   ├── gasgen.py           تولید Code.gs
│   ├── security.py         لاگین، CSRF، rate limit، هدرها
│   ├── store.py            ذخیره‌سازی اتمیک ۰۶۰۰، رله‌ها، بکاپ
│   ├── licensing.py        قفل آفلاین Ed25519
│   ├── templates/          قالب‌های فارسی راست‌چین
│   └── static/             CSS، JS، نشان — همگی محلی
├── engine/                 موتور رله
│   ├── domain_fronter.py   Domain Fronting، چرخش SNI، HTTP/2
│   ├── proxy_server.py     پروکسی HTTP و SOCKS5
│   ├── account_manager.py  احراز هویت و شمارش per-user
│   └── mitm.py             تولید گواهی محلی
├── scripts/                اجرای پس‌زمینه
├── deploy/                 کد Worker و Apps Script
└── docs/screenshots/       تصاویر این README
```

### چرا ترد، نه subprocess؟

موتور یک برنامه‌ی asyncio است و Flask همگام؛ این دو نمی‌توانند یک event loop
مشترک داشته باشند. پنل یک ترد جداگانه می‌سازد، داخلش یک event loop تازه
راه می‌اندازد و `ProxyServer` را همان‌جا می‌سازد — و یک ارجاع به آن شیء نگه می‌دارد.

دلیلش این است که داشبورد باید **واقعاً زنده** باشد: آمار مستقیماً از شیء در حال
اجرا خوانده می‌شود، نه از روی pars کردن لاگ. هر فراخوانی که به وضعیت رله دست
می‌زند با `run_coroutine_threadsafe` به همان event loop برگردانده می‌شود، پس
دیکشنری‌های داخلی فقط از تردی خوانده می‌شوند که آن‌ها را تغییر می‌دهد.

**هزینه‌اش (صادقانه):** پنل و رله در یک پروسه‌اند، پس یک کرش مدیریت‌نشده هر دو را
می‌برد. در عوض داشبورد واقعاً زنده است.

### بهینه‌سازی مصرف

| مورد | تدبیر |
|:--|:--|
| تردها | فقط دو ترد: رله و نمونه‌بردار. فیل‌اوور و ذخیره‌ی سهمیه روی همان تیک موجود سوارند |
| پولینگ مرورگر | وقتی تب مخفی است **کاملاً متوقف** می‌شود؛ رله خاموش = کندتر |
| درخواست‌ها | `/api/stats` یک بار snapshot می‌گیرد، نه دو بار |
| فیل‌اوور | صفر درخواست اضافه — از ترافیک واقعی می‌خواند |
| لاگ | فقط در حافظه، ۴۰۰ سطر، بدون نوشتن روی دیسک |

---

<a id="dev"></a>

## 🧪 توسعه و تست

```bash
# تحلیل ایستا
.venv/bin/pip install pyflakes
.venv/bin/python -m pyflakes panel/*.py engine/*.py

# بررسی سینتکس JS
node --check panel/static/js/aras.js

# بررسی اسکریپت‌های shell
bash -n scripts/*.sh

# اجرای پنل روی داده‌ی موقت (بدون دست‌زدن به داده‌ی واقعی)
ARAS_DATA_DIR=/tmp/test DFT_CONFIG=/tmp/test/config.json \
  ARAS_PANEL_PORT=8601 python -m panel
```

---

<a id="license"></a>

## 📄 لایسنس

| بخش | پروانه |
|:--|:--|
| `panel/` | **اختصاصی** — [`panel/LICENSE`](panel/LICENSE) |
| `engine/`, `deploy/`, `main.py`, `setup.py` | **MIT** — [`LICENSE`](LICENSE) |

پروانه‌ی پنل اجرای خصوصی نامحدود و حسابرسی امنیتی را کاملاً آزاد می‌گذارد؛ ولی
ری‌برندسازی و فروش مجدد بدون اجازه‌ی کتبی مجاز نیست.


---

<a id="disclaimer"></a>

## ⚠️ سلب مسئولیت

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

The panel is fully offline: no external CDN, no telemetry, no phone-home, no
remote kill switch. Its only outbound call is `api.cloudflare.com` during a
deploy. A censorship-circumvention tool must not become the surveillance
chokepoint it exists to avoid.

```bash
git clone https://github.com/ArasTey/Aras-GP.git && cd Aras-GP
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m panel          # → http://127.0.0.1:8600
```

Licensing: `panel/` is proprietary ([`panel/LICENSE`](panel/LICENSE)) and
permits unlimited private use and security auditing but not rebranding or
resale. The relay engine under `engine/` derives from MIT-licensed code; the
full licence text is kept in [`LICENSE`](LICENSE) as MIT requires.
