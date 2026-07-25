# مرجع API پنل

[← بازگشت به README](../README.md)


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
