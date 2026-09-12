"""Rolex Life Modules (v2 §23–29) — personal life intelligence.

All local-first: SQLite storage + pure-python logic + natural language.
Optional AI/web only when explicitly asked (never automatic).

Modules:
  • FinanceTracker  (§23) — expenses, income, budget, reports
  • BusinessAssistant (§24) — business plans, docs, analysis
  • TravelAssistant (§25) — trips, itinerary, checklists
  • FamilyAssistant (§26) — events, important dates, shared plans
  • HealthVault     (§27) — records, reminders (info-only, no medical advice)
  • CommsAssistant  (§29) — drafts messages, never auto-sends
"""
from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("life")


class LifeError(RolexError):
    code = "LIFE_ERROR"


def _connect(db: str) -> sqlite3.Connection:
    p = Path(db)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _money(v: float) -> str:
    return f"₹{v:,.2f}"


# ==========================================================================
# §23 FINANCE
# ==========================================================================
class FinanceTracker:
    """Expense/income tracking + budget + monthly report (SQLite)."""

    def __init__(self, db_path: str | None = None):
        self.db = str(db_path or CONFIG.DATA_DIR / "rolex_life.db")
        with _connect(self.db) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS finance_tx (
                id TEXT PRIMARY KEY, kind TEXT, amount REAL,
                category TEXT, note TEXT, ts REAL)""")

    def add(self, kind: str, amount: float, category: str = "general",
            note: str = "") -> dict:
        if kind not in ("expense", "income"):
            raise LifeError("kind must be expense|income")
        if amount <= 0:
            raise LifeError("amount must be > 0")
        tid = uuid.uuid4().hex[:8]
        with _connect(self.db) as c:
            c.execute("INSERT INTO finance_tx VALUES (?,?,?,?,?,?)",
                      (tid, kind, round(float(amount), 2),
                       category or "general", note, time.time()))
        return {"id": tid, "kind": kind, "amount": amount,
                "category": category, "note": note}

    def summary(self, days: int = 30) -> dict:
        since = time.time() - days * 86400
        with _connect(self.db) as c:
            rows = c.execute(
                "SELECT * FROM finance_tx WHERE ts>=? ORDER BY ts DESC",
                (since,)).fetchall()
        exp = sum(r["amount"] for r in rows if r["kind"] == "expense")
        inc = sum(r["amount"] for r in rows if r["kind"] == "income")
        cats: dict[str, float] = {}
        for r in rows:
            if r["kind"] == "expense":
                cats[r["category"]] = cats.get(r["category"], 0) + r["amount"]
        return {"days": days, "tx": len(rows), "income": round(inc, 2),
                "expense": round(exp, 2),
                "balance": round(inc - exp, 2),
                "top_categories": sorted(cats.items(), key=lambda x: -x[1])[:5]}

    def report(self, days: int = 30) -> str:
        s = self.summary(days)
        lines = [f"💰 Rolex Finance · last {s['days']} days"]
        lines.append(f"   income  : {_money(s['income'])}")
        lines.append(f"   expense : {_money(s['expense'])}")
        lines.append(f"   balance : {_money(s['balance'])}")
        for cat, amt in s["top_categories"]:
            lines.append(f"   · {cat}: {_money(amt)}")
        if not s["tx"]:
            lines.append("   (no entries yet — 'spent 250 on food' என்று சொல்லுங்கள்)")
        return "\n".join(lines)

    # ------------------------------------------------- natural language
    _RE_SPENT = re.compile(
        r"^(?:i\s+)?(?:spent|spend|paid|kuduthirukken|செலவு|செலவிட்டேன்)\s+"
        r"(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)\s*(?:on|for|க்கு)?\s*(.*)$", re.I)
    _RE_GOT = re.compile(
        r"^(?:i\s+)?(?:got|received|earned|income|salary|varavu|வரவு|"
        r"வாங்கினேன்)\s+(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)\s*(?:from|for|க்கு)?\s*(.*)$", re.I)
    _RE_REPORT = re.compile(
        r"^(?:finance|expense|budget|money)?\s*report\b(.*)$", re.I)

    def parse_command(self, text: str) -> str:
        t = (text or "").strip()
        low = t.lower()
        m = self._RE_SPENT.match(low)
        if m and m.group(1):
            amt = float(m.group(1))
            cat = self._guess_category(m.group(2) or "general")
            self.add("expense", amt, cat, note=t[:80])
            return f"📉 செலவு பதிவு · spent {_money(amt)} on {cat}"
        m = self._RE_GOT.match(low)
        if m and m.group(1):
            amt = float(m.group(1))
            cat = self._guess_category(m.group(2) or "income")
            self.add("income", amt, cat, note=t[:80])
            return f"📈 வரவு பதிவு · income {_money(amt)} ({cat})"
        m = self._RE_REPORT.match(low)
        if m:
            days = 30
            mm = re.search(r"(\d+)\s*(day|days|month|months)", m.group(1) or "")
            if mm:
                n = int(mm.group(1))
                days = n * 30 if "month" in mm.group(2) else n
            return self.report(days)
        if re.search(r"\b(balance|how much (do )?i (have|spent)|"
                     r"இருப்பு|எவ்வளவு செலவு)\b", low):
            return self.report(30)
        return ""

    @staticmethod
    def _guess_category(text: str) -> str:
        t = (text or "").lower()
        cats = {
            "food": ["food", "lunch", "dinner", "hotel", "coffee", "tea",
                     "snack", "saapadu", "சாப்பாடு", "உணவு"],
            "travel": ["travel", "bus", "train", "petrol", "fuel", "uber",
                       "ola", "auto", "பயணம்", "பெட்ரோல்"],
            "shopping": ["shopping", "amazon", "flipkart", "clothes",
                         "dress", "ஷாப்பிங்", "ஆடை"],
            "bills": ["bill", "electricity", "eb bill", "water", "mobile",
                      "recharge", "internet", "wifi", "broadband", "பில்"],
            "health": ["medicine", "doctor", "hospital", "clinic",
                       "மருத்துவம்", "மருந்து"],
            "education": ["book", "course", "fee", "tuition", "exam",
                          "புத்தகம்", "கட்டணம்"],
            "entertainment": ["movie", "game", "netflix", "music",
                              "சினிமா", "படம்"],
            "home": ["rent", "grocery", "vegetables", "milk", "house",
                     "வீட்டு", "காய்கறி", "பால்"],
            "gift": ["gift", "present", "பரிசு"],
            "income": ["salary", "wage", "freelance", "bonus", "interest",
                       "சம்பளம்", "வரவு"],
        }
        for cat, words in cats.items():
            if any(w in t for w in words):
                return cat
        return "general"


# ==========================================================================
# §29 COMMUNICATIONS (draft-only, never auto-send)
# ==========================================================================
class CommsAssistant:
    """Message drafts + templates. NEVER sends — permission-first."""

    def __init__(self):
        self.drafts: list[dict] = []

    def draft(self, to: str, message: str, channel: str = "sms") -> dict:
        d = {"id": uuid.uuid4().hex[:8], "to": to, "message": message,
             "channel": channel, "ts": time.time(), "status": "draft"}
        self.drafts.append(d)
        return d

    def list(self) -> str:
        if not self.drafts:
            return "✉️ drafts இல்லை · no drafts (Rolex never sends without permission)"
        lines = ["✉️ Rolex Drafts (auto-send இல்லை — permission required):"]
        for d in self.drafts[-10:]:
            lines.append(f"  [{d['id']}] {d['channel']}→{d['to']}: "
                         f"{d['message'][:60]}")
        return "\n".join(lines)

    _RE_DRAFT = re.compile(
        r"^(?:draft|write|compose)\s+(?:a\s+)?(?:message|msg|sms|whatsapp|"
        r"mail|email)\s+(?:to|for)\s+(\S+)\s*(?:saying|about|:)?\s*(.*)$",
        re.I)

    def parse_command(self, text: str) -> str:
        m = self._RE_DRAFT.match((text or "").strip())
        if not m:
            if re.search(r"\b(show|list).*(drafts?)\b", (text or "").lower()):
                return self.list()
            return ""
        to, msg = m.group(1).strip(), (m.group(2) or "").strip()
        if not msg:
            return "✉️ message content சொல்லுங்கள் · what should it say?"
        d = self.draft(to, msg, channel="sms")
        return (f"✉️ draft ready [{d['id']}] → {to}: \"{msg}\"\n"
                f"   ⚠️ Rolex auto-send பண்ணாது — permission வேண்டும்.")


# ==========================================================================
# §26 FAMILY
# ==========================================================================
class FamilyAssistant:
    """Events, important dates, birthday/anniversary reminders."""

    def __init__(self, db_path: str | None = None):
        self.db = str(db_path or CONFIG.DATA_DIR / "rolex_life.db")
        with _connect(self.db) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS family_events (
                id TEXT PRIMARY KEY, person TEXT, event TEXT, date TEXT,
                note TEXT, ts REAL)""")

    def add(self, person: str, event: str, date: str, note: str = "") -> dict:
        if not re.match(r"\d{4}-\d{2}-\d{2}", (date or "").strip()):
            raise LifeError(f"date must be YYYY-MM-DD, got: {date}")
        eid = uuid.uuid4().hex[:8]
        with _connect(self.db) as c:
            c.execute("INSERT INTO family_events VALUES (?,?,?,?,?,?)",
                      (eid, person, event, date, note, time.time()))
        return {"id": eid, "person": person, "event": event,
                "date": date, "note": note}

    def upcoming(self, days: int = 60) -> list[dict]:
        rows = []
        with _connect(self.db) as c:
            for r in c.execute("SELECT * FROM family_events "
                               "ORDER BY date").fetchall():
                rows.append(dict(r))
        today = datetime.now().date()
        out = []
        for r in rows:
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            except Exception:                                   # noqa: BLE001
                continue
            # yearly events (birthday) — shift year
            try:
                anniv = d.replace(year=today.year)
                if anniv < today:
                    anniv = d.replace(year=today.year + 1)
                r2 = dict(r); r2["days_left"] = (anniv - today).days
                r2["date"] = anniv.strftime("%Y-%m-%d")
                out.append(r2)
            except Exception:                                   # noqa: BLE001
                continue
        return sorted([x for x in out if x["days_left"] <= days],
                      key=lambda x: x["days_left"])

    def report(self, days: int = 60) -> str:
        ups = self.upcoming(days)
        all_ups = self.upcoming(days=36500)   # everything, for "next" line
        if not all_ups:
            return ("👨‍👩‍👧 family events இல்லை — 'amma birthday 1975-06-10' "
                    "என்று சேர்க்கலாம்.")
        lines = [f"👨‍👩‍👧 Rolex Family · next {days} days"]
        for r in ups:
            lines.append(f"   {r['date']} ({r['days_left']}d) · "
                         f"{r['person']}'s {r['event']}")
        if not ups and all_ups:
            nxt = all_ups[0]
            lines.append(f"   (next: {nxt['person']}'s {nxt['event']} "
                         f"{nxt['date']} — {nxt['days_left']} days away)")
        return "\n".join(lines)

    _RE_ADD = re.compile(
        r"^(?:(\w+)'s)\s+(birthday|anniversary|wedding|event|reminder)\s+"
        r"(\d{4}-\d{2}-\d{2})\s*(.*)$", re.I)
    _RE_LIST = re.compile(r"^(?:family|events)\s*(?:list|upcoming)?\b.*$",
                          re.I)

    def parse_command(self, text: str) -> str:
        t = (text or "").strip()
        m = self._RE_ADD.match(t)
        if m:
            person, event, date, note = (m.group(1), m.group(2).lower(),
                                         m.group(3), (m.group(4) or "").strip())
            self.add(person, event, date, note)
            return (f"🎂 family event saved: {person}'s {event} on {date}")
        if self._RE_LIST.match(t.lower()):
            return self.report()
        return ""


