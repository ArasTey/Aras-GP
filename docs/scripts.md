# مرجع اسکریپت‌ها

[← بازگشت به README](../README.md)


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
