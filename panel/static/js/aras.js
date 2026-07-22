/* =====================================================================
   Aras-GP Panel — client runtime
   ---------------------------------------------------------------------
   No framework, no bundler, no CDN. Everything the panel needs at runtime
   lives in this file: a CSRF-aware fetch wrapper, Persian-aware
   formatters, toasts, a modal, and a hand-rolled canvas chart.

   The chart is deliberately not a charting library. Pulling one in would
   mean either a CDN request (which a censorship tool must not make) or a
   vendored megabyte of JS. Two hundred lines of canvas covers what the
   dashboard actually needs.
   ===================================================================== */

(function () {
  "use strict";

  var Aras = window.Aras = {};

  /* ── csrf-aware transport ──────────────────────────────────────── */

  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  Aras.api = function (url, options) {
    options = options || {};
    var headers = Object.assign(
      { "Accept": "application/json", "X-CSRF-Token": csrf() },
      options.headers || {}
    );
    var init = { method: options.method || "GET", headers: headers,
                 credentials: "same-origin" };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    return fetch(url, init).then(function (response) {
      if (response.status === 401) {
        window.location.href = "/login";
        return { ok: false, error: "نشست منقضی شد." };
      }
      return response.json().catch(function () {
        return { ok: false, error: "پاسخ نامعتبر از پنل." };
      });
    }).catch(function () {
      return { ok: false, error: "ارتباط با پنل قطع شد." };
    });
  };

  Aras.post = function (url, body) {
    return Aras.api(url, { method: "POST", body: body || {} });
  };

  /* ── formatters ────────────────────────────────────────────────── */

  var BYTE_UNITS = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت"];

  Aras.bytes = function (value, digits) {
    value = Number(value) || 0;
    var i = 0;
    while (value >= 1024 && i < BYTE_UNITS.length - 1) { value /= 1024; i++; }
    var d = digits === undefined ? (i === 0 ? 0 : (value < 10 ? 2 : 1)) : digits;
    return { value: value.toFixed(d), unit: BYTE_UNITS[i] };
  };

  Aras.bytesText = function (value) {
    var parts = Aras.bytes(value);
    return parts.value + " " + parts.unit;
  };

  Aras.speed = function (bps) {
    var parts = Aras.bytes(bps);
    return parts.value + " " + parts.unit + "/ث";
  };

  /* Metrics use Latin digits on purpose: they sit in tabular columns next to
     Latin units (ms, KB), and Persian-Indic digits (U+06F0…) are missing from
     some fallback fonts, which would show as tofu boxes. Prose stays Persian. */
  Aras.number = function (value) {
    return (Number(value) || 0).toLocaleString("en-US");
  };

  Aras.duration = function (seconds) {
    seconds = Math.max(0, Math.floor(Number(seconds) || 0));
    var d = Math.floor(seconds / 86400);
    var h = Math.floor((seconds % 86400) / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (d) return d + " روز و " + h + " ساعت";
    if (h) return h + " ساعت و " + m + " دقیقه";
    if (m) return m + " دقیقه و " + s + " ثانیه";
    return s + " ثانیه";
  };

  Aras.ago = function (epoch) {
    if (!epoch) return "—";
    var delta = Date.now() / 1000 - Number(epoch);
    if (delta < 5) return "همین حالا";
    if (delta < 60) return Math.floor(delta) + " ثانیه پیش";
    if (delta < 3600) return Math.floor(delta / 60) + " دقیقه پیش";
    if (delta < 86400) return Math.floor(delta / 3600) + " ساعت پیش";
    return Math.floor(delta / 86400) + " روز پیش";
  };

  Aras.dateTime = function (epoch) {
    if (!epoch) return "—";
    try {
      return new Date(Number(epoch) * 1000)
        .toLocaleString("fa-IR-u-nu-latn", { dateStyle: "medium", timeStyle: "short" });
    } catch (e) {
      return new Date(Number(epoch) * 1000).toISOString().slice(0, 16).replace("T", " ");
    }
  };

  Aras.escape = function (text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  };

  /* ── toasts ────────────────────────────────────────────────────── */

  var ICONS = {
    success: '<path d="M20 6 9 17l-5-5"/>',
    error: '<circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/>',
    warn: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>'
  };

  Aras.toast = function (message, kind, ttl) {
    kind = kind || "info";
    var host = document.querySelector(".ar-toasts");
    if (!host) {
      host = document.createElement("div");
      host.className = "ar-toasts";
      document.body.appendChild(host);
    }
    var node = document.createElement("div");
    node.className = "ar-toast ar-toast--" + kind;
    node.setAttribute("role", kind === "error" ? "alert" : "status");
    node.innerHTML =
      '<svg class="ar-i" width="18" height="18" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round">' + (ICONS[kind] || ICONS.info) + "</svg>" +
      "<div>" + Aras.escape(message) + "</div>";
    host.appendChild(node);

    var timer = setTimeout(dismiss, ttl || 5200);
    node.addEventListener("click", dismiss);

    function dismiss() {
      clearTimeout(timer);
      node.classList.add("ar-toast--out");
      setTimeout(function () { node.remove(); }, 200);
    }
  };

  /* Show a {ok, error, message} API result as a toast; returns result.ok. */
  Aras.report = function (result, successMessage) {
    if (result && result.ok) {
      Aras.toast(result.message || successMessage || "انجام شد.", "success");
      return true;
    }
    Aras.toast((result && result.error) || "عملیات ناموفق بود.", "error", 7000);
    return false;
  };

  /* ── button busy state ─────────────────────────────────────────── */

  Aras.busy = function (button, on) {
    if (!button) return;
    if (on) {
      button.dataset.arasLabel = button.innerHTML;
      button.classList.add("ar-btn--busy");
      button.disabled = true;
      button.innerHTML =
        '<svg class="ar-i" width="15" height="15" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="2.4" stroke-linecap="round">' +
        '<path d="M21 12a9 9 0 1 1-6.2-8.6"/></svg><span>در حال انجام…</span>';
    } else {
      button.classList.remove("ar-btn--busy");
      button.disabled = false;
      if (button.dataset.arasLabel) button.innerHTML = button.dataset.arasLabel;
    }
  };

  /* Wrap an async click handler with busy state. */
  Aras.action = function (button, handler) {
    if (!button) return;
    button.addEventListener("click", function (event) {
      event.preventDefault();
      if (button.disabled) return;
      Aras.busy(button, true);
      Promise.resolve(handler(event)).finally(function () {
        Aras.busy(button, false);
      });
    });
  };

  /* ── clipboard ─────────────────────────────────────────────────── */

  Aras.copy = function (text, label) {
    function fallback() {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); } catch (e) { /* nothing else to try */ }
      area.remove();
      Aras.toast((label || "متن") + " کپی شد.", "success", 2600);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () {
        Aras.toast((label || "متن") + " کپی شد.", "success", 2600);
      }, fallback);
    } else {
      // http://127.0.0.1 is not a secure context in some browsers.
      fallback();
    }
  };

  /* ── modal ─────────────────────────────────────────────────────── */

  Aras.modal = {
    open: function (id) {
      var node = document.getElementById(id);
      if (!node) return;
      node.hidden = false;
      var focusable = node.querySelector("input, select, textarea, button");
      if (focusable) setTimeout(function () { focusable.focus(); }, 60);
    },
    close: function (id) {
      var node = document.getElementById(id);
      if (node) node.hidden = true;
    }
  };

  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-modal-open]");
    if (opener) { Aras.modal.open(opener.dataset.modalOpen); return; }
    var closer = event.target.closest("[data-modal-close]");
    if (closer) { Aras.modal.close(closer.dataset.modalClose); return; }
    if (event.target.classList && event.target.classList.contains("ar-modal")) {
      event.target.hidden = true;
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    Array.prototype.forEach.call(document.querySelectorAll(".ar-modal:not([hidden])"),
      function (node) { node.hidden = true; });
  });

  /* ── copy buttons ──────────────────────────────────────────────── */

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) return;
    event.preventDefault();
    var selector = button.dataset.copy;
    var source = selector.charAt(0) === "#" ? document.querySelector(selector) : null;
    var text = source ? (source.value !== undefined ? source.value : source.textContent)
                      : selector;
    Aras.copy(text, button.dataset.copyLabel || "متن");
  });

  /* ── sidebar (mobile) ──────────────────────────────────────────── */

  Aras.sidebar = function (open) {
    var side = document.querySelector(".ar-side");
    var scrim = document.querySelector(".ar-scrim");
    if (!side) return;
    side.classList.toggle("ar-side--open", open);
    if (scrim) scrim.hidden = !open;
  };

  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-sidebar-toggle]")) {
      Aras.sidebar(!document.querySelector(".ar-side").classList.contains("ar-side--open"));
    } else if (event.target.closest(".ar-scrim")) {
      Aras.sidebar(false);
    }
  });

  /* ── canvas area chart ─────────────────────────────────────────── */

  /**
   * Minimal live area chart.
   *   canvas  — target <canvas>
   *   options — { color, fill, label, format }
   * Call .render(points) with an array of numbers, newest last.
   */
  Aras.Chart = function (canvas, options) {
    options = options || {};
    var ctx = canvas.getContext("2d");
    var points = [];
    var hover = null;
    var self = this;

    var color = options.color || "#7C5CFF";
    var color2 = options.color2 || "#2F83F6";
    var format = options.format || function (v) { return String(v); };

    function size() {
      var ratio = window.devicePixelRatio || 1;
      var rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * ratio));
      canvas.height = Math.max(1, Math.floor(rect.height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      return { w: rect.width, h: rect.height };
    }

    function draw() {
      var box = size();
      var w = box.w, h = box.h;
      ctx.clearRect(0, 0, w, h);
      if (points.length < 2) return;

      var padTop = 14, padBottom = 22, padSide = 4;
      var plotH = h - padTop - padBottom;
      var plotW = w - padSide * 2;
      var max = Math.max.apply(null, points);
      if (!isFinite(max) || max <= 0) max = 1;
      max *= 1.18;

      // horizontal guides
      ctx.strokeStyle = "rgba(255,255,255,0.055)";
      ctx.lineWidth = 1;
      for (var g = 0; g <= 3; g++) {
        var gy = padTop + (plotH / 3) * g;
        ctx.beginPath();
        ctx.moveTo(padSide, gy + 0.5);
        ctx.lineTo(w - padSide, gy + 0.5);
        ctx.stroke();
      }

      var stepX = plotW / (points.length - 1);
      function xAt(i) { return padSide + stepX * i; }
      function yAt(v) { return padTop + plotH - (v / max) * plotH; }

      // smooth path (monotone-ish via midpoint quadratics)
      function trace() {
        ctx.beginPath();
        ctx.moveTo(xAt(0), yAt(points[0]));
        for (var i = 1; i < points.length; i++) {
          var px = xAt(i - 1), py = yAt(points[i - 1]);
          var cx = xAt(i), cy = yAt(points[i]);
          var mx = (px + cx) / 2;
          ctx.bezierCurveTo(mx, py, mx, cy, cx, cy);
        }
      }

      // fill
      var gradient = ctx.createLinearGradient(0, padTop, 0, padTop + plotH);
      gradient.addColorStop(0, hexA(color, 0.34));
      gradient.addColorStop(1, hexA(color, 0));
      trace();
      ctx.lineTo(xAt(points.length - 1), padTop + plotH);
      ctx.lineTo(xAt(0), padTop + plotH);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      // stroke
      var strokeGrad = ctx.createLinearGradient(0, 0, w, 0);
      strokeGrad.addColorStop(0, color2);
      strokeGrad.addColorStop(1, color);
      trace();
      ctx.strokeStyle = strokeGrad;
      ctx.lineWidth = 2.2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.shadowColor = hexA(color, 0.5);
      ctx.shadowBlur = 12;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // leading marker
      var lastX = xAt(points.length - 1), lastY = yAt(points[points.length - 1]);
      ctx.beginPath();
      ctx.arc(lastX, lastY, 3.4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(lastX, lastY, 7, 0, Math.PI * 2);
      ctx.strokeStyle = hexA(color, 0.35);
      ctx.lineWidth = 1.4;
      ctx.stroke();

      // hover readout
      if (hover !== null && hover >= 0 && hover < points.length) {
        var hx = xAt(hover), hy = yAt(points[hover]);
        ctx.beginPath();
        ctx.moveTo(hx, padTop);
        ctx.lineTo(hx, padTop + plotH);
        ctx.strokeStyle = "rgba(255,255,255,0.2)";
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(hx, hy, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#fff";
        ctx.fill();

        var text = format(points[hover]);
        ctx.font = '600 11px ' +
          getComputedStyle(document.body).getPropertyValue("--ar-font");
        var tw = ctx.measureText(text).width + 14;
        var tx = Math.min(Math.max(hx - tw / 2, 2), w - tw - 2);
        ctx.fillStyle = "rgba(16,16,32,0.94)";
        roundRect(ctx, tx, 0, tw, 19, 6);
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.12)";
        ctx.stroke();
        ctx.fillStyle = "#EFEAFF";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, tx + tw / 2, 10);
      }
    }

    function roundRect(c, x, y, w, h, r) {
      c.beginPath();
      c.moveTo(x + r, y);
      c.arcTo(x + w, y, x + w, y + h, r);
      c.arcTo(x + w, y + h, x, y + h, r);
      c.arcTo(x, y + h, x, y, r);
      c.arcTo(x, y, x + w, y, r);
      c.closePath();
    }

    function hexA(hex, alpha) {
      var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      if (!m) return hex;
      return "rgba(" + parseInt(m[1], 16) + "," + parseInt(m[2], 16) + "," +
             parseInt(m[3], 16) + "," + alpha + ")";
    }

    canvas.addEventListener("mousemove", function (event) {
      if (points.length < 2) return;
      var rect = canvas.getBoundingClientRect();
      var ratio = (event.clientX - rect.left) / rect.width;
      hover = Math.round(ratio * (points.length - 1));
      draw();
    });

    canvas.addEventListener("mouseleave", function () { hover = null; draw(); });
    window.addEventListener("resize", function () { draw(); });

    self.render = function (values) {
      points = (values || []).map(function (v) { return Number(v) || 0; });
      draw();
    };
    self.redraw = draw;
    return self;
  };

  /* ── polling ───────────────────────────────────────────────────── */

  /**
   * Repeatedly call `fn`, but only while the tab is actually being looked at.
   *
   * A background tab polling every 5 s burns CPU on both ends and, for a
   * censorship tool, adds a steady request pattern for no benefit. Hidden tabs
   * are paused entirely and resume with an immediate refresh, so the operator
   * never sees stale numbers when they switch back.
   *
   * `options.idle` slows the loop down when `options.isIdle()` says nothing is
   * moving — a stopped relay does not need five-second updates.
   */
  Aras.poll = function (fn, interval, options) {
    options = options || {};
    var idle = options.idle || interval * 3;
    var timer = null;

    function delay() {
      return (options.isIdle && options.isIdle()) ? idle : interval;
    }

    function stop() {
      if (timer) { clearTimeout(timer); timer = null; }
    }

    function loop() {
      stop();
      if (document.hidden) return;
      Promise.resolve(fn()).finally(function () {
        if (!document.hidden) timer = setTimeout(loop, delay());
      });
    }

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop(); else loop();
    });

    loop();
    return { stop: stop, refresh: loop };
  };

  /* ── flash messages rendered server-side ───────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    var holder = document.getElementById("ar-flashes");
    if (!holder) return;
    try {
      JSON.parse(holder.textContent || "[]").forEach(function (item) {
        Aras.toast(item[1], item[0] === "message" ? "info" : item[0]);
      });
    } catch (e) { /* malformed flash payload is not worth breaking the page */ }
  });
})();