# ==========================================================================
# §25 TRAVEL
# ==========================================================================
class TravelAssistant:
    """Trip checklists + itinerary storage (planning engine does steps)."""

    _PACK_BASE = [
        "ID / Aadhaar / tickets", "phone + charger", "power bank",
        "medicines + first aid", "clothes (days + 1)", "toothbrush kit",
        "cash + cards", "water bottle",
    ]

    def __init__(self, db_path: str | None = None):
        self.db = str(db_path or CONFIG.DATA_DIR / "rolex_life.db")
        with _connect(self.db) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY, name TEXT, place TEXT, days INTEGER,
                budget REAL, notes TEXT, ts REAL)""")

    def new_trip(self, name: str, place: str, days: int = 3,
                 budget: float = 0.0, notes: str = "") -> dict:
        tid = uuid.uuid4().hex[:8]
        with _connect(self.db) as c:
            c.execute("INSERT INTO trips VALUES (?,?,?,?,?,?,?)",
                      (tid, name, place, days, budget, notes, time.time()))
        return {"id": tid, "name": name, "place": place, "days": days,
                "budget": budget}

    def pack_list(self, extra: list[str] | None = None) -> list[str]:
        return self._PACK_BASE + list(extra or [])

    def report(self) -> str:
        with _connect(self.db) as c:
            rows = c.execute("SELECT * FROM trips ORDER BY ts DESC "
                             "LIMIT 5").fetchall()
        if not rows:
            return "✈️ trips இல்லை · 'plan a trip to ooty' என்று கேளுங்கள்."
        lines = ["✈️ Rolex Trips:"]
        for r in rows:
            lines.append(f"   [{r['id']}] {r['name']} @ {r['place']} · "
                         f"{r['days']}d · ₹{r['budget'] or 0}")
        return "\n".join(lines)

    _RE_PACK = re.compile(r"\b(packing|pack)\s*(list)?\b", re.I)
    _RE_TRIPS = re.compile(r"^(?:my\s+)?(?:trips?|travel)\s*(?:list)?\b.*$",
                           re.I)

    def parse_command(self, text: str) -> str:
        low = (text or "").lower()
        if self._RE_PACK.search(low):
            items = self.pack_list()
            return ("🎒 Rolex Packing List:\n   "
                    + "\n   ".join(f"○ {i}" for i in items))
        if self._RE_TRIPS.match(low):
            return self.report()
        return ""


# ==========================================================================
# §27 HEALTH (information-only vault)
# ==========================================================================
class HealthVault:
    """Records + reminders — INFORMATION ONLY, never medical advice."""

    def __init__(self, db_path: str | None = None):
        self.db = str(db_path or CONFIG.DATA_DIR / "rolex_life.db")
        with _connect(self.db) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS health_records (
                id TEXT PRIMARY KEY, kind TEXT, value TEXT, unit TEXT,
                note TEXT, ts REAL)""")

    def add(self, kind: str, value: str, unit: str = "", note: str = "") -> dict:
        hid = uuid.uuid4().hex[:8]
        with _connect(self.db) as c:
            c.execute("INSERT INTO health_records VALUES (?,?,?,?,?,?)",
                      (hid, kind, str(value), unit, note, time.time()))
        return {"id": hid, "kind": kind, "value": value, "unit": unit}

    def log_vitals(self, kind: str, value: float, unit: str) -> dict:
        return self.add(kind, value, unit, note="vitals")

    def report(self) -> str:
        with _connect(self.db) as c:
            rows = c.execute("SELECT * FROM health_records ORDER BY ts DESC "
                             "LIMIT 10").fetchall()
        if not rows:
            return ("❤️ health records இல்லை — 'log weight 72 kg' "
                    "என்று பதிவு செய்யலாம்.")
        lines = ["❤️ Rolex Health Records (info-only, medical advice இல்லை):"]
        for r in rows:
            when = datetime.fromtimestamp(r["ts"]).strftime("%d %b %H:%M")
            lines.append(f"   {when} · {r['kind']}: {r['value']}"
                         f"{r['unit'] or ''}")
        return "\n".join(lines)

    _RE_LOG = re.compile(
        r"^log\s+(weight|bp|sugar|steps|sleep|temp(?:erature)?)\s+"
        r"(\d+(?:\.\d+)?)\s*(kg|lbs|mmhg|mg)?\s*(?:dl)?\s*(.*)$",
        re.I)
    _RE_REPORT = re.compile(r"^(?:my\s+)?health\s*(?:report|records?)?\b.*$",
                            re.I)

    def parse_command(self, text: str) -> str:
        t = (text or "").strip()
        m = self._RE_LOG.match(t)
        if m:
            kind, val, unit = m.group(1).lower(), float(m.group(2)), \
                (m.group(3) or "").lower()
            unit = {"weight": "kg", "sugar": "mg/dL", "bp": "",
                    "steps": "", "sleep": "h", "temp": "°C",
                    "temperature": "°C"}.get(kind, unit)
            self.add(kind, val, unit, note="logged")
            return (f"❤️ logged · {kind}: {val}{unit} "
                    f"(info-only — doctor advice இல்லை)")
        if self._RE_REPORT.match(t.lower()):
            return self.report()
        return ""


