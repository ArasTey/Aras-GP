# نصب روی هر سیستم‌عامل

[← بازگشت به README](../README.md)


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
