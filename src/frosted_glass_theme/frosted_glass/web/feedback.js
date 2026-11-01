/* Frosted Glass + Feedback: reviewer-side script.
   window.FG_CONFIG is written by the add-on just before this script. */
(function () {
  "use strict";
  var root = document.documentElement;
  var KEYS = { 1: "again", 2: "hard", 3: "good", 4: "easy" };

  function cfg() { return window.FG_CONFIG || {}; }

  // ---------------------------------------------------------------- audio
  // Sounds are decoded once and played through Web Audio inside this page,
  // which starts them within a few milliseconds of the key press.
  var ctx = null, gain = null, buffers = {};

  function initAudio() {
    if (ctx || !(window.AudioContext || window.webkitAudioContext)) return;
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: "interactive" });
      gain = ctx.createGain();
      gain.connect(ctx.destination);
      setVolume();
      // A signal far below hearing keeps the output device (and Bluetooth
      // headphones) from dozing off between answers, which would delay the note.
      try {
        var hum = ctx.createConstantSource ? ctx.createConstantSource() : null;
        if (hum) {
          var low = ctx.createGain();
          low.gain.value = 0.00002;
          hum.connect(low);
          low.connect(ctx.destination);
          hum.start();
        }
      } catch (e) {}
      var urls = cfg().sounds || {};
      Object.keys(urls).forEach(function (key) {
        fetch(urls[key])
          .then(function (r) { return r.arrayBuffer(); })
          .then(function (data) { return ctx.decodeAudioData(data); })
          .then(function (buf) { buffers[key] = buf; })
          .catch(function () {});
      });
    } catch (e) { ctx = null; }
  }

  function setVolume() {
    if (gain) gain.gain.value = Math.max(0, Math.min(1, Number(cfg().volume) || 0));
  }

  // Keep the audio device awake so the first note isn't late.
  function wake() { if (ctx && ctx.state !== "running") ctx.resume().catch(function () {}); }
  ["keydown", "mousedown", "pointerdown"].forEach(function (ev) {
    document.addEventListener(ev, wake, true);
  });

  function playSound(key) {
    var buf = buffers[key];
    if (ctx && buf && ctx.state === "running") {
      var src = ctx.createBufferSource();
      var fade = ctx.createGain();
      // a few ms of fade-in so the note never clicks on
      fade.gain.setValueAtTime(0, ctx.currentTime);
      fade.gain.linearRampToValueAtTime(1, ctx.currentTime + 0.004);
      src.buffer = buf;
      src.connect(fade);
      fade.connect(gain);
      src.start();
      return;
    }
    // Page audio not ready (or blocked): let the add-on play it natively.
    wake();
    if (window.pycmd) pycmd("fgsound:" + key);
  }

  // ---------------------------------------------------------------- glass

  // Apply sizing/tint variables, volume, and switch the glass on or off.
  window.fgApply = function (newCfg) {
    if (newCfg) window.FG_CONFIG = newCfg;
    var c = cfg();
    var vars = c.vars || {};
    Object.keys(vars).forEach(function (k) { root.style.setProperty(k, vars[k]); });
    var sheet = document.getElementById("fg-glass-css");
    if (sheet) sheet.disabled = !c.glass;
    syncPane();
    // Card text size: only the base size changes; bold, colors etc. are untouched,
    // and text sized relative to it (em, %) follows along.
    var size = document.getElementById("fg-text-size");
    if (size) size.textContent = c.text_px > 0 ? "html body.card { font-size: " + c.text_px + "px !important; }" : "";
    setVolume();
  };

  // The frosted glass layer, kept exactly behind the card (see glass.css).
  function syncPane() {
    var qa = document.getElementById("qa");
    if (!qa || !document.body) return;
    var pane = document.getElementById("fg-pane");
    if (!pane) {
      pane = document.createElement("div");
      pane.id = "fg-pane";
      document.body.insertBefore(pane, document.body.firstChild);
    }
    pane.hidden = !cfg().glass;
    if (pane.hidden) return;
    pane.classList.toggle("fg-empty", !qa.firstChild);
    // move by the difference between where the pane is and where the card is,
    // so it lines up whatever the pane is positioned against
    var p = pane.getBoundingClientRect(), q = qa.getBoundingClientRect();
    var left = (parseFloat(pane.style.left) || 0) + q.left - p.left;
    var top = (parseFloat(pane.style.top) || 0) + q.top - p.top;
    pane.style.left = left + "px";
    pane.style.top = top + "px";
    pane.style.width = q.width + "px";
    pane.style.height = q.height + "px";
  }

  function watchPane() {
    var qa = document.getElementById("qa");
    if (!qa) return;
    syncPane();
    // size changes are followed from watchHeight's observer below
    new MutationObserver(syncPane).observe(qa, { childList: true });
    window.addEventListener("resize", syncPane);
  }

  function rgba(hex, a) {
    var h = String(hex || "").replace("#", "");
    if (h.length === 3) h = h.replace(/./g, "$&$&");
    if (!/^[0-9a-f]{6}/i.test(h)) return "rgba(255,255,255," + a + ")";
    return "rgba(" + parseInt(h.slice(0, 2), 16) + "," + parseInt(h.slice(2, 4), 16) + "," +
      parseInt(h.slice(4, 6), 16) + "," + a + ")";
  }

  function glow(key) {
    var c = cfg();
    var qa = document.getElementById("qa");
    if (!c.glass || !qa || !qa.animate) return;
    var color = (c.colors || {})[key];
    var base = getComputedStyle(qa).boxShadow;
    if (!base || base === "none") base = "0 0 0 0 transparent";
    qa.animate(
      [
        { boxShadow: "0 0 0 1px " + rgba(color, 0.75) + ", 0 0 30px " + rgba(color, 0.38) + ", " + base },
        { boxShadow: "0 0 0 1px " + rgba(color, 0.6) + ", 0 0 30px " + rgba(color, 0.3) + ", " + base, offset: 0.3 },
        { boxShadow: "0 0 0 1px " + rgba(color, 0) + ", 0 0 30px " + rgba(color, 0) + ", " + base }
      ],
      { duration: 1100, easing: "cubic-bezier(.3,.6,.4,1)" }
    );
  }

  // ease 1=Again 2=Hard 3=Good 4=Easy. The note is started as early as
  // possible (key or button going down); the add-on's answer hook calls this
  // again a moment later and is ignored if the note already played.
  var last = { ease: 0, t: -1e9 };

  function fire(ease, withGlow, withSound) {
    var key = KEYS[ease];
    if (!key) return;
    last = { ease: ease, t: performance.now() };
    if (withSound) playSound(key);
    if (withGlow) glow(key);
  }

  window.fgSide = function (answerShown) {
    window.fgAnswerShown = answerShown;
    last = { ease: 0, t: -1e9 };
  };

  window.fgPress = function (ease) {
    if (!window.fgAnswerShown) return;
    var c = cfg();
    fire(ease, c.glow_on !== false, c.sound_on !== false);
  };

  // Called by the add-on when Anki takes the answer (before it saves it).
  window.fgFeedback = function (ease, withGlow, withSound) {
    if (last.ease === ease && performance.now() - last.t < 1500) return;
    fire(ease, withGlow, withSound);
  };

  document.addEventListener("keydown", function (e) {
    if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    var ease = (cfg().answer_keys || {})[String(e.key).toLowerCase()];
    if (ease) window.fgPress(ease);
  }, true);

  // Snapshot of what the page is rendering, for "Copy diagnostics".
  window.fgDiagnostics = function () {
    var qa = document.getElementById("qa");
    var cs = qa ? getComputedStyle(qa) : null;
    var sheet = document.getElementById("fg-glass-css");
    var before = document.body ? getComputedStyle(document.body, "::before") : null;
    return JSON.stringify({
      glassSheetPresent: !!sheet,
      glassSheetDisabled: sheet ? sheet.disabled : null,
      qaFound: !!qa,
      paneFound: !!document.getElementById("fg-pane"),
      paneBackdrop: document.getElementById("fg-pane") ? (getComputedStyle(document.getElementById("fg-pane")).backdropFilter || getComputedStyle(document.getElementById("fg-pane")).webkitBackdropFilter) : null,
      qaWidth: qa ? qa.getBoundingClientRect().width : null,
      supportsBackdrop: !!(window.CSS && CSS.supports && (CSS.supports("backdrop-filter", "blur(1px)") || CSS.supports("-webkit-backdrop-filter", "blur(1px)"))),
      bodyClass: document.body ? document.body.className : null,
      wallpaperLayer: before ? String(before.backgroundImage).slice(0, 300) : null,
      audioState: ctx ? ctx.state : "none",
      audioLatencyMs: ctx ? Math.round(((ctx.baseLatency || 0) + (ctx.outputLatency || 0)) * 1000) : null,
      soundsLoaded: Object.keys(buffers),
      otherStylesTouchingQa: Array.prototype.slice.call(document.styleSheets).reduce(function (acc, s) {
        try {
          Array.prototype.forEach.call(s.cssRules || [], function (r) {
            if (r.selectorText && /#qa\b/.test(r.selectorText) && (!s.ownerNode || s.ownerNode.id !== "fg-glass-css")) acc.push(r.cssText.slice(0, 160));
          });
        } catch (e) {}
        return acc;
      }, []).slice(0, 10),
      userAgent: navigator.userAgent
    }, null, 1);
  };

  // When a long card does change the panel's height, ease between the two
  // heights instead of snapping, so the edge (and any glow on it) moves smoothly.
  function watchHeight() {
    var qa = document.getElementById("qa");
    if (!qa || !window.ResizeObserver) return;
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var lastH = 0;
    // Stop watching while the panel eases to its new size, so the animation
    // itself doesn't trigger more resize notifications.
    var ro = new ResizeObserver(function () {
      var h = qa.getBoundingClientRect().height;
      if (lastH && h && !reduce && qa.animate && cfg().glass && Math.abs(h - lastH) > 4) {
        ro.unobserve(qa);
        var a = qa.animate(
          [{ height: lastH + "px", overflow: "hidden" }, { height: h + "px", overflow: "hidden" }],
          { duration: 240, easing: "cubic-bezier(.3,.6,.4,1)" }
        );
        a.onfinish = a.oncancel = function () { lastH = qa.getBoundingClientRect().height; ro.observe(qa); syncPane(); };
        // the glass layer follows the card's edge on every frame of the ease
        (function follow() { syncPane(); if (a.playState === "running") requestAnimationFrame(follow); })();
        return;
      }
      lastH = h;
      syncPane();
    });
    ro.observe(qa);
  }

  window.fgApply();
  initAudio();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", watchHeight);
    document.addEventListener("DOMContentLoaded", watchPane);
  } else {
    watchHeight();
    watchPane();
  }
})();