# ==========================================================================
# §24 BUSINESS
# ==========================================================================
class BusinessAssistant:
    """Business planning helper — uses PlanningEngine templates + docs."""

    _RE_PLAN = re.compile(
        r"^(?:business|biz)\s+(plan|idea|analysis)\s+(?:for\s+)?(.+)$", re.I)

    def parse_command(self, task: str) -> str:
        m = self._RE_PLAN.match((task or "").strip())
        if not m:
            return ""
        what = m.group(2).strip()
        steps = [
            "ℹ️ Define the customer & problem in one line",
            "ℹ️ List top 3 competitors & their pricing",
            "🔢 Estimate startup cost: assets + licenses + 3-month runway",
            "🔢 Break-even: fixed cost ÷ (price − variable cost)",
            "📋 Register the business & open a bank account",
            "📋 Build v1 offer & test with 5 real customers",
            "🧭 Review weekly: sales, cost, feedback",
        ]
        lines = [f"💼 Rolex Business Plan · {what}"]
        lines += [f"  {i+1}. {s[2:]}" for i, s in enumerate(steps)]
        lines.append("  ─ 'plan " + what + "' என்று கேட்டா planning engine "
                     "முழு tracker தரும்.")
        return "\n".join(lines)


# ==========================================================================
# Package singletons
# ==========================================================================
FINANCE = FinanceTracker()
FAMILY = FamilyAssistant()
TRAVEL = TravelAssistant()
HEALTH = HealthVault()
COMMS = CommsAssistant()
BIZ = BusinessAssistant()


def life_route(text: str) -> str:
    """Try all life modules; first non-empty reply wins. '' = not mine."""
    for mod in (FINANCE, FAMILY, TRAVEL, HEALTH, COMMS, BIZ):
        try:
            out = mod.parse_command(text)
        except Exception as e:                                  # noqa: BLE001
            log.warning("%s parse failed: %s", type(mod).__name__, e)
            continue
        if out:
            return out
    return ""
