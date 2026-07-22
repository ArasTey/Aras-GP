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
| [🚀 راه‌اندازی](#setup) | [🔁 اجرای دائمی](#daemon) | [👥 کاربران](#users) |
| [🤖 ChatGPT و IP ثابت](#ai) | [🔀 سوییچ خودکار](#failover) | [💾 پشتیبان‌گیری](#backup) |
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
    B -.->|"فقط میزبان‌های AI"| F["🖧 VPS شما"]
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
| ⚙️ **تنظیمات** | خروجی AI و IP ثابت، پشتیبان‌گیری، سوییچ خودکار، رمز پنل |
| 📖 **راهنما** | آموزش گام‌به‌گام داخل پنل با چک‌لیست پیشرفت واقعی شما |

---

<a id="gallery"></a>

## 🖼️ نمای پنل

<details open>
<summary><b>📊 داشبورد</b> — آمار زنده، نمودار سرعت، سلامت مسیر</summary>
<br><img src="docs/screenshots/dashboard.png" alt="داشبورد">
</details>

<details>
<summary><b>👥 کاربران</b> — سهمیه، انقضا، وضعیت لحظه‌ای، قطع اتصال</summary>
<br><img src="docs/screenshots/users.png" alt="کاربران">
</details>

<details>
<summary><b>➕ ساخت کاربر</b> — تولید رمز، سهمیه، تاریخ انقضا</summary>
<br><img src="docs/screenshots/modal-user.png" alt="مودال کاربر">
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
<summary><b>💾 پروفایل‌ها</b> — چند کانفیگ ذخیره‌شده</summary>
<br><img src="docs/screenshots/modal-profiles.png" alt="پروفایل‌ها">
</details>

<details>
<summary><b>⚙️ تنظیمات</b> — خروجی AI، پشتیبان‌گیری، سوییچ خودکار</summary>
<br><img src="docs/screenshots/settings.png" alt="تنظیمات">
</details>

<details>
<summary><b>📖 راهنما</b> — آموزش داخل پنل با چک‌لیست پیشرفت</summary>
<br><img src="docs/screenshots/guide.png" alt="راهنما">
</details>

<details>
<summary><b>🔐 ورود</b> و <b>📱 موبایل</b> — کاملاً ریسپانسیو</summary>
<br>
<p align="center">
<img src="docs/screenshots/login.png" width="60%" alt="ورود"><br><br>
<img src="docs/screenshots/mobile.png" width="30%" alt="موبایل">
<img src="docs/screenshots/mobile-menu.png" width="30%" alt="منوی موبایل">
</p>
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
| یک VPS ارزان | فقط اگر ChatGPT یا IP ثابت می‌خواهید | ⬜ |
| یک دامنه | فقط برای روش امنِ خروجی AI (جایگزین: Cloudflare Tunnel) | ⬜ |

### 🐧 لینوکس

```bash
# ۱. کلون
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

# ۲. محیط مجازی
python3 -m venv .venv
source .venv/bin/activate

# ۳. وابستگی‌ها
pip install -r requirements.txt -r panel/requirements.txt

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
pip install -r requirements.txt -r panel/requirements.txt

python -m panel
```

> **چرا `python3`؟** روی macOS دستور `python` اصلاً وجود ندارد. اگر `python -m venv`
> بزنید venv ساخته نمی‌شود و pip بسته‌ها را روی پایتون سیستم نصب می‌کند.
> بعد از `source .venv/bin/activate` دستور `python` داخل venv در دسترس است.

### 🪟 ویندوز

```powershell
git clone https://github.com/ArasTey/Aras-GP.git
cd Aras-GP

py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r panel\requirements.txt

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

## 🚀 راه‌اندازی در شش قدم

> صفحه‌ی **راهنما** داخل پنل همین مراحل را با چک‌لیست پیشرفت واقعی شما نشان می‌دهد.

```mermaid
flowchart TD
    S1["1️⃣ کلید احراز هویت"] --> S2["2️⃣ دیپلوی Worker"]
    S2 --> S3["3️⃣ Apps Script"]
    S3 --> S4["4️⃣ نصب گواهی CA"]
    S4 --> S5["5️⃣ روشن‌کردن رله"]
    S5 --> S6["6️⃣ تنظیم مرورگر"]
    style S1 fill:#7C5CFF,color:#fff
    style S2 fill:#F38020,color:#fff
    style S3 fill:#4285F4,color:#fff
    style S4 fill:#f4536f,color:#fff
    style S5 fill:#2F83F6,color:#fff
    style S6 fill:#22c58c,color:#fff
```

### ۱️⃣ کلید احراز هویت

صفحه‌ی **دیپلوی** → دکمه‌ی 🔄 کنار کادر `auth_key`.
این رمز مشترک بین رله‌ی شما و Apps Script است و همان‌جا ذخیره می‌شود.

### ۲️⃣ Cloudflare Worker

دکمه‌ی **«ساخت توکن با دسترسی آماده»** صفحه‌ی کلودفلر را با دسترسی‌های زیر
از پیش تیک‌خورده باز می‌کند:

| دسترسی | چرا |
|:--|:--|
| `Account → Workers Scripts → Edit` | آپلود اسکریپت و فعال‌سازی workers.dev |
| `Account → Account Settings → Read` | فهرست‌کردن حساب‌ها تا Account ID خودکار پر شود |

فقط **Continue to summary** → **Create Token**.

> ⚠️ توکن **فقط یک بار** نمایش داده می‌شود. همان لحظه کپی کنید.

بعد در پنل: توکن را پیست کنید → **بررسی توکن** (Account ID خودکار پر می‌شود) →
**دیپلوی Worker**.

پنل این پنج کار را انجام می‌دهد:

```
1. GET  /user/tokens/verify                                   بررسی توکن
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

---

<a id="daemon"></a>

## 🔁 اجرای دائمی

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

<a id="ai"></a>

## 🤖 ChatGPT و IP ثابت

ترافیکی که از Cloudflare Workers خارج می‌شود با IP رنج کلودفلر به مقصد می‌رسد و
OpenAI آن رنج را مسدود کرده:

```
Unable to load site
Please try again later. If you are using a VPN, try turning it off.
[IP:2a06:98c0:3600::103 | Ray ID:a1f3b1fdce195358]
```

این **داخل رله قابل حل نیست**. راهش یک خروجی دیگر است: یک VPS که شما کنترلش
می‌کنید. پنل دو روش می‌دهد.

### 🛡️ روش امن — از مسیر گوگل (پیشنهادی)

```mermaid
flowchart LR
    A["🖥️ مرورگر"] --> B["⚙️ رله"]
    B -->|"SNI=google.com"| C["📄 Apps Script"]
    C --> D["☁️ Worker"]
    D -->|"HTTPS"| E["🖧 VPS شما"]
    E --> F["🤖 OpenAI"]
    style A fill:#7C5CFF,color:#fff
    style B fill:#2F83F6,color:#fff
    style C fill:#4285F4,color:#fff
    style D fill:#F38020,color:#fff
    style E fill:#22c58c,color:#fff
    style F fill:#10a37f,color:#fff
```

ISP همچنان **فقط گوگل** می‌بیند و مقصد IP ثابت VPS شما را.

```bash
# روی VPS — با دامنه‌ی خودتان (Caddy گواهی Let's Encrypt را خودکار می‌گیرد)
curl -fsSL https://raw.githubusercontent.com/ArasTey/Aras-GP/main/scripts/install-forwarder.sh -o f.sh
sudo bash f.sh --domain fwd.example.com

# یا بدون دامنه — با Cloudflare Tunnel
sudo bash f.sh --tunnel
```

آخر کار **آدرس** و **کلید** را می‌دهد → تنظیمات پنل → «AI از مسیر گوگل» →
تست → ذخیره → **بعد یک بار Worker را دوباره دیپلوی کنید** (آدرس و کلید باید
روی خود Worker بایند شوند).

### ⚡ روش سریع — مستقیم

```mermaid
flowchart LR
    A["🖥️ مرورگر"] --> B["⚙️ رله"]
    B -->|"SOCKS5 مستقیم"| C["🖧 VPS شما"]
    C --> D["🤖 OpenAI"]
    style A fill:#7C5CFF,color:#fff
    style B fill:#2F83F6,color:#fff
    style C fill:#22c58c,color:#fff
    style D fill:#10a37f,color:#fff
```

دو هاپ کمتر و سریع‌تر، ولی اتصال به VPS برای ISP قابل دیدن است و
Domain Fronting ندارد.

```bash
curl -fsSL https://raw.githubusercontent.com/ArasTey/Aras-GP/main/scripts/install-exit-node.sh | sudo bash
```

### مقایسه

| | 🛡️ از مسیر گوگل | ⚡ مستقیم |
|:--|:--:|:--:|
| Domain Fronting حفظ می‌شود | ✅ | ❌ |
| ISP چه می‌بیند | فقط گوگل | اتصال به IP خارجی |
| IP ثابت برای مقصد | ✅ | ✅ |
| سرعت | متوسط | سریع‌تر |
| نیاز به دامنه یا Tunnel | ✅ | ❌ |

> 🔄 هر دو روش **فقط** دامنه‌های فهرست‌شده را از VPS رد می‌کنند؛ بقیه از رله.
> اگر VPS خاموش شود، آن میزبان‌ها خودکار به رله برمی‌گردند — قطعی نمی‌شود.

**دامنه‌های پیش‌فرض:** `openai.com` · `chatgpt.com` · `oaistatic.com` ·
`oaiusercontent.com` · `claude.ai` · `anthropic.com` · `gemini.google.com` ·
`perplexity.ai` · `x.ai` · `grok.com`

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
| `forwarder_hosts` | list | از مسیر Worker → فورواردر VPS |
| `direct_google_exclude` | list | سرویس‌های گوگل که باید از رله بروند |
| `direct_google_allow` | list | سرویس‌های گوگل که مستقیم می‌روند |
| `youtube_via_relay` | bool | یوتیوب از رله (دور زدن SafeSearch اجباری) |
| `hosts` | dict | نگاشت DNS دستی: `{"example.com": "1.2.3.4"}` |

> الگوی با نقطه‌ی ابتدایی (مثل `.local`) همه‌ی زیردامنه‌ها را می‌گیرد.

### بخش‌های افزوده‌ی پنل

```jsonc
"proxy_auth": {                       // احراز هویت کاربران
  "enabled": false,
  "realm": "Aras-GP",
  "users": []
},
"upstream_proxy": {                   // خروجی مستقیم SOCKS5
  "enabled": false,
  "url": "socks5://user:pass@1.2.3.4:1080",
  "route_all": false,                 // true = کل ترافیک، نه فقط لیست
  "hosts": ["openai.com", "chatgpt.com"]
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

### خروجی AI

| متد | مسیر | کار |
|:--|:--|:--|
| `POST` | `/api/forwarder/save` · `test` | روش امن (از مسیر گوگل) |
| `POST` | `/api/upstream/save` · `test` | روش مستقیم (SOCKS5) |

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

### `scripts/install-forwarder.sh` — خروجی امن روی VPS

```bash
sudo bash install-forwarder.sh [گزینه‌ها]
```

| گزینه | پیش‌فرض | کار |
|:--|:--|:--|
| `--domain X` | — | TLS با Caddy + Let's Encrypt |
| `--tunnel` | — | TLS با Cloudflare Tunnel (بدون دامنه) |
| `--port N` | `8787` | پورت داخلی فورواردر |
| `--auth-key X` | تصادفی ۴۸ کاراکتری | کلید مشترک با Worker |
| `--uninstall` | — | حذف کامل |

نصب می‌کند: یک فورواردر پایتون (فقط کتابخانه‌ی استاندارد) + سرویس systemd با
sandbox (`DynamicUser`, `ProtectSystem=strict`, `MemoryMax=256M`).

### `scripts/install-exit-node.sh` — خروجی مستقیم روی VPS

```bash
sudo bash install-exit-node.sh [گزینه‌ها]
```

| گزینه | پیش‌فرض | کار |
|:--|:--|:--|
| `--port N` | `1080` | پورت SOCKS5 |
| `--user X` | `aras` | نام کاربری |
| `--password X` | تصادفی ۲۴ کاراکتری | رمز |
| `--bind X` | `0.0.0.0` | آدرس شنود |
| `--uninstall` | — | حذف کامل |

> 🔒 دسترسی به شبکه‌ی داخلی (RFC1918 و loopback) به‌صورت پیش‌فرض **بلاک** است تا
> VPS شما به‌خاطر port scan تعلیق نشود. برای شبکه‌ی خانگی:
> `ARAS_ALLOW_PRIVATE=1`.

### `main.py` — موتور رله بدون پنل

```bash
python main.py                      # اجرا با config.json
python main.py -c other.json        # کانفیگ دیگر
python main.py -p 9090              # تغییر پورت
python main.py --scan               # یافتن سریع‌ترین IP گوگل
python main.py --install-cert       # نصب گواهی CA
python main.py --uninstall-cert     # حذف گواهی
python main.py --no-cert-check      # رد کردن بررسی گواهی
python main.py --log-level DEBUG
```

### `panel/licensing.py` — قفل لایسنس آفلاین

```bash
python -m panel.licensing keygen --out vendor-key.pem
python -m panel.licensing sign --key vendor-key.pem --licensee "نام" --days 365
python -m panel.licensing verify --file panel/data/license.key
```

بررسی کاملاً محلی است — یک امضای Ed25519، **بدون هیچ تماس شبکه‌ای**.

---

<a id="troubleshooting"></a>

## 🩺 عیب‌یابی

| نشانه | علت معمول | راه حل |
|:--|:--|:--|
| `ERR_CERT_AUTHORITY_INVALID` | گواهی در System keychain نیست یا مرورگر restart نشده | وضعیت → نصب گواهی + دستور `sudo`، بعد `⌘Q` روی مرورگر |
| «تست اتصال» ناموفق | Deployment ID اشتباه، یا `Who has access` ≠ Anyone، یا `auth_key` با `Code.gs` یکی نیست | کد را دوباره تولید و جای‌گذاری کنید و deployment تازه بسازید |
| اولین درخواست ۳ تا ۵ ثانیه | Apps Script باید container را بیدار کند | چند Deployment ID + `parallel_relay: 2` |
| ChatGPT باز نمی‌شود، بقیه کار می‌کنند | IP خروجی کلودفلر بلاک شده | [بخش AI](#ai) |
| با بستن ترمینال قطع می‌شود | پنل وابسته به ترمینال اجرا شده | `./scripts/aras-panel.sh start` |
| `Address already in use` | نمونه‌ی دیگری در حال اجراست | `./scripts/aras-panel.sh stop` یا پورت را عوض کنید |
| رمز پنل فراموش شده | — | `panel/data/panel.json` را پاک کنید؛ کانفیگ و کاربران می‌مانند |
| `zsh: command not found: python` | روی مک `python` وجود ندارد | `python3` بزنید یا venv را فعال کنید |
| SOCKS5 بالا نمی‌آید ولی HTTP کار می‌کند | پورت ۱۰۸۰ اشغال است | پنل در صفحه‌ی وضعیت هشدار می‌دهد؛ پورت را عوض کنید |
| کاربر با رمز درست وصل نمی‌شود | سهمیه تمام شده یا تاریخ انقضا گذشته | صفحه‌ی کاربران → ستون وضعیت |

**اولین جایی که باید نگاه کنید:** وضعیت → **لاگ زنده‌ی رله**.
لاگ فقط در حافظه است (۴۰۰ سطر آخر)، روی دیسک نوشته نمی‌شود، و هرگز `auth_key`
یا رمز کاربران را نشان نمی‌دهد.

```bash
# لاگ اسکریپت پس‌زمینه
./scripts/aras-panel.sh logs

# لاگ فورواردر روی VPS
journalctl -u aras-forwarder -f
journalctl -u aras-exit -f
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
│   ├── upstream_proxy.py   کلاینت SOCKS5 برای خروجی VPS
│   └── mitm.py             تولید گواهی محلی
├── scripts/                اجرای پس‌زمینه + نصب روی VPS
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

موتور رله از کد متن‌باز [denuitt1/mhr-cfw](https://github.com/denuitt1/mhr-cfw)
مشتق شده که تحت **MIT** منتشر شده. متن کامل آن پروانه در [`LICENSE`](LICENSE)
نگه داشته شده، همان‌طور که MIT الزام می‌کند.

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
