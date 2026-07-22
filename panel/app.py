"""Aras-GP Panel — Flask application.

Route map
---------
Pages      /setup /login /  /deploy /config /users /settings /status
JSON API   /api/stats /api/status /api/series /api/logs
           /api/relay/{start,stop,restart,test}
           /api/cloudflare/{verify,accounts,deploy}
           /api/gas/{code,deployment-id}
           /api/users/*  /api/profiles/*  /api/ca/install

Outbound network calls made by this process, exhaustively:
  • ``api.cloudflare.com`` — only while a deploy or token check is running.
  • whatever the relay itself talks to (the operator's own GAS/Worker).
Nothing else. No telemetry, no analytics, no update check, no licence server.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import requests

from flask import (
    Flask, Response, flash, jsonify, redirect, render_template, request,
    send_file, url_for,
)

from . import (
    __version__, cloudflare, configgen, failover, gasgen, licensing, paths,
    security, store, users,
)
from .relay_manager import macos_trust_command, manager, refresh_ca_status
from upstream_proxy import DEFAULT_AI_HOSTS, UpstreamError, UpstreamProxy  # engine/

log = logging.getLogger("panel")


def _json_body() -> dict:
    """Request body as a dict of strings.

    Form fields are always strings, but a JSON client can send numbers, lists
    or objects where a name is expected. Coercing here means every validator
    downstream can assume ``str`` and reject bad input with a real message,
    instead of raising ``AttributeError`` on ``.strip()`` and returning a 500.
    ``None`` is preserved, because several endpoints use it to mean
    "leave this field unchanged".
    """
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        raw = request.form.to_dict()
    return {
        key: (None if value is None else
              value if isinstance(value, str) else str(value))
        for key, value in (raw or {}).items()
    }


def _int_arg(value, default: int, low: int, high: int) -> int:
    """Clamp a user-supplied number, falling back instead of raising.

    Query strings and form fields are attacker-controlled; a bare ``int()``
    on them turns a typo into a 500.
    """
    try:
        return max(low, min(high, int(str(value).strip())))
    except (TypeError, ValueError):
        return default


_ENV_LINE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")


def _invalid_env_line(content: str) -> str | None:
    """Return the first line that is not ``KEY=VALUE``, a comment, or blank.

    The forwarder ``.env`` is written outside the panel's data directory and is
    consumed by docker-compose, so a malformed paste (or a stray API call
    sending a non-string body) would leave the operator with a file that
    silently breaks their deployment.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not _ENV_LINE_RE.match(stripped):
            return stripped
    return None


def _safe_next(target: str | None, fallback: str) -> str:
    """Only allow same-origin relative redirects.

    ``//evil.example.com`` and ``/\\evil.example.com`` both start with "/" but
    are protocol-relative URLs that leave the site, so a plain startswith("/")
    check is an open redirect.
    """
    if not target or not target.startswith("/"):
        return fallback
    if target.startswith("//") or target.startswith("/\\"):
        return fallback
    return target


def _probe_upstream(proxy) -> dict:
    """Ask api.ipify.org, through the exit, what IP the world sees.

    Runs in a throwaway event loop so it never touches the relay's loop, and
    is only ever called from the explicit "test" button.
    """
    import asyncio

    async def run():
        started = time.monotonic()
        reader, writer = await proxy.connect("api.ipify.org", 80)
        try:
            writer.write(b"GET / HTTP/1.1\r\nHost: api.ipify.org\r\n"
                         b"User-Agent: Aras-GP\r\nConnection: close\r\n\r\n")
            await writer.drain()
            raw = await asyncio.wait_for(reader.read(4096), timeout=15)
        finally:
            writer.close()
        elapsed = (time.monotonic() - started) * 1000
        body = raw.split(b"\r\n\r\n", 1)[-1].decode("utf-8", "replace").strip()
        return {"ok": True, "ip": body[:64], "ms": round(elapsed, 1)}

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(asyncio.wait_for(run(), timeout=25))
    except UpstreamError as exc:
        return {"ok": False, "error": str(exc)}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "خروجی در زمان مقرر پاسخ نداد."}
    except Exception as exc:
        return {"ok": False, "error": f"اتصال ناموفق بود: {exc}"}
    finally:
        loop.close()


def _ok(**payload):
    return jsonify({"ok": True, **payload})


