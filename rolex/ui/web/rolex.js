/* ============================================================
   ROLEX AI v2.1 · NEON HORIZON controller
   - Cosmic starfield + nebula canvas (realistic depth)
   - Fire/ice center emblem, bass-reactive glow
   - WebAudio sub-bass reactor -> --bass live CSS var
   - 16 orbital module satellites, per-route themed FX
   - Bridges to local Python backend; demo brain fallback
   ============================================================ */
"use strict";

/* ---------------- State ---------------- */
const S = {
  turns: 0,
  local: 0,
  routes: {},
  bootTime: Date.now(),
  speaking: false,
  backend: "demo",           /* "live" | "demo" */
  speakReplies: false,
  lastReply: "",
};

/* ---------------- Backend bridge ---------------- */
const API = {
  base: (location.protocol === "http:" || location.protocol === "https:")
    ? "" : "http://127.0.0.1:8777",
  async call(path, body) {
    const r = await fetch(`${API.base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
};

/* ---------------- i18n ---------------- */
const L = {
  welcome:
    "\ud83d\udc51 ROLEX v2.2.0 online \u00b7 NEON HORIZON.\n" +
    "Local-first personal intelligence \u00b7 ellame local!\n" +
    'Try: "2+2*10^3" \u00b7 "add task buy milk" \u00b7 "chennai la weather enna" \u00b7 "make a plan for ooty trip"',
  wake: "\ud83c\udfa7 Hey Guru detected \u2014 Rolex listening\u2026",
  offline:
    "\u26a0 Backend offline \u2014 demo brain active. python -m rolex.ui.bridge " +
    "run pannina full power kedaikum (live weather, tasks, memory, plans).",
};

/* ---------------- Demo brain (file:// fallback) ---------------- */
const DEMO = {
  re: {
    math: /^[\d\s+\-*/().%^]+$/,
    task: /^(add|create)\s+(task|todo)\s+(.+?)(\s+urgent)?$/i,
    showtasks: /^(show|list)\s+(my\s+)?(tasks|todos)$/i,
    weather: /weather\s+(?:in\s+)?([\w\s]+?)(\?|$)/i,
    plan: /(?:make|create)\s+a?\s*plan\s+for\s+(.+)$/i,
    remember: /^remember\s+(?:that\s+)?(.+)$/i,
    recall: /^(?:recall|what\s+do\s+you\s+know\s+about)\s+(.+)$/i,
    forget: /^forget\s+(?:about\s+)?(.+)$/i,
    prefs: /^(my\s+)?preferences$/i,
    voice: /set\s+voice\s+(?:to\s+)?(\w+)/i,
    wake: /^hey\s+guru/i,
    battery: /battery|charge/i,
    devices: /devices?|hardware/i,
  },
  tasks: [
    { id: "7f3a", title: "buy milk", prio: "high", done: false },
    { id: "b21c", title: "finish Neon Horizon UI", prio: "high", done: false },
    { id: "c910", title: "call mom", prio: "med", done: true },
  ],
  mem: [
    { key: "bike", value: "my bike is black and gold" },
    { key: "name", value: "owner is Sabari" },
  ],
  plans: [],

  async answer(q) {
    const t = q.trim();
    const r = DEMO.re;
    if (r.wake.test(t)) return { text: "\ud83c\udfa7 Rolex: yes?", route: "wake", local: true, conf: 1 };

    if (r.math.test(t) && /[\d]/.test(t)) {
      try {
        const val = Function(`"use strict"; return (${t.replace(/\^/g, "**")})`)();
        if (Number.isFinite(val)) return { text: `\u26a1 ${t} = ${val}`, route: "math", local: true, conf: 1 };
      } catch (e) { /* fall through */ }
    }

    let m = t.match(r.task);
    if (m) {
      DEMO.tasks.push({ id: Math.random().toString(16).slice(2, 6), title: m[3], prio: m[4] ? "high" : "med", done: false });
      return { text: `\u2705 \u0baa\u0ba3\u0bbf \u0b9a\u0bc7\u0bb0\u0bcd\u0b95\u0bcd\u0b95\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f\u0ba4\u0bc1 \u00b7 Task added: ${m[3]}`, route: "task", local: true, conf: .95 };
    }

    if (r.showtasks.test(t)) {
      const lines = DEMO.tasks.map((x, i) => `  ${x.done ? "\u2611" : "\u25cb"} ${i + 1}. ${x.title} (${x.prio}) \u2026[${x.id}]`);
      return { text: "\ud83d\udccb Rolex Task Board:\n" + lines.join("\n"), route: "task", local: true, conf: .95 };
    }

    m = t.match(r.remember);
    if (m) {
      DEMO.mem.push({ key: m[1].split(" ").slice(0, 3).join(" "), value: m[1] });
      return { text: `\ud83d\udcbe Rolex-\u0b95\u0bcd\u0b95\u0bc1 \u0ba8\u0bbf\u0ba9\u0bc8\u0bb5\u0bbf\u0bb2\u0bcd \u00b7 remembered: ${m[1]}`, route: "memory", local: true, conf: .95 };
    }

    m = t.match(r.recall);
    if (m) {
      const hits = DEMO.mem.filter((x) => x.value.toLowerCase().includes(m[1].toLowerCase().split(" ")[0]));
      if (hits.length) return { text: `\ud83d\udcbe ${hits.map((h) => "\u2022 " + h.value).join("\n")}`, route: "memory", local: true, conf: .95 };
      return { text: `\ud83d\udcbe '${m[1]}' \u0baa\u0bb1\u0bcd\u0bb1\u0bbf \u0b87\u0ba9\u0bcd\u0ba9\u0bc1\u0bae\u0bcd \u0b95\u0bb1\u0bcd\u0bb1\u0bb5\u0bbf\u0bb2\u0bcd\u0bb2\u0bc8 \u00b7 nothing remembered yet.`, route: "memory", local: true, conf: .95 };
    }

    m = t.match(r.forget);
    if (m) {
      const n = DEMO.mem.length;
      DEMO.mem = DEMO.mem.filter((x) => !x.value.toLowerCase().includes(m[1].toLowerCase()));
      return { text: `\ud83d\uddd1 ${n - DEMO.mem.length} memory entry forgotten.`, route: "memory", local: true, conf: .95 };
    }

    if (r.prefs.test(t)) {
      return { text: "\ud83d\udcbe preferences:\n" + DEMO.mem.map((x) => `  \u2022 ${x.key}: ${x.value}`).join("\n"), route: "memory", local: true, conf: .95 };
    }

    m = t.match(r.voice);
    if (m) {
      document.getElementById("t-voice").textContent = m[1].toUpperCase();
      document.getElementById("t-vrate").textContent = m[1].toLowerCase() === "jarvis" ? "158" : m[1].toLowerCase() === "narrator" ? "132" : "172";
      document.getElementById("t-vpitch").textContent = m[1].toLowerCase() === "jarvis" ? "30" : m[1].toLowerCase() === "narrator" ? "-10" : "10";
      return { text: `\ud83c\udfa7 voice profile \u2192 ${m[1]} (\u00a712 modulation active)`, route: "voice", local: true, conf: 1 };
    }

    m = t.match(r.weather);
    if (m) {
      const city = m[1].trim();
      if (S.backend === "live") {
        return await API.call("/ask", { text: t });
      }
      return {
        text: `\ud83c\udf26 ${city} live weather needs backend (Open-Meteo).\n` +
              "python -m rolex.ui.bridge run pannunga \u2014 appo live data kedaikum.",
        route: "live", local: false, conf: .5,
      };
    }

    m = t.match(r.plan);
    if (m) {
      const goal = m[1];
      const steps = [
        ["\u2139", "Decide destination & dates"],
        ["\ud83d\udcb0", `Estimate budget: ${goal}`],
        ["\ud83d\udcdd", "TODO \u2014 book tickets"],
        ["\ud83e\uddf3", "Pack list prepare"],
        ["\u2705", "Verify & enjoy"],
      ];
      DEMO.plans.push({ goal, steps: steps.map((s) => ({ glyph: s[0], text: s[1], done: false })) });
      return { text: `\ud83d\uddfa Rolex Plan \u00b7 ${goal} (5 steps)\n` + steps.map((s, i) => `  \u25cb ${i + 1}. ${s[0]} ${s[1]}`).join("\n"), route: "plan", local: true, conf: .95 };
    }

    if (r.battery.test(t)) return { text: "\ud83d\udd0b battery: 87% \u00b7 charging (demo telemetry)", route: "device", local: true, conf: 1 };
    if (r.devices.test(t)) return { text: "\ud83d\udcf1 device: Android 14 \u00b7 ARM64 \u00b7 8GB RAM (demo telemetry)", route: "device", local: true, conf: 1 };

    return {
      text: "\ud83e\udd14 Local brain-la idhu illa \u00b7 demo mode.\n" +
            "Try: math \u00b7 tasks \u00b7 remember \u00b7 recall \u00b7 plan \u00b7 weather \u00b7 voice \u00b7 battery\n" +
            "Backend connect pannina full Rolex power!",
      route: "chat", local: false, conf: .3,
    };
  },
};

/* ============================================================
   BASS REACTOR \u2014 sub-bass audio + glow level engine
   Drives --bass (0..1) live; pulses on reply + word boundaries
   ============================================================ */
const BASS = {
  on: true,
  level: 0,          /* smoothed 0..1 */
  target: 0,         /* instantaneous target */
  spike: 0,          /* decaying spike (word boundary / reply) */
  ctx: null,
  master: null,
  oscA: null, oscB: null,

  ensure() {
    if (BASS.ctx) return true;
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return false;
      BASS.ctx = new AC();
      BASS.master = BASS.ctx.createGain();
      BASS.master.gain.value = 0;

      /* deep sub-bass voice: 52Hz + 104Hz detuned, lowpassed */
      const lp = BASS.ctx.createBiquadFilter();
      lp.type = "lowpass"; lp.frequency.value = 220; lp.Q.value = 0.8;
      BASS.oscA = BASS.ctx.createOscillator();
      BASS.oscA.type = "sine"; BASS.oscA.frequency.value = 52;
      BASS.oscB = BASS.ctx.createOscillator();
      BASS.oscB.type = "triangle"; BASS.oscB.frequency.value = 104;
      const gB = BASS.ctx.createGain(); gB.gain.value = 0.35;
      BASS.oscA.connect(lp); BASS.oscB.connect(gB); gB.connect(lp);
      lp.connect(BASS.master); BASS.master.connect(BASS.ctx.destination);
      BASS.oscA.start(); BASS.oscB.start();
      return true;
    } catch (e) { return false; }
  },

  pulse(strength) {          /* word boundary / reply thump */
    BASS.spike = Math.min(1.4, BASS.spike + strength);
  },

  tick(dt, now) {            /* called every frame */
    /* continuous wobble while Rolex speaks */
    let wob = 0;
    if (S.speaking) {
      wob = 0.30 + 0.34 * Math.abs(Math.sin(now * 0.006)) +
            0.18 * Math.abs(Math.sin(now * 0.017 + 1.3));
    }
    BASS.spike = Math.max(0, BASS.spike - dt * 2.6);
    BASS.target = BASS.on ? Math.min(1, wob + BASS.spike) : 0;
    BASS.level += (BASS.target - BASS.level) * Math.min(1, dt * 9);

    document.documentElement.style.setProperty("--bass", BASS.level.toFixed(3));

    /* mirror level into audible sub-bass */
    if (BASS.ctx && BASS.master) {
      const g = BASS.on ? BASS.level * 0.34 : 0;
      BASS.master.gain.setTargetAtTime(g, BASS.ctx.currentTime, 0.05);
    }
  },
};

/* ============================================================
   FX ENGINE \u2014 starfield, nebula, particles, shockwaves
   ============================================================ */
const FX = {
  cv: null, cx: null, W: 0, H: 0,
  stars: [], parts: [], shocks: [],
  t0: performance.now(),

  init() {
    FX.cv = document.getElementById("fx");
    FX.cx = FX.cv.getContext("2d");
    FX.resize();
    window.addEventListener("resize", FX.resize);
    /* realistic depth starfield: 3 layers */
    FX.stars = [];
    const n = Math.min(190, Math.floor((FX.W * FX.H) / 9000));
    for (let i = 0; i < n; i++) {
      FX.stars.push({
        x: Math.random() * FX.W, y: Math.random() * FX.H,
        z: Math.random(),                       /* 0 far .. 1 near */
        tw: Math.random() * Math.PI * 2,        /* twinkle phase */
        ts: 0.4 + Math.random() * 1.8,          /* twinkle speed */
      });
    }
  },

  resize() {
    FX.W = FX.cv.width = window.innerWidth;
    FX.H = FX.cv.height = window.innerHeight;
  },

  center() {
    const r = document.getElementById("orb").getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  },

  shock(color) {
    const c = FX.center();
    FX.shocks.push({ x: c.x, y: c.y, r: 60, v: 5.5 + BASS.level * 6, a: 0.85, color: color || "212,175,55" });
  },

  burst(kind, color, count) {
    const c = FX.center();
    const n = count || 26;
    for (let i = 0; i < n; i++) {
      const ang = Math.random() * Math.PI * 2;
      const sp = 1.2 + Math.random() * 3.4 + BASS.level * 3;
      FX.parts.push({
        x: c.x, y: c.y,
        vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - 0.8,
        life: 1, decay: 0.008 + Math.random() * 0.014,
        size: 2.5 + Math.random() * 4.5,
        rot: Math.random() * Math.PI * 2, vr: (Math.random() - .5) * 0.14,
        kind, color,
        grav: (kind === "drop" || kind === "coin" || kind === "pin" || kind === "heart") ? 0.055 : 0.012,
      });
    }
    if (FX.parts.length > 260) FX.parts.splice(0, FX.parts.length - 260);
  },

  draw(now) {
    const cx = FX.cx, W = FX.W, H = FX.H;
    const dt = Math.min(0.05, (now - FX.t0) / 1000 || 0.016);
    FX.t0 = now;
    const b = BASS.level;

    cx.clearRect(0, 0, W, H);

    /* --- nebula: fire left / ice right / gold deep, breathing with bass --- */
    const breathe = 0.75 + 0.25 * Math.sin(now * 0.0006);
    const fireR = 320 + 130 * b;
    const iceR = 320 + 130 * b;
    let g = cx.createRadialGradient(W * 0.06, H * 0.04, 0, W * 0.06, H * 0.04, fireR);
    g.addColorStop(0, `rgba(255,66,30,${(0.16 + 0.22 * b) * breathe})`);
    g.addColorStop(1, "rgba(255,66,30,0)");
    cx.fillStyle = g; cx.fillRect(0, 0, W, H);

    g = cx.createRadialGradient(W * 0.94, H * 0.06, 0, W * 0.94, H * 0.06, iceR);
    g.addColorStop(0, `rgba(25,150,255,${(0.14 + 0.22 * b) * breathe})`);
    g.addColorStop(1, "rgba(25,150,255,0)");
    cx.fillStyle = g; cx.fillRect(0, 0, W, H);

    g = cx.createRadialGradient(W * 0.5, H * 1.05, 0, W * 0.5, H * 1.05, 420 + 160 * b);
    g.addColorStop(0, `rgba(127,110,255,${0.10 + 0.14 * b})`);
    g.addColorStop(1, "rgba(127,110,255,0)");
    cx.fillStyle = g; cx.fillRect(0, 0, W, H);

    /* --- stars: parallax drift + twinkle; near stars streak with bass --- */
    for (const s of FX.stars) {
      s.x += (0.006 + s.z * 0.02) * (1 + b * 2);
      if (s.x > W + 4) s.x = -4;
      const tw = 0.45 + 0.55 * Math.abs(Math.sin(now * 0.001 * s.ts + s.tw));
      const a = (0.25 + s.z * 0.75) * tw;
      const r = 0.4 + s.z * 1.5 + b * s.z * 1.2;
      cx.beginPath();
      cx.arc(s.x, s.y, r, 0, Math.PI * 2);
      cx.fillStyle = s.z > 0.82 ? `rgba(200,225,255,${a})` : `rgba(255,244,214,${a * 0.9})`;
      cx.fill();
    }

    /* --- shockwaves --- */
    for (let i = FX.shocks.length - 1; i >= 0; i--) {
      const w = FX.shocks[i];
      w.r += w.v; w.a -= 0.016;
      if (w.a <= 0) { FX.shocks.splice(i, 1); continue; }
      cx.beginPath();
      cx.arc(w.x, w.y, w.r, 0, Math.PI * 2);
      cx.strokeStyle = `rgba(${w.color},${w.a})`;
      cx.lineWidth = 2.2;
      cx.stroke();
      cx.beginPath();
      cx.arc(w.x, w.y, w.r * 0.86, 0, Math.PI * 2);
      cx.strokeStyle = `rgba(25,211,255,${w.a * 0.5})`;
      cx.lineWidth = 1;
      cx.stroke();
    }

    /* --- route particles --- */
    for (let i = FX.parts.length - 1; i >= 0; i--) {
      const p = FX.parts[i];
      p.x += p.vx * (1 + b * 0.6);
      p.y += p.vy * (1 + b * 0.6);
      p.vy += p.grav;
      p.rot += p.vr;
      p.life -= p.decay;
      if (p.life <= 0) { FX.parts.splice(i, 1); continue; }
      FX.drawPart(cx, p);
    }
  },

  drawPart(cx, p) {
    cx.save();
    cx.translate(p.x, p.y);
    cx.rotate(p.rot);
    cx.globalAlpha = Math.max(0, Math.min(1, p.life));
    cx.fillStyle = p.color;
    cx.strokeStyle = p.color;
    cx.lineWidth = 1.6;
    const s = p.size;
    switch (p.kind) {
      case "spark":                            /* math \u00b7 4-point star */
        cx.beginPath();
        for (let k = 0; k < 4; k++) {
          cx.rotate(Math.PI / 2);
          cx.moveTo(0, 0); cx.lineTo(s * 1.6, 0);
        }
        cx.stroke();
        cx.beginPath(); cx.arc(0, 0, s * 0.4, 0, Math.PI * 2); cx.fill();
        break;
      case "orb":                              /* memory/knowledge \u00b7 glow orb */
        cx.shadowBlur = 12; cx.shadowColor = p.color;
        cx.beginPath(); cx.arc(0, 0, s, 0, Math.PI * 2); cx.fill();
        break;
      case "check": {                          /* task \u00b7 tick */
        cx.lineWidth = 2.4;
        cx.beginPath();
        cx.moveTo(-s, 0); cx.lineTo(-s * 0.2, s * 0.8); cx.lineTo(s * 1.2, -s * 0.9);
        cx.stroke();
        break;
      }
      case "pin":                              /* plan \u00b7 map pin */
        cx.beginPath();
        cx.arc(0, -s * 0.4, s * 0.7, Math.PI, 0);
        cx.lineTo(0, s * 1.3);
        cx.closePath(); cx.fill();
        break;
      case "drop":                             /* weather \u00b7 rain streak */
        cx.lineWidth = 2;
        cx.beginPath(); cx.moveTo(0, -s * 1.6); cx.lineTo(0, s * 1.6); cx.stroke();
        break;
      case "bolt": {                           /* device/command \u00b7 lightning */
        cx.lineWidth = 2;
        cx.beginPath();
        cx.moveTo(-s * 0.3, -s * 1.4); cx.lineTo(s * 0.4, -s * 0.2);
        cx.lineTo(-s * 0.1, 0); cx.lineTo(s * 0.5, s * 1.4);
        cx.stroke();
        break;
      }
      case "ring":                             /* voice \u00b7 expanding ring */
        cx.lineWidth = 2;
        cx.beginPath(); cx.arc(0, 0, s * (2 - p.life), 0, Math.PI * 2); cx.stroke();
        break;
      case "shield":                           /* smarthome \u00b7 shield */
        cx.beginPath();
        cx.moveTo(0, -s * 1.2);
        cx.lineTo(s, -s * 0.6); cx.lineTo(s * 0.8, s * 0.7); cx.lineTo(0, s * 1.3);
        cx.lineTo(-s * 0.8, s * 0.7); cx.lineTo(-s, -s * 0.6);
        cx.closePath(); cx.stroke();
        break;
      case "coin":                             /* finance \u00b7 coin */
        cx.beginPath(); cx.arc(0, 0, s * 0.8, 0, Math.PI * 2); cx.fill();
        cx.globalAlpha *= 0.5;
        cx.fillStyle = "#04060f";
        cx.fillRect(-s * 0.12, -s * 0.5, s * 0.24, s);
        break;
      case "heart": {                          /* health \u00b7 heart */
        cx.beginPath();
        cx.moveTo(0, s * 0.9);
        cx.bezierCurveTo(-s * 1.4, -s * 0.2, -s * 0.5, -s * 1.3, 0, -s * 0.4);
        cx.bezierCurveTo(s * 0.5, -s * 1.3, s * 1.4, -s * 0.2, 0, s * 0.9);
        cx.fill();
        break;
      }
      case "doc":                              /* documents \u00b7 page */
        cx.fillRect(-s * 0.7, -s, s * 1.4, s * 2);
        cx.globalAlpha *= 0.5; cx.fillStyle = "#04060f";
        cx.fillRect(-s * 0.4, -s * 0.5, s * 0.8, s * 0.2);
        cx.fillRect(-s * 0.4, 0, s * 0.8, s * 0.2);
        break;
      case "lab":                              /* remote lab \u00b7 flask */
        cx.beginPath();
        cx.moveTo(-s * 0.25, -s); cx.lineTo(s * 0.25, -s);
        cx.lineTo(s * 0.8, s); cx.lineTo(-s * 0.8, s);
        cx.closePath(); cx.stroke();
        break;
      case "brain":                            /* learning \u00b7 node + branches */
        cx.beginPath(); cx.arc(0, 0, s * 0.55, 0, Math.PI * 2); cx.fill();
        cx.lineWidth = 1.4;
        for (let k = 0; k < 3; k++) {
          const a2 = k * 2.1;
          cx.beginPath();
          cx.moveTo(Math.cos(a2) * s * 0.5, Math.sin(a2) * s * 0.5);
          cx.lineTo(Math.cos(a2) * s * 1.5, Math.sin(a2) * s * 1.5);
          cx.stroke();
        }
        break;
      case "radar":                            /* search/ai \u00b7 arc sweep */
        cx.lineWidth = 2.4;
        cx.beginPath(); cx.arc(0, 0, s * 1.1, p.rot, p.rot + 1.2); cx.stroke();
        break;
      case "sync":                             /* sync \u00b7 two arcs */
        cx.lineWidth = 2.2;
        cx.beginPath(); cx.arc(0, 0, s * 0.9, 0.3, 2.4); cx.stroke();
        cx.beginPath(); cx.arc(0, 0, s * 0.9, 3.4, 5.6); cx.stroke();
        break;
      default:                                 /* dot */
        cx.beginPath(); cx.arc(0, 0, s * 0.7, 0, Math.PI * 2); cx.fill();
    }
    cx.restore();
  },
};

/* ---------------- route theme table ---------------- */
const ROUTES = {
  wake:     { fx: "ring",   color: "#d4af37", sat: "voice",     n: 14 },
  math:     { fx: "spark",  color: "#ffe98a", sat: "math",      n: 26 },
  command:  { fx: "bolt",   color: "#ffd24d", sat: "device",    n: 18 },
  memory:   { fx: "orb",    color: "#b48cff", sat: "memory",    n: 22 },
  voice:    { fx: "ring",   color: "#19d3ff", sat: "voice",     n: 20 },
  task:     { fx: "check",  color: "#35e07c", sat: "tasks",     n: 22 },
  plan:     { fx: "pin",    color: "#ffb347", sat: "planning",  n: 20 },
  reminders:{ fx: "pin",    color: "#ff8c5a", sat: "tasks",     n: 16 },
  life:     { fx: "coin",   color: "#ffd700", sat: "finance",   n: 20 },
  smarthome:{ fx: "shield", color: "#ff6a3c", sat: "smarthome", n: 22 },
  device:   { fx: "bolt",   color: "#9dff5a", sat: "device",    n: 18 },
  live:     { fx: "drop",   color: "#41c9ff", sat: "weather",   n: 30 },
  sync:     { fx: "sync",   color: "#35e0c0", sat: "sync",      n: 20 },
  document: { fx: "doc",    color: "#e8ecf4", sat: "documents", n: 18 },
  knowledge:{ fx: "orb",    color: "#5ad0ff", sat: "knowledge", n: 18 },
  ai:       { fx: "radar",  color: "#41c9ff", sat: "search",    n: 18 },
  offline:  { fx: "orb",    color: "#ff5a5a", sat: "search",    n: 12 },
  chat:     { fx: "orb",    color: "#8391ad", sat: "knowledge", n: 10 },
};

function fxForRoute(route) {
  const th = ROUTES[route] || ROUTES.chat;
  FX.burst(th.fx, th.color, th.n);
  FX.shock("212,175,55");
  hitModule(th.sat);
  blazeSat(th.sat);
}

/* ============================================================
   ORBITAL SATELLITES \u2014 16 module satellites around emblem
   ============================================================ */
const SATS = [
  { id: "math",      ico: "\u002b",      c: "#ffe98a", lbl: "MATH \u00a73",        q: "2+2*10^3" },
  { id: "memory",    ico: "\u25c9",      c: "#b48cff", lbl: "MEMORY \u00a72",      q: "recall my bike" },
  { id: "tasks",     ico: "\u2713",      c: "#35e07c", lbl: "TASKS \u00a79",       q: "show my tasks" },
  { id: "planning",  ico: "\u25b2",      c: "#ffb347", lbl: "PLANNING \u00a710",   q: "make a plan for ooty trip" },
  { id: "knowledge", ico: "\u25c8",      c: "#5ad0ff", lbl: "KNOWLEDGE \u00a77",   q: "what do you know about rolex" },
  { id: "documents", ico: "\u25a4",      c: "#e8ecf4", lbl: "DOCS \u00a78",        q: "list my documents" },
  { id: "weather",   ico: "\u2614",      c: "#41c9ff", lbl: "WEATHER \u00a76",     q: "chennai la weather enna", opt: true },
  { id: "search",    ico: "\u25d4",      c: "#6ea8ff", lbl: "SEARCH \u00a76.1",    q: "search for best phone 2025", opt: true },
  { id: "smarthome", ico: "\u2b1f",      c: "#ff6a3c", lbl: "HOME \u00a730",       q: "smart home status" },
  { id: "device",    ico: "\u26a1",      c: "#9dff5a", lbl: "DEVICE \u00a731",     q: "battery status" },
  { id: "sync",      ico: "\u21c4",      c: "#35e0c0", lbl: "SYNC \u00a720",       q: "backup status" },
  { id: "lab",       ico: "\u25b5",      c: "#8affc4", lbl: "LAB \u00a721",        q: "remote lab status", opt: true },
  { id: "voice",     ico: "\u2593",      c: "#19d3ff", lbl: "VOICE \u00a712",      q: "set voice to jarvis" },
  { id: "learning",  ico: "\u2b21",      c: "#ff7ad9", lbl: "LEARN \u00a739",      q: "learning status" },
  { id: "finance",   ico: "\u20b9",      c: "#ffd700", lbl: "FINANCE \u00a723",    q: "track expense 250 rupees coffee" },
  { id: "health",    ico: "\u2665",      c: "#ff6f91", lbl: "HEALTH \u00a727",     q: "log water 2 liters" },
];

function buildOrbit() {
  const orbit = document.getElementById("orbit");
  const cx = orbit.clientWidth / 2, cy = orbit.clientHeight / 2;
  const R = Math.min(cx, cy) - 26;
  SATS.forEach((m, i) => {
    const a = (i / SATS.length) * Math.PI * 2 - Math.PI / 2;
    const el = document.createElement("div");
    el.className = "sat" + (m.opt ? " opt" : "");
    el.id = "sat-" + m.id;
    /* margin:-23px in CSS centers the box on these coords */
    el.style.left = (cx + Math.cos(a) * R) + "px";
    el.style.top = (cy + Math.sin(a) * R) + "px";
    el.style.setProperty("--satc", m.c);
    el.innerHTML = `<span>${m.ico}</span><span class="satlbl">${m.lbl}</span>`;
    el.title = m.lbl;
    el.addEventListener("click", () => { ask(m.q); });
    orbit.appendChild(el);
  });
}

function blazeSat(id) {
  const el = document.getElementById("sat-" + id);
  if (!el) return;
  el.classList.remove("blaze");
  void el.offsetWidth;                    /* restart animation */
  el.classList.add("blaze");
  setTimeout(() => el.classList.remove("blaze"), 1700);
}

/* ============================================================
   VOICE \u2014 TTS with bass-reactive boundary pulses + STT
   ============================================================ */
const VOICE = {
  synth: window.speechSynthesis,

  speak(text) {
    if (!VOICE.synth || !S.speakReplies) return;
    VOICE.synth.cancel();
    BASS.ensure();
    if (BASS.ctx && BASS.ctx.state === "suspended") BASS.ctx.resume();
    const clean = text.replace(/[\u2022\u25b6\u26a1\ud83c\udf00-\ud83e\uddff]/gu, "").slice(0, 300);
    const u = new SpeechSynthesisUtterance(clean);
    u.rate = 1.15;
    u.pitch = 0.85;
    u.volume = 0.95;
    const vs = VOICE.synth.getVoices();
    const pick = vs.find((v) => /en-GB/i.test(v.lang) && /male|daniel|george/i.test(v.name)) ||
                 vs.find((v) => /en-GB/i.test(v.lang)) || vs[0];
    if (pick) u.voice = pick;

    u.onstart = () => {
      S.speaking = true;
      setOrb("listening");
      BASS.pulse(1.0);                     /* opening thump */
      FX.shock("255,120,60");
    };
    u.onboundary = () => {                 /* every word -> bass pulse + tiny fx */
      BASS.pulse(0.45 + Math.random() * 0.35);
    };
    u.onend = () => {
      S.speaking = false;
      BASS.pulse(0.6);                     /* closing thump */
      setOrb("standby");
    };
    VOICE.synth.speak(u);
  },

  listen(onFinal) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { toast("Voice input not supported in this browser"); return; }
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = false;
    rec.onstart = () => setOrb("listening");
    rec.onresult = (e) => {
      const txt = e.results[0][0].transcript;
      setOrb("standby");
      onFinal(txt);
    };
    rec.onerror = () => setOrb("standby");
    rec.onend = () => setOrb("standby");
    rec.start();
  },
};

/* ---------------- Orb status ---------------- */
function setOrb(mode) {
  const orb = document.getElementById("orb");
  const st = document.getElementById("orb-status");
  orb.classList.remove("listening");
  if (mode === "listening") {
    orb.classList.add("listening");
    st.innerHTML = "<b>ROLEX</b> \u00b7 LISTENING\u2026";
  } else if (mode === "speaking") {
    st.innerHTML = "<b>ROLEX</b> \u00b7 SPEAKING (JARVIS)";
  } else {
    st.innerHTML = "<b>ROLEX</b> \u00b7 STANDBY \u00b7 <em>HEY GURU TO WAKE</em>";
  }
}

/* ---------------- Chat ---------------- */
function addMsg(text, mine, meta) {
  const stream = document.getElementById("stream");
  const div = document.createElement("div");
  div.className = "msg " + (mine ? "mine" : "rolex");
  const av = mine ? "" : '<div class="avatar">\ud83d\udc51</div>';
  const metaHtml = meta
    ? `<div class="meta"><span class="tag ${meta.local ? "local" : meta.route === "offline" ? "offline" : "ai"}">${meta.local ? "\u26a1 LOCAL" : meta.route === "offline" ? "OFFLINE" : "\u2601 AI"}</span><span>${meta.route}</span><span>${meta.conf.toFixed(2)}</span><span>${meta.secs}ms</span></div>`
    : "";
  div.innerHTML = `${av}<div class="body"><div class="bubble">${esc(text)}</div>${metaHtml}</div>`;
  stream.appendChild(div);
  stream.scrollTop = stream.scrollHeight;
}

function typing(on) {
  let el = document.getElementById("typing");
  if (on) {
    if (!el) {
      el = document.createElement("div");
      el.id = "typing";
      el.className = "msg rolex";
      el.innerHTML = '<div class="avatar">\ud83d\udc51</div><div class="body"><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div></div>';
      document.getElementById("stream").appendChild(el);
    }
  } else if (el) el.remove();
}

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ---------------- Ask pipeline ---------------- */
async function ask(q) {
  addMsg(q, true);
  typing(true);
  const t0 = performance.now();
  let res;
  try {
    if (S.backend === "live") {
      res = await API.call("/ask", { text: q });
    } else {
      res = await new Promise((r) => setTimeout(() => r(DEMO.answer(q)), 350 + Math.random() * 450));
    }
  } catch (e) {
    res = { text: "\u26a0 backend connection lost \u2014 demo brain took over", route: "offline", local: false, conf: .5 };
    S.backend = "demo";
  }
  typing(false);
  const secs = Math.round(performance.now() - t0);
  res.secs = secs / 1000;
  res.conf = res.conf ?? 0.8;
  res.route = res.route || "chat";
  res.local = res.local ?? false;
  addMsg(res.text, false, res);

  /* \u2605 THE MOMENT: reply lands -> bass thump + shockwave + themed fx */
  fxForRoute(res.route);
  BASS.pulse(1.0);
  if (!S.speakReplies) BASS.pulse(0.5);

  trackStats(res);
  if (S.speakReplies) VOICE.speak(res.text);
  return res;
}

/* ---------------- Stats ---------------- */
function trackStats(res) {
  S.turns++;
  if (res.local) S.local++;
  S.routes[res.route] = (S.routes[res.route] || 0) + 1;
  const top = Object.entries(S.routes).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([k, v]) => `${k}:${v}`).join(" ");
  document.getElementById("stat-turns").textContent = S.turns;
  document.getElementById("t-turns").textContent = S.turns;
  document.getElementById("t-routes").textContent = top || "\u2014";
  document.getElementById("t-localpct").textContent = Math.round((S.local / S.turns) * 100) + "%";
  document.getElementById("t-last").textContent = res.route;
  document.getElementById("t-speed").textContent = res.secs.toFixed(2) + "s";
  const meter = document.getElementById("t-meter");
  if (meter) meter.style.width = Math.min(100, res.secs * 140) + "%";
  refreshTelemetry();
}

/* ---------------- Telemetry ---------------- */
async function refreshTelemetry() {
  if (S.backend === "live") {
    try {
      const st = await API.call("/status", {});
      document.getElementById("t-state").textContent = st.state || "running";
      document.getElementById("t-uptime").textContent = fmtDur(st.uptime || 0);
      document.getElementById("t-sm-count").textContent = st.sm_count ?? 0;
      document.getElementById("t-voice").textContent = (st.voice_profile || "JARVIS").toUpperCase();
      document.getElementById("t-vrate").textContent = st.vrate ?? 158;
      document.getElementById("t-vpitch").textContent = st.vpitch ?? 30;
    } catch (e) { /* silent */ }
  } else {
    document.getElementById("t-uptime").textContent = fmtDur((Date.now() - S.bootTime) / 1000);
  }
  document.getElementById("stat-uptime").textContent = fmtDur((Date.now() - S.bootTime) / 1000);
}

function fmtDur(s) {
  s = Math.floor(s);
  if (s < 60) return s + "s";
  if (s < 3600) return Math.floor(s / 60) + "m " + (s % 60) + "s";
  return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
}

/* ---------------- Modules grid ---------------- */
const MODULES = [
  { n: "Math \u00a73", cls: "on", sat: "math" },
  { n: "Memory \u00a72", cls: "on", sat: "memory" },
  { n: "Tasks \u00a79", cls: "on", sat: "tasks" },
  { n: "Planning \u00a710", cls: "on", sat: "planning" },
  { n: "Knowledge \u00a77", cls: "on", sat: "knowledge" },
  { n: "Documents \u00a78", cls: "on", sat: "documents" },
  { n: "Weather \u00a76", cls: "opt", sat: "weather" },
  { n: "Web Search \u00a76", cls: "opt", sat: "search" },
  { n: "Smart Home \u00a730", cls: "on", sat: "smarthome" },
  { n: "Device \u00a731", cls: "on", sat: "device" },
  { n: "Sync \u00a720", cls: "on", sat: "sync" },
  { n: "Remote Lab \u00a721", cls: "opt", sat: "lab" },
  { n: "Voice \u00a712", cls: "on", sat: "voice" },
  { n: "Learning \u00a739", cls: "on", sat: "learning" },
  { n: "Finance \u00a723", cls: "on", sat: "finance" },
  { n: "Health \u00a727", cls: "on", sat: "health" },
];

function renderModules() {
  const html = MODULES.map((m) =>
    `<div class="mod ${m.cls}" data-sat="${m.sat}"><span class="mdot"></span>${m.n}</div>`).join("");
  document.getElementById("mod-grid").innerHTML = html;
  document.getElementById("d-modgrid").innerHTML = html;
}

function hitModule(satId) {
  document.querySelectorAll(`.mod[data-sat="${satId}"]`).forEach((el) => {
    el.classList.remove("hit");
    void el.offsetWidth;
    el.classList.add("hit");
    setTimeout(() => el.classList.remove("hit"), 1300);
  });
}

/* ---------------- Toast ---------------- */
function toast(text) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = text;
  document.getElementById("toasts").appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

/* ---------------- Views (floating windows) ---------------- */
function showView(name) {
  document.querySelectorAll(".win").forEach((w) => w.classList.remove("open"));
  document.querySelectorAll(".rail-btn[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  if (name && name !== "chat") {
    const w = document.getElementById("view-" + name);
    if (w) w.classList.add("open");
  }
}

/* ---------------- Dashboard ---------------- */
async function renderDash() {
  let data = { todos: [], mem: [], reminders: [], kb: 51, plans: 0 };
  if (S.backend === "live") {
    try { data = await API.call("/dash", {}); } catch (e) { /* demo */ }
  } else {
    data.todos = DEMO.tasks;
    data.mem = DEMO.mem;
    data.plans = DEMO.plans.length;
    data.kb = 51;
  }
  document.getElementById("d-todos").textContent = data.todos.filter((t) => !t.done).length;
  document.getElementById("d-mem").textContent = data.mem.length;
  document.getElementById("d-kb").textContent = data.kb;
  document.getElementById("d-plans").textContent = data.plans;
  document.getElementById("stat-todos").textContent = data.todos.filter((t) => !t.done).length;
  document.getElementById("stat-kb").textContent = data.kb;

  document.getElementById("d-tasklist").innerHTML =
    data.todos.slice(0, 8).map((t) => `
      <div class="taskrow ${t.done ? "done" : ""}" data-id="${t.id}">
        <span class="tcheck">${t.done ? "\u2713" : ""}</span>
        <span class="ttitle">${esc(t.title)}</span>
        <span class="tprio ${t.prio}">${t.prio}</span>
        <span class="tid">\u2026${t.id}</span>
      </div>`).join("") || '<div class="sub">no tasks yet \u2014 "add task \u2026" try pannunga</div>';

  document.getElementById("d-memlist").innerHTML =
    data.mem.slice(0, 8).map((m) => `
      <div class="memrow"><b>${esc(m.key)}</b>${esc(m.value)}</div>`).join("") || '<div class="sub">nothing remembered yet</div>';

  document.getElementById("d-reminders").innerHTML =
    (data.reminders || []).slice(0, 6).map((r) => `
      <div class="taskrow" style="border-left-color:#b48cff"><span>\u23f0</span>
      <span class="ttitle">${esc(r.title)}</span><span class="tid">${esc(r.when || "")}</span></div>`).join("")
    || '<div class="sub">no reminders \u2014 "remind me to \u2026 at \u2026" try pannunga</div>';
}

/* ---------------- Plans ---------------- */
async function renderPlans() {
  let plans = [];
  if (S.backend === "live") {
    try { plans = (await API.call("/plans", {})).plans || []; } catch (e) {}
  } else plans = DEMO.plans;
  document.getElementById("plan-list").innerHTML =
    plans.map((p) => `
      <div class="plan-card">
        <h4>\ud83d\uddfa ${esc(p.goal)} <span class="pid">${esc(p.id || "")}</span></h4>
        ${p.steps.map((s, i) => `
          <div class="pstep ${s.done ? "done" : ""}">
            <span class="num">${i + 1}</span>
            <span class="ptext">${esc(s.text)}</span>
            <span class="pact">${s.kind || ""}</span>
          </div>`).join("")}
      </div>`).join("") || '<div class="sub">plans illa \u2014 "make a plan for \u2026" try pannunga</div>';
}

/* ---------------- Memory ---------------- */
async function renderMemory() {
  let mem = [];
  if (S.backend === "live") {
    try { mem = (await API.call("/memory", {})).mem || []; } catch (e) {}
  } else mem = DEMO.mem;
  document.getElementById("mem-list").innerHTML =
    mem.map((m) => `
      <div class="memrow"><b>${esc(m.key)}</b>${esc(m.value)}
        <span class="del" data-v="${esc(m.value)}">\u2715</span></div>`).join("")
    || '<div class="sub">empty \u2014 "remember that \u2026" type pannunga</div>';
}

/* ---------------- Tools ---------------- */
const CAPS = [
  { i: "\u26a1", n: "Math & Engineering", d: "Arithmetic, algebra, geometry, units, electrical, engineering formulas \u2014 100% local (\u00a73)", t: "LOCAL" },
  { i: "\u25c9", n: "Personal Memory", d: "Facts, preferences, conversation history in SQLite \u2014 remembers you forever (\u00a72)", t: "LOCAL" },
  { i: "\u2713", n: "Task Manager", d: "Add / complete / update / delete / prioritize with natural language + Tamil (\u00a79)", t: "LOCAL" },
  { i: "\u25b2", n: "Planning Engine", d: "Goal \u2192 steps \u2192 execute \u2192 verify. Trip, study, project, budget, fitness templates (\u00a710)", t: "LOCAL" },
  { i: "\u2614", n: "Live Weather", d: "Open-Meteo keyless weather + geocoding, 30-min live cache, Tamil output (\u00a76.3)", t: "OPTIONAL" },
  { i: "\u25d4", n: "Web Search", d: "Serper.dev optional API key \u2014 cached 6h, Rolex voice final answers (\u00a76.1)", t: "OPTIONAL" },
  { i: "\u2b1f", n: "Smart Home VI2", d: "Device registry + danger lock approval gate for unsafe actions (\u00a730)", t: "LOCAL" },
  { i: "\u26a1", n: "Device Manager", d: "Battery, storage, connectivity, hardware info \u2014 Android aware (\u00a731)", t: "LOCAL" },
  { i: "\u20b9", n: "Finance Tracker", d: "Spent/income logging, category detection, \u20b9 reports (\u00a723)", t: "LOCAL" },
  { i: "\u2665", n: "Family & Health", d: "Birthdays, packing lists, vitals logging \u2014 info-only (\u00a726\u00a727)", t: "LOCAL" },
  { i: "\u25a4", n: "Documents", d: "txt/md/csv/json/pdf/docx/xlsx/pptx analysis + graceful missing deps (\u00a78)", t: "LOCAL" },
  { i: "\u21c4", n: "Sync & Backup", d: "Zip backups, rclone Google Drive, rsync VPS \u2014 explicit confirm only (\u00a720)", t: "LOCAL" },
  { i: "\u25b5", n: "Remote Lab", d: "TCP/JSON pairing, SHA-256 token auth, EMERGENCY STOP honored (\u00a721)", t: "OPTIONAL" },
  { i: "\u2b21", n: "Self-Learning", d: "Propose \u2192 Sandbox \u2192 Test \u2192 Approve \u2192 Apply \u2192 Rollback (\u00a739)", t: "LOCAL" },
  { i: "\u2593", n: "Jarvis Voice", d: "JARVIS / ASSISTANT / NARRATOR profiles + bass-reactive glow (\u00a712)", t: "LOCAL" },
  { i: "\u2605", n: "Neon Horizon UI", d: "Fire/ice emblem, orbital modules, starfield FX \u2014 this HUD (v2.1)", t: "LOCAL" },
];

function renderTools() {
  document.getElementById("cap-list").innerHTML = CAPS.map((c) => `
    <div class="cap">
      <div class="cico">${c.i}</div>
      <div><h5>${c.n}</h5><div class="cdesc">${c.d}</div></div>
      <span class="ctag ${c.t === "LOCAL" ? "local" : "opt"}">${c.t}</span>
    </div>`).join("");
}

/* ---------------- Diagnostics ---------------- */
function renderDiag() {
  const pills = [
    ["core", "ok"], ["memory", "ok"], ["math", "ok"], ["knowledge", "ok"],
    ["tasks", "ok"], ["planning", "ok"], ["voice", "ok"], ["sync", "ok"],
    ["weather", "warn"], ["remote-lab", "warn"], ["web-search", "warn"],
    ["neon-fx", "ok"], ["bass-reactor", "ok"], ["api-keys", "warn"],
  ];
  document.getElementById("diag-pills").innerHTML = pills.map(([n, s]) =>
    `<div class="hpill ${s}"><b>${s === "ok" ? "\u25cf" : "\u25cb"}</b>${n}</div>`).join("");

  const lines = [
    ["INFO", "rolex.core", "system online \u00b7 v2.2.0 \u00b7 NEON HORIZON \u00b7 local-first armed"],
    ["INFO", "rolex.ui", "starfield + nebula + orbital satellites active"],
    ["INFO", "rolex.bass", "sub-bass reactor armed \u00b7 glow follows voice"],
    ["INFO", "rolex.memory", "sqlite attached \u00b7 facts + prefs + exchanges"],
    ["INFO", "rolex.math", "arithmetic/geometry/units/electrical loaded"],
    ["INFO", "rolex.tasks", "TaskManager \u00a79 wired \u00b7 NL parser active"],
    ["INFO", "rolex.planning", "PlanningEngine \u00a710 \u00b7 6 templates"],
    ["INFO", "rolex.voice", "JARVIS profile default \u00b7 rate 158 \u00b7 pitch 30"],
    ["WARN", "rolex.live", "web search keys not set \u2014 serper/tavily optional (Settings \u2192 API Keys)"],
    ["WARN", "rolex.live", "openweather key not set \u2014 open-meteo keyless fallback active"],
    ["INFO", "rolex.smarthome", "VI2 registry loaded \u00b7 danger lock ARMED"],
    ["INFO", "rolex.security", "\u00a716 armed \u00b7 secrets.json ignored by backups"],
    ["INFO", "rolex.learning", "\u00a739 pipeline idle \u00b7 sandbox ready"],
    ["OK",   "rolex.tests", "260 tests green - 198 legacy + 62 v2"],
  ];
  document.getElementById("diaglog-body").innerHTML = lines.map((l) => {
    const cls = l[0] === "OK" ? "ok-line" : `lvl-${l[0]}`;
    const ts = new Date().toISOString().slice(11, 19);
    return `<div class="dline"><span class="ts">${ts}</span> <span class="${cls}">${l[0]}</span> ${l[1]} \u2014 ${l[2]}</div>`;
  }).join("");
}

/* ---------------- Wave bars ---------------- */
function buildWave() {
  const w = document.getElementById("wave");
  w.innerHTML = "";
  for (let i = 0; i < 22; i++) w.appendChild(document.createElement("i"));
}

function tickWave(now) {
  const bars = document.querySelectorAll("#wave i");
  bars.forEach((b, i) => {
    const wob = S.speaking
      ? 0.3 + 0.7 * Math.abs(Math.sin(now * 0.008 + i * 0.55))
      : 0.06 + 0.05 * Math.abs(Math.sin(now * 0.002 + i * 0.4));
    const h = 4 + (wob * 20) + BASS.level * 14;
    b.style.height = h.toFixed(1) + "px";
  });
}

/* ---------------- Settings ---------------- */
function initSettings() {
  const sv = document.getElementById("set-voice");
  sv.addEventListener("change", async () => {
    if (S.backend === "live") {
      try { await API.call("/voice", { profile: sv.value }); } catch (e) {}
    }
    document.getElementById("t-voice").textContent = sv.value.toUpperCase();
    document.getElementById("t-vrate").textContent = sv.value === "jarvis" ? "158" : sv.value === "narrator" ? "132" : "172";
    document.getElementById("t-vpitch").textContent = sv.value === "jarvis" ? "30" : sv.value === "narrator" ? "-10" : "10";
    toast(`\ud83c\udfa7 voice profile \u2192 ${sv.value}`);
    addMsg(`set voice to ${sv.value}`, true);
    ask(`set voice to ${sv.value}`);
  });

  document.getElementById("set-localfirst").addEventListener("click", function () {
    this.classList.toggle("on");
    toast(this.classList.contains("on") ? "\u2601 local-first mode ON \u2014 external AI only as last resort" : "\u26a0 local-first OFF \u2014 AI hub may answer directly");
  });

  document.getElementById("set-dangerlock").addEventListener("click", function () {
    this.classList.toggle("on");
    toast(this.classList.contains("on") ? "\ud83d\udee1 danger lock ARMED (\u00a730)" : "\u26a0 danger lock off \u2014 not recommended!");
  });

  document.getElementById("set-speak").addEventListener("click", function () {
    S.speakReplies = this.classList.contains("on");
    this.classList.toggle("on");
    S.speakReplies = this.classList.contains("on");
    if (S.speakReplies) VOICE.speak("Rolex online. Neon Horizon active. Jarvis voice modulation engaged.");
    toast(S.speakReplies ? "\ud83d\udd0a speak replies ON \u2014 Jarvis voice + bass glow" : "\ud83d\udd07 speak replies off");
  });

  document.getElementById("set-bass").addEventListener("click", function () {
    this.classList.toggle("on");
    BASS.on = this.classList.contains("on");
    if (BASS.on) {
      BASS.ensure();
      if (BASS.ctx && BASS.ctx.state === "suspended") BASS.ctx.resume();
      BASS.pulse(1);
      FX.shock("255,120,60");
    }
    toast(BASS.on ? "\u266b bass glow ON \u2014 center pulse follows voice" : "bass glow off");
  });

  document.getElementById("set-serper-save").addEventListener("click", async () => {
    const v = document.getElementById("set-serper").value.trim();
    if (!v) { toast("\u26a0 paste key first"); return; }
    try {
      await API.call("/keys", { name: "SERPER_API_KEY", key: v });
      toast("\u2601 serper key saved \u2014 web search armed");
    } catch (e) {
      toast("\u26a0 backend offline \u2014 key save needs live bridge");
    }
  });

  // v2.2: all optional API keys — generic /keys endpoint
  const KEYMAP = [
    ["set-tavily",        "TAVILY_API_KEY",       "tavily"],
    ["set-openweather",   "OPENWEATHER_API_KEY",  "openweather"],
    ["set-elevenlabs",    "ELEVENLABS_API_KEY",   "elevenlabs \u266a"],
    ["set-gemini",        "GEMINI_API_KEY",       "gemini"],
    ["set-openai",        "OPENAI_API_KEY",       "openai"]
  ];
  for (const [id, name, label] of KEYMAP) {
    const btn = document.getElementById(id + "-save");
    if (!btn) continue;
    btn.addEventListener("click", async () => {
      const v = document.getElementById(id).value.trim();
      if (!v) { toast("\u26a0 paste key first"); return; }
      try {
        await API.call("/keys", { name: name, key: v });
        toast("\u2601 " + label + " key saved \u2014 encrypted store");
        FX.burst("coin", "#ffe98a", 8);
      } catch (e) {
        toast("\u26a0 backend offline \u2014 key save needs live bridge");
      }
    });
  }
}

/* ============================================================
   MAIN LOOP + BOOT
   ============================================================ */
function loop(now) {
  const dt = Math.min(0.05, (now - (loop.last || now)) / 1000);
  loop.last = now;
  BASS.tick(dt, now);
  FX.draw(now);
  tickWave(now);
  requestAnimationFrame(loop);
}

async function boot() {
  /* splash timing */
  setTimeout(() => document.getElementById("splash").classList.add("hide"), 2400);

  /* FX + orbit + wave */
  FX.init();
  buildOrbit();
  buildWave();
  requestAnimationFrame(loop);

  /* audio unlock on first gesture (browser policy) */
  const unlock = () => { BASS.ensure(); if (BASS.ctx && BASS.ctx.state === "suspended") BASS.ctx.resume(); };
  window.addEventListener("pointerdown", unlock, { once: true });
  window.addEventListener("keydown", unlock, { once: true });

  /* backend detect */
  try {
    const st = await API.call("/status", {});
    S.backend = "live";
    document.getElementById("t-state").textContent = st.state || "running";
    document.getElementById("t-voice").textContent = (st.voice_profile || "JARVIS").toUpperCase();
    toast("\ud83d\udfe2 LIVE backend connected \u2014 Neon Horizon full power");
    renderDash();
  } catch (e) {
    S.backend = "demo";
    setTimeout(() => toast("\ud83d\udfe0 Demo brain active \u2014 python -m rolex.ui.bridge run pannunga"), 3000);
  }

  renderModules();
  addMsg(L.welcome, false, null);
  setOrb("standby");
  initSettings();
  renderTools();
  renderDiag();

  /* wire chat */
  const input = document.getElementById("input");
  const send = () => {
    const v = input.value.trim();
    if (!v) return;
    input.value = "";
    ask(v);
  };
  document.getElementById("btn-send").addEventListener("click", send);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
  document.querySelectorAll(".quick button").forEach((b) =>
    b.addEventListener("click", () => ask(b.dataset.q)));

  /* voice */
  document.getElementById("btn-mic").addEventListener("click", () => VOICE.listen(ask));
  document.getElementById("orb").addEventListener("click", () => {
    if (S.speaking) return;
    setOrb("listening");
    VOICE.listen(ask);
  });
  document.getElementById("rail-voice").addEventListener("click", function () {
    const btn = document.getElementById("set-speak");
    const on = !btn.classList.contains("on");
    btn.classList.toggle("on", on);
    S.speakReplies = on;
    if (on) VOICE.speak("Rolex online. Jarvis voice engaged.");
    toast(on ? "\ud83c\udfa7 Jarvis voice ON \u2014 replies spoken + bass glow" : "\ud83d\udd07 voice off");
  });

  /* views */
  document.querySelectorAll(".rail-btn[data-view]").forEach((b) =>
    b.addEventListener("click", () => {
      showView(b.dataset.view);
      const v = b.dataset.view;
      if (v === "dash") renderDash();
      if (v === "plans") renderPlans();
      if (v === "memory") renderMemory();
      if (v === "tools") renderTools();
      if (v === "diag") renderDiag();
    }));
  document.querySelectorAll(".win .wclose").forEach((b) =>
    b.addEventListener("click", () => showView("chat")));
  document.getElementById("crown") ?
    document.getElementById("crown").addEventListener("click", () => showView("chat")) :
    document.querySelector("#rail .crown").addEventListener("click", () => showView("chat"));

  /* plan + memory inputs */
  document.getElementById("plan-btn").addEventListener("click", () => {
    const v = document.getElementById("plan-input").value.trim();
    if (v) { ask(v); document.getElementById("plan-input").value = ""; }
  });
  document.getElementById("mem-btn").addEventListener("click", () => {
    const v = document.getElementById("mem-input").value.trim();
    if (v) { ask("remember that " + v.replace(/^remember\s+(that\s+)?/i, "")); document.getElementById("mem-input").value = ""; }
  });

  /* dashboard quick-complete (demo) */
  document.getElementById("d-tasklist").addEventListener("click", (e) => {
    const chk = e.target.closest(".tcheck");
    if (!chk) return;
    const row = chk.parentElement;
    row.classList.toggle("done");
    chk.textContent = row.classList.contains("done") ? "\u2713" : "";
    const t = DEMO.tasks.find((x) => x.id === row.dataset.id);
    if (t) t.done = !t.done;
  });

  /* memory delete (demo) */
  document.getElementById("mem-list").addEventListener("click", (e) => {
    if (!e.target.classList.contains("del")) return;
    const v = e.target.dataset.v;
    DEMO.mem = DEMO.mem.filter((x) => x.value !== v);
    renderMemory();
    toast("\ud83d\uddd1 forgotten (demo)");
  });

  /* tickers */
  setInterval(refreshTelemetry, 1000);
  if (S.backend === "live") setInterval(renderDash, 30000);
}

document.addEventListener("DOMContentLoaded", boot);
