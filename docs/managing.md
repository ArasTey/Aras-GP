# مدیریت پنل و اجرای دائمی

[← بازگشت به README](../README.md)


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