def _fail(message: str, status: int = 400, **payload):
    return jsonify({"ok": False, "error": message, **payload}), status


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    paths.ensure_dirs()
    security.register(app)

    # Flush per-user byte counters to config.json once a minute while the
    # relay runs, so quotas survive a kill -9 as well as a clean shutdown.
    manager.sample_hook = users.persist_live_usage

    def _switch_to_next_relay(reason: str) -> bool:
        """Move to the next saved relay. Called by the failover monitor.

        Returns True when a switch actually happened, so the monitor knows
        whether to keep watching or give up until traffic changes.
        """
        state = store.load()
        target = failover.pick_next(store.list_relays(), state.get("active_relay"))
        if target is None:
            log.info("Failover wanted (%s) but no alternative relay is saved.", reason)
            return False

        if store.apply_relay(target["id"]) is None:
            return False
        log.warning("Failover: switching to relay %r — %s", target["name"], reason)
        store.add_history({"kind": "failover", "ok": True,
                           "script_name": target["name"], "error": reason})
        config = store.load_config()
        if config is not None and manager.running:
            manager.restart(config)
        return True

    manager.switch_hook = _switch_to_next_relay

    _settings = store.load()["settings"]
    manager.failover.enabled = bool(_settings.get("auto_failover", False))
    manager.failover.grace = float(_settings.get("failover_seconds", 60))

    @app.context_processor
    def _globals():
        return {
            "panel_version": __version__,
            "relay_running": manager.running,
            "nav_active": request.endpoint,
            "license_status": licensing.check(),
        }

    # ── first run ─────────────────────────────────────────────────────

    @app.route("/setup", methods=["GET", "POST"])
    @security.rate_limit("setup", limit=10, window=300)
    def setup():
        if security.admin_configured():
            return redirect(url_for("login_view"))
        if request.method == "POST":
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            if len(password) < 10:
                flash("رمز عبور پنل باید حداقل ۱۰ کاراکتر باشد.", "error")
            elif password != confirm:
                flash("دو رمز وارد شده یکسان نیستند.", "error")
            else:
                security.set_admin_password(password)
                security.login(security.client_ip())
                flash("پنل آماده است. خوش آمدید.", "success")
                return redirect(url_for("dashboard"))
        return render_template("setup.html")

    # ── auth ──────────────────────────────────────────────────────────

    @app.route("/login", methods=["GET", "POST"])
    @security.rate_limit("login", limit=8, window=300)
    def login_view():
        if not security.admin_configured():
            return redirect(url_for("setup"))
        if request.method == "POST":
            if security.check_admin_password(request.form.get("password", "")):
                security.limiter.reset("login")
                security.login(security.client_ip())
                return redirect(_safe_next(request.args.get("next"),
                                           url_for("dashboard")))
            log.warning("Failed panel login from %s", security.client_ip())
            flash("رمز عبور نادرست است.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout_view():
        security.logout()
        return redirect(url_for("login_view"))

    # ── pages ─────────────────────────────────────────────────────────

    @app.route("/")
    @security.login_required
    def dashboard():
        return render_template("dashboard.html", status=manager.status(),
                               chart_window=store.load()["settings"]["chart_window"])

    @app.route("/deploy")
    @security.login_required
    def deploy_page():
        state = store.load()
        config = store.load_config() or {}
        return render_template(
            "deploy.html",
            cf=state["cloudflare"],
            token_saved=bool(state["cloudflare"].get("token")),
            token_hint=security.redact(state["cloudflare"].get("token")),
            gas=state["gas"],
            gas_steps=gasgen.STEPS,
            auth_key_set=bool(config.get("auth_key")),
            auth_key=config.get("auth_key", ""),
            cf_token_url=cloudflare.TOKEN_TEMPLATE_URL,
            history=state["deploy_history"][:12],
        )

    @app.route("/config")
    @security.login_required
    def config_page():
        config = store.load_config()
        is_new = config is None
        if is_new:
            config = configgen.defaults()
        script_id = config.get("script_ids") or config.get("script_id") or ""
        script_ids = script_id if isinstance(script_id, list) else [script_id]
        return render_template(
            "config.html",
            cfg=config,
            is_new=is_new,
            script_ids="\n".join(s for s in script_ids if s),
            hosts_text="\n".join(f"{k} = {v}" for k, v in (config.get("hosts") or {}).items()),
            log_levels=configgen.LOG_LEVELS,
            profiles=store.list_profiles(),
        )

    @app.route("/users")
    @security.login_required
    def users_page():
        config = store.load_config()
        return render_template(
            "users.html",
            has_config=config is not None,
            auth_enabled=bool((config or {}).get("proxy_auth", {}).get("enabled")),
            user_list=users.list_users() if config else [],
            settings=users.client_settings("") if config else {},
            lan_sharing=bool((config or {}).get("lan_sharing")),
        )

    @app.route("/settings")
    @security.login_required
    def settings_page():
        state = store.load()
        config = store.load_config() or {}
        forwarder_env = ""
        if os.path.exists(paths.FORWARDER_ENV):
            with open(paths.FORWARDER_ENV, encoding="utf-8") as handle:
                forwarder_env = handle.read()
        return render_template(
            "settings.html",
            cfg=config,
            settings=state["settings"],
            cf=state["cloudflare"],
            forwarder_env=forwarder_env,
            upstream=(config.get("upstream_proxy") or {}),
            forwarder=state["forwarder"],
            forwarder_hosts=(config.get("forwarder_hosts") or []),
            default_ai_hosts=list(DEFAULT_AI_HOSTS),
            license=licensing.check(),
        )

    @app.route("/status")
    @security.login_required
    def status_page():
        return render_template("status.html", status=manager.status(),
                               ca_command=macos_trust_command())

    # ── relay lifecycle ───────────────────────────────────────────────

    @app.post("/api/relay/start")
    @security.login_required
    def api_relay_start():
        config = store.load_config()
        if config is None:
            return _fail("هنوز کانفیگی ساخته نشده است.")
        try:
            configgen.validate(config)
        except configgen.ConfigError as exc:
            return _fail(str(exc))
        ok, message = manager.start(config)
        return (_ok(message=message) if ok else _fail(message))

    @app.post("/api/relay/stop")
    @security.login_required
    def api_relay_stop():
        users.persist_live_usage()
        ok, message = manager.stop()
        return _ok(message=message) if ok else _fail(message)

    @app.post("/api/relay/restart")
    @security.login_required
    def api_relay_restart():
        config = store.load_config()
        if config is None:
            return _fail("هنوز کانفیگی ساخته نشده است.")
        users.persist_live_usage()
        ok, message = manager.restart(config)
        return _ok(message=message) if ok else _fail(message)

    @app.post("/api/relay/test")
    @security.login_required
    @security.rate_limit("relay_test", limit=12, window=60)
    def api_relay_test():
        result = manager.test_relay()
        return jsonify(result)

    # ── live data ─────────────────────────────────────────────────────

    @app.get("/api/stats")
    @security.login_required
    def api_stats():
        stats = manager.stats()
        points = store.load()["settings"].get("chart_window", 120)
        return jsonify({
            "ok": True,
            "status": manager.status(),
            "per_site": stats["per_site"][:40],
            "blacklisted_scripts": stats["blacklisted_scripts"],
            "sni_rotation": stats["sni_rotation"],
            "series": manager.series(_int_arg(request.args.get("points"), points, 30, 720)),
            "accounts": stats["accounts"],
            "account_totals": stats["account_totals"],
        })

    @app.get("/api/status")
    @security.login_required
    def api_status():
        return _ok(status=manager.status())

    @app.get("/api/logs")
    @security.login_required
    def api_logs():
        return _ok(lines=manager.logs.tail(
            limit=_int_arg(request.args.get("limit"), 200, 1, 400),
            level=request.args.get("level") or None,
        ))

    @app.post("/api/logs/clear")
    @security.login_required
    def api_logs_clear():
        manager.logs.clear()
        return _ok()

    # ── config builder ────────────────────────────────────────────────

    @app.post("/api/config/auth-key")
    @security.login_required
    def api_auth_key():
        """Generate a key and, if asked, persist it into config.json.

        The deploy page needs a usable auth_key before Code.gs can be
        rendered, so it can save one without a round trip to the config form.
        """
        body = _json_body()
        key = (body.get("auth_key") or "").strip() or configgen.generate_auth_key()

        if str(body.get("save", "")).lower() in ("1", "true", "on"):
            if len(key) < configgen.MIN_AUTH_KEY_LENGTH:
                return _fail(
                    f"کلید باید حداقل {configgen.MIN_AUTH_KEY_LENGTH} کاراکتر باشد."
                )
            config = store.load_config() or configgen.defaults()
            config["auth_key"] = key
            store.save_config(configgen.strip_internal(config))
            note = ("ذخیره شد. یادتان باشد Code.gs را دوباره تولید و در "
                    "Apps Script جای‌گذاری کنید.")
            if manager.running:
                note += " برای اعمال، رله را ری‌استارت کنید."
            return _ok(auth_key=key, saved=True, message=note)

        return _ok(auth_key=key, saved=False)

    @app.post("/config")
    @security.login_required
    def config_save():
        form = request.form.to_dict()
        form["_form_submitted"] = "1"
        base = store.load_config() or configgen.defaults()
        try:
            config = configgen.build(form, base=base)
        except configgen.ConfigError as exc:
            flash(str(exc), "error")
            return redirect(url_for("config_page"))

        for warning in configgen.warnings_of(config):
            flash(warning, "warn")
        store.save_config(configgen.strip_internal(config))
        flash("کانفیگ ذخیره شد (config.json).", "success")

        if manager.running and form.get("restart_after_save"):
            ok, message = manager.restart(store.load_config())
            flash(message, "success" if ok else "error")
        elif manager.running:
            flash("برای اعمال تغییرات، رله را دوباره راه‌اندازی کنید.", "warn")
        return redirect(url_for("config_page"))

    @app.get("/api/config/download")
    @security.login_required
    def api_config_download():
        if not os.path.exists(paths.CONFIG_FILE):
            return _fail("فایل config.json وجود ندارد.", 404)
        return send_file(paths.CONFIG_FILE, as_attachment=True,
                         download_name="config.json", mimetype="application/json")

    @app.post("/api/profiles/save")
    @security.login_required
    def api_profile_save():
        name = (_json_body().get("name") or "").strip()
        config = store.load_config()
        if config is None:
            return _fail("کانفیگی برای ذخیره وجود ندارد.")
        try:
            store.save_profile(name, config)
        except ValueError:
            return _fail("نام پروفایل نامعتبر است.")
        return _ok(profiles=store.list_profiles())

    @app.post("/api/profiles/load")
    @security.login_required
    def api_profile_load():
        name = (_json_body().get("name") or "").strip()
        config = store.load_profile(name)
        if config is None:
            return _fail("پروفایل پیدا نشد.", 404)
        store.save_config(config)
        return _ok(message="پروفایل بارگذاری شد.")

    @app.post("/api/profiles/delete")
    @security.login_required
    def api_profile_delete():
        name = (_json_body().get("name") or "").strip()
        if not store.delete_profile(name):
            return _fail("حذف پروفایل ناموفق بود.")
        return _ok(profiles=store.list_profiles())

    # ── saved relays ──────────────────────────────────────────────────

    @app.get("/api/relays")
    @security.login_required
    def api_relays_list():
        return _ok(relays=store.list_relays())

    @app.post("/api/relays/save")
    @security.login_required
    def api_relays_save():
        body = _json_body()
        config = store.load_config()
        if config is None:
            return _fail("کانفیگی برای ذخیره وجود ندارد.")
        try:
            configgen.validate(config)
        except configgen.ConfigError as exc:
            return _fail(f"این رله هنوز کامل نیست: {exc}")

        name = (body.get("name") or "").strip()
        if not name:
            return _fail("یک نام برای رله وارد کنید.")
        if len(name) > 60:
            return _fail("نام رله بیش از حد بلند است.")

        record = store.relay_from_config(
            config, name,
            {**store.load()["cloudflare"], "note": (body.get("note") or "").strip()},
        )
        store.save_relay(record)
        return _ok(relays=store.list_relays(), message="رله ذخیره شد.")

    @app.post("/api/relays/apply")
    @security.login_required
    def api_relays_apply():
        relay = store.apply_relay((_json_body().get("id") or "").strip())
        if relay is None:
            return _fail("رله پیدا نشد.", 404)
        message = "رله فعال شد."
        if manager.running:
            ok, restart_message = manager.restart(store.load_config())
            message = f"رله فعال شد و بازراه‌اندازی {'شد' if ok else 'نشد'}: {restart_message}"
        return _ok(relays=store.list_relays(), message=message)

    @app.post("/api/relays/delete")
    @security.login_required
    def api_relays_delete():
        if not store.delete_relay((_json_body().get("id") or "").strip()):
            return _fail("رله پیدا نشد.", 404)
        return _ok(relays=store.list_relays(), message="رله حذف شد.")

    # ── fronted forwarder (AI over Google) ────────────────────────────

    @app.post("/api/forwarder/save")
    @security.login_required
    def api_forwarder_save():
        """Route chosen hosts through the Worker → your VPS, still fronted.

        Writes ``forwarder_hosts`` into config.json (the engine tags those
        requests with ``f:1`` so the Worker forwards them) and keeps the URL
        and key for the next Worker deploy, which must carry both as bindings.
        """
        body = _json_body()
        config = store.load_config()
        if config is None:
            return _fail("ابتدا کانفیگ رله را بسازید.")

        enabled = str(body.get("enabled", "")).lower() in ("1", "true", "on")
        url = (body.get("url") or "").strip().rstrip("/")
        key = (body.get("auth_key") or "").strip()
        hosts = configgen.as_list(body.get("hosts")) or list(DEFAULT_AI_HOSTS)

        if enabled:
            if not url.startswith("https://"):
                return _fail(
                    "آدرس فورواردر باید با https:// شروع شود — "
                    "Worker به آدرس بدون TLS فوروارد نمی‌کند."
                )
            if len(key) < 32:
                return _fail("کلید فورواردر باید حداقل ۳۲ کاراکتر باشد.")

        config["forwarder_hosts"] = hosts if enabled else []
        store.save_config(config)
        store.update(forwarder={"url": url, "auth_key": key, "enabled": enabled})

        message = "ذخیره شد."
        if enabled:
            message += (" برای اعمال، Worker را دوباره دیپلوی کنید تا "
                        "آدرس و کلید فورواردر روی آن bind شود.")
        if manager.running:
            ok, detail = manager.restart(store.load_config())
            message += f" رله بازراه‌اندازی {'شد' if ok else 'نشد'}."
        return _ok(message=message, hosts=hosts)

    @app.post("/api/forwarder/test")
    @security.login_required
    @security.rate_limit("fwd_test", limit=10, window=60)
    def api_forwarder_test():
        """One real request to the forwarder, only when the button is pressed."""
        body = _json_body()
        saved = store.load()["forwarder"]
        url = (body.get("url") or saved.get("url") or "").strip().rstrip("/")
        key = (body.get("auth_key") or saved.get("auth_key") or "").strip()
        if not url:
            return _fail("آدرس فورواردر وارد نشده است.")
        if not url.startswith("https://"):
            return _fail("آدرس فورواردر باید https باشد.")

        payload = json.dumps({"u": "https://api.ipify.org", "m": "GET",
                              "h": {"User-Agent": "Aras-GP"}, "r": True})
        try:
            response = requests.post(
                url, data=payload, timeout=25,
                headers={"content-type": "application/json",
                         "x-upstream-auth": key},
            )
        except requests.RequestException as exc:
            return _fail(f"اتصال به فورواردر برقرار نشد: {type(exc).__name__}", 502)

        if response.status_code == 403:
            return _fail("کلید فورواردر اشتباه است.", 502)
        if response.status_code != 200:
            return _fail(f"فورواردر کد {response.status_code} برگرداند.", 502)
        try:
            data = response.json()
        except ValueError:
            return _fail("پاسخ فورواردر JSON نبود.", 502)
        if "e" in data:
            return _fail(f"فورواردر خطا داد: {data['e']}", 502)

        ip = ""
        if data.get("b"):
            import base64 as _b64
            try:
                ip = _b64.b64decode(data["b"]).decode("utf-8", "replace").strip()
            except Exception:
                ip = ""
        return _ok(ip=ip[:64], status=data.get("s"))

    # ── upstream exit (AI hosts / static IP) ──────────────────────────

    @app.post("/api/upstream/save")
    @security.login_required
    def api_upstream_save():
        body = _json_body()
        config = store.load_config()
        if config is None:
            return _fail("ابتدا کانفیگ رله را بسازید.")

        url = (body.get("url") or "").strip()
        enabled = str(body.get("enabled", "")).lower() in ("1", "true", "on")
        route_all = str(body.get("route_all", "")).lower() in ("1", "true", "on")
        hosts = configgen.as_list(body.get("hosts"))

        if enabled:
            if not url:
                return _fail("آدرس خروجی را وارد کنید.")
            try:
                UpstreamProxy(url)
            except ValueError as exc:
                return _fail(str(exc))

        config["upstream_proxy"] = {
            "enabled": enabled,
            "url": url,
            "route_all": route_all,
            "hosts": hosts or list(DEFAULT_AI_HOSTS),
        }
        store.save_config(config)
        message = "ذخیره شد."
        if manager.running:
            ok, detail = manager.restart(store.load_config())
            message += f" رله بازراه‌اندازی {'شد' if ok else 'نشد'} — {detail}"
        return _ok(message=message,
                   hosts=config["upstream_proxy"]["hosts"])

    @app.post("/api/upstream/test")
    @security.login_required
    @security.rate_limit("upstream_test", limit=10, window=60)
    def api_upstream_test():
        """Open one real connection through the exit and report the IP it has.

        A single request, only when the operator presses the button — the
        panel never probes this endpoint on a timer.
        """
        url = (_json_body().get("url") or "").strip()
        if not url:
            config = store.load_config() or {}
            url = (config.get("upstream_proxy") or {}).get("url", "")
        if not url:
            return _fail("آدرس خروجی وارد نشده است.")
        try:
            proxy = UpstreamProxy(url)
        except ValueError as exc:
            return _fail(str(exc))

        result = _probe_upstream(proxy)
        if result.get("ok"):
            return _ok(**result)
        return _fail(result.get("error", "اتصال ناموفق بود."), 502)

    # ── backup / restore / reset ──────────────────────────────────────

    @app.get("/api/backup/export")
    @security.login_required
    def api_backup_export():
        include = request.args.get("secrets", "1") != "0"
        payload = store.export_backup(include_secrets=include)
        payload["panel_version"] = __version__
        stamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = "" if include else "-بدون-رمز"
        body = json.dumps(payload, indent=2, ensure_ascii=False)
        return Response(
            body,
            mimetype="application/json",
            headers={
                "Content-Disposition":
                    f'attachment; filename="aras-gp-backup-{stamp}{suffix}.json"',
            },
        )

    @app.post("/api/backup/import")
    @security.login_required
    @security.rate_limit("backup_import", limit=5, window=300)
    def api_backup_import():
        upload = request.files.get("backup")
        if upload is None:
            return _fail("فایلی انتخاب نشده است.")
        try:
            payload = json.loads(upload.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _fail("فایل پشتیبان قابل خواندن نیست.")
        try:
            restored = store.import_backup(payload)
        except ValueError as exc:
            return _fail(str(exc))
        log.info("Backup restored: %s", ", ".join(restored))
        return _ok(restored=restored,
                   message="بازگردانی شد: " + "، ".join(restored))

    @app.post("/api/reset")
    @security.login_required
    @security.rate_limit("reset", limit=3, window=600)
    def api_reset():
        # Destructive and irreversible, so it needs an explicit typed
        # confirmation rather than a single click.
        if (_json_body().get("confirm") or "").strip() != "DELETE":
            return _fail("برای تأیید، عبارت DELETE را وارد کنید.")
        if manager.running:
            manager.stop()
        store.factory_reset(keep_admin=True)
        log.warning("Factory reset performed from %s", security.client_ip())
        return _ok(message="همه‌ی داده‌ها پاک شد. رمز پنل دست‌نخورده ماند.")

    # ── Cloudflare deploy ─────────────────────────────────────────────

    def _cf_token(body: dict) -> str:
        token = (body.get("api_token") or "").strip()
        if token:
            return token
        saved = store.load()["cloudflare"].get("token") or ""
        if not saved:
            raise ValueError("توکن API کلودفلر وارد نشده است.")
        return saved

    @app.post("/api/cloudflare/verify")
    @security.login_required
    @security.rate_limit("cf_verify", limit=10, window=60)
    def api_cf_verify():
        body = _json_body()
        try:
            token = _cf_token(body)
            info = cloudflare.verify_token(token)
            accounts = cloudflare.list_accounts(token)
        except ValueError as exc:
            return _fail(str(exc))
        except cloudflare.CloudflareError as exc:
            return _fail(exc.message, 502, details=exc.errors)
        return _ok(status=info.get("status", ""), accounts=accounts)

    @app.post("/api/cloudflare/deploy")
    @security.login_required
    @security.rate_limit("cf_deploy", limit=6, window=300)
    def api_cf_deploy():
        body = _json_body()
        account_id = (body.get("account_id") or "").strip()
        script_name = (body.get("script_name") or "aras-relay").strip()
        upstream = (body.get("upstream_forwarder_url") or "").strip()
        remember = str(body.get("remember_token", "")).lower() in ("1", "true", "on")

        try:
            token = _cf_token(body)
            result = cloudflare.deploy(
                token, account_id, script_name, upstream,
                store.load()["forwarder"].get("auth_key", ""),
            )
        except ValueError as exc:
            return _fail(str(exc))
        except cloudflare.CloudflareError as exc:
            store.add_history({"kind": "cloudflare", "ok": False,
                               "script_name": script_name, "error": exc.message})
            return _fail(exc.message, 502, details=exc.errors)

        # Persist only what the operator agreed to keep; the token is stored
        # solely on an explicit opt-in and only in a 0600 file.
        store.update(cloudflare={
            "account_id": account_id,
            "script_name": result["script_name"],
            "token": token if remember else "",
            "workers_subdomain": result["subdomain"],
            "worker_url": result["worker_url"],
            "upstream_forwarder_url": upstream,
        })
        store.add_history({"kind": "cloudflare", "ok": True,
                           "script_name": result["script_name"],
                           "worker_url": result["worker_url"]})
        log.info("Worker deployed: %s", result["worker_url"])
        return _ok(**result)

    @app.post("/api/cloudflare/forget-token")
    @security.login_required
    def api_cf_forget():
        store.update(cloudflare={"token": ""})
        return _ok(message="توکن ذخیره‌شده حذف شد.")

    # ── Apps Script ───────────────────────────────────────────────────

    @app.post("/api/gas/code")
    @security.login_required
    def api_gas_code():
        body = _json_body()
        config = store.load_config() or {}
        state = store.load()
        auth_key = (body.get("auth_key") or config.get("auth_key") or "").strip()
        worker_url = (body.get("worker_url")
                      or state["cloudflare"].get("worker_url") or "").strip()
        try:
            code = gasgen.render(auth_key, worker_url)
        except gasgen.GasError as exc:
            return _fail(str(exc))
        store.update(gas={"last_generated_at": time.time()})
        return _ok(code=code, worker_url=worker_url)

    @app.post("/api/gas/deployment-id")
    @security.login_required
    def api_gas_deployment():
        body = _json_body()
        try:
            deployment_id = gasgen.normalize_deployment_id(body.get("deployment_id"))
        except gasgen.GasError as exc:
            return _fail(str(exc))

        config = store.load_config()
        if config is None:
            return _fail("ابتدا کانفیگ را بسازید.")

        existing = config.get("script_ids") or config.get("script_id") or []
        ids = existing if isinstance(existing, list) else ([existing] if existing else [])
        ids = [i for i in ids if i and i not in configgen.PLACEHOLDER_SCRIPT_IDS]
        if body.get("replace") or not ids:
            ids = [deployment_id]
        elif deployment_id not in ids:
            ids.append(deployment_id)

        config.pop("script_ids", None)
        config["script_id"] = ids if len(ids) > 1 else ids[0]
        store.save_config(config)

        state = store.load()
        saved = state["gas"]["deployment_ids"]
        if deployment_id not in saved:
            saved.append(deployment_id)
        store.update(gas={"deployment_ids": saved})

        return _ok(script_ids=ids, exec_url=gasgen.exec_url(deployment_id))

    # ── proxy users ───────────────────────────────────────────────────

    @app.post("/api/users/auth-toggle")
    @security.login_required
    def api_users_toggle():
        enabled = str(_json_body().get("enabled", "")).lower() in ("1", "true", "on")
        try:
            users.set_auth_enabled(enabled)
        except users.UserError as exc:
            return _fail(str(exc))
        if manager.running:
            return _ok(message="اعمال شد. برای تغییر روش احراز هویت SOCKS5 "
                               "بهتر است رله را ری‌استارت کنید.")
        return _ok(message="اعمال شد.")

    @app.post("/api/users/add")
    @security.login_required
    def api_users_add():
        body = _json_body()
        try:
            users.add_user(
                username=body.get("username", ""),
                password=body.get("password", ""),
                quota_gb=body.get("quota_gb") or 0,
                expires_at=body.get("expires_at"),
                note=body.get("note", ""),
            )
        except (users.UserError, ValueError) as exc:
            return _fail(str(exc))
        return _ok(users=users.list_users())

    @app.post("/api/users/update")
    @security.login_required
    def api_users_update():
        body = _json_body()
        enabled = body.get("enabled")
        try:
            users.update_user(
                username=body.get("username", ""),
                password=body.get("password") or None,
                quota_gb=body.get("quota_gb") if body.get("quota_gb") not in (None, "") else None,
                expires_at=body.get("expires_at"),
                note=body.get("note"),
                enabled=None if enabled is None else str(enabled).lower() in ("1", "true", "on"),
            )
        except (users.UserError, ValueError) as exc:
            return _fail(str(exc))
        return _ok(users=users.list_users())

    @app.post("/api/users/delete")
    @security.login_required
    def api_users_delete():
        try:
            users.delete_user(_json_body().get("username", ""))
        except users.UserError as exc:
            return _fail(str(exc))
        return _ok(users=users.list_users())

    @app.post("/api/users/reset-usage")
    @security.login_required
    def api_users_reset():
        try:
            users.reset_usage(_json_body().get("username", ""))
        except users.UserError as exc:
            return _fail(str(exc))
        return _ok(users=users.list_users())

    @app.post("/api/users/disconnect")
    @security.login_required
    def api_users_disconnect():
        try:
            killed = users.disconnect(_json_body().get("username", ""))
        except users.UserError as exc:
            return _fail(str(exc))
        return _ok(closed=killed, users=users.list_users())

    @app.get("/api/users")
    @security.login_required
    def api_users_list():
        config = store.load_config()
        if config is None:
            return _ok(users=[], auth_enabled=False)
        return _ok(users=users.list_users(), auth_enabled=users.auth_enabled())

    # ── settings ──────────────────────────────────────────────────────

    @app.post("/settings")
    @security.login_required
    def settings_save():
        form = request.form
        store.update(settings={
            "auto_start_relay": form.get("auto_start_relay") == "on",
            "remember_cloudflare_token": form.get("remember_cloudflare_token") == "on",
            "chart_window": _int_arg(form.get("chart_window"), 120, 30, 720),
            "auto_failover": form.get("auto_failover") == "on",
            "failover_seconds": _int_arg(form.get("failover_seconds"), 60, 20, 600),
        })
        manager.failover.enabled = form.get("auto_failover") == "on"
        manager.failover.grace = float(_int_arg(form.get("failover_seconds"), 60, 20, 600))

        if form.get("panel_password"):
            if len(form["panel_password"]) < 10:
                flash("رمز جدید پنل باید حداقل ۱۰ کاراکتر باشد.", "error")
            elif form["panel_password"] != form.get("panel_password_confirm"):
                flash("تکرار رمز جدید مطابقت ندارد.", "error")
            else:
                security.set_admin_password(form["panel_password"])
                flash("رمز پنل تغییر کرد.", "success")
        flash("تنظیمات ذخیره شد.", "success")
        return redirect(url_for("settings_page"))

    @app.post("/api/settings/forwarder-env")
    @security.login_required
    def api_forwarder_env():
        body = _json_body()
        # A request with no "content" key must not silently truncate the file:
        # this writes outside the panel's own data directory, so an empty or
        # malformed body would destroy the operator's forwarder settings.
        if "content" not in body:
            return _fail("محتوایی برای ذخیره ارسال نشده است.")
        content = str(body.get("content") or "")
        if len(content) > 16 * 1024:
            return _fail("محتوای فایل .env بیش از حد بزرگ است.")
        if not content.strip():
            return _fail(
                "محتوای خالی ذخیره نمی‌شود. برای پاک‌کردن تنظیمات فورواردر، "
                "فایل .env را مستقیماً حذف کنید."
            )
        bad = _invalid_env_line(content)
        if bad is not None:
            return _fail(f"سطر نامعتبر در فایل .env: «{bad[:60]}» — "
                         f"هر سطر باید به شکل KEY=VALUE باشد.")
        os.makedirs(os.path.dirname(paths.FORWARDER_ENV), exist_ok=True)
        fd = os.open(paths.FORWARDER_ENV, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        return _ok(message="فایل .env فورواردر ذخیره شد.")

    # ── certificate authority ─────────────────────────────────────────

    @app.post("/api/ca/install")
    @security.login_required
    @security.rate_limit("ca_install", limit=4, window=120)
    def api_ca_install():
        from cert_installer import install_ca      # from engine/
        from mitm import CA_CERT_FILE, MITMCertManager

        if not os.path.exists(CA_CERT_FILE):
            MITMCertManager()   # side effect: writes ca/ca.crt + ca/ca.key
        ok = bool(install_ca(CA_CERT_FILE))
        trusted = refresh_ca_status()
        if ok and trusted:
            return _ok(message="گواهی CA نصب و مورد اعتماد شد. مرورگر را ببندید و باز کنید.")
        if ok:
            return _ok(message="نصب انجام شد ولی هنوز مورد اعتماد نیست؛ "
                               "ممکن است نیاز به راه‌اندازی مجدد مرورگر باشد.")
        return _fail("نصب خودکار ناموفق بود. دستور "
                     "`python main.py --install-cert` را با دسترسی مدیر اجرا کنید.")

    @app.get("/api/ca/download")
    @security.login_required
    def api_ca_download():
        from mitm import CA_CERT_FILE
        if not os.path.exists(CA_CERT_FILE):
            return _fail("گواهی CA هنوز ساخته نشده است.", 404)
        return send_file(CA_CERT_FILE, as_attachment=True, download_name="aras-gp-ca.crt")

    @app.get("/api/ca/status")
    @security.login_required
    def api_ca_status():
        return _ok(trusted=refresh_ca_status(), command=macos_trust_command())

    # ── errors ────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def _not_found(_error):
        if request.path.startswith("/api/"):
            return _fail("مسیر پیدا نشد.", 404)
        return render_template("error.html", code=404,
                               message="صفحه‌ای که دنبالش بودید پیدا نشد."), 404

    @app.errorhandler(500)
    def _server_error(error):
        log.exception("Unhandled panel error: %s", error)
        if request.path.startswith("/api/"):
            return _fail("خطای داخلی پنل.", 500)
        return render_template("error.html", code=500,
                               message="خطای داخلی در پنل رخ داد."), 500

    return app


def _maybe_autostart() -> None:
    settings = store.load()["settings"]
    if not settings.get("auto_start_relay"):
        return
    config = store.load_config()
    if config is None:
        return
    try:
        configgen.validate(config)
    except configgen.ConfigError as exc:
        log.warning("Auto-start skipped: %s", exc)
        return
    ok, message = manager.start(config)
    log.info("Auto-start: %s", message if ok else f"failed — {message}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    licensing.guard()

    host = os.environ.get("ARAS_PANEL_HOST", "127.0.0.1")
    port = int(os.environ.get("ARAS_PANEL_PORT", "8600"))

    if host not in ("127.0.0.1", "localhost", "::1"):
        log.warning(
            "Panel is binding to %s — it holds your auth_key and Cloudflare "
            "token. Put it behind a VPN or an authenticated reverse proxy with "
            "TLS; do not expose it to the internet.", host,
        )

    app = create_app()
    _maybe_autostart()

    log.info("Aras-GP Panel v%s → http://%s:%d", __version__, host, port)
    try:
        app.run(host=host, port=port, debug=False, threaded=True,
                use_reloader=False)
    finally:
        if manager.running:
            users.persist_live_usage()
            manager.stop()


if __name__ == "__main__":
    main()
