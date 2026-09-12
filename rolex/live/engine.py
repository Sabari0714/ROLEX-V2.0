"""Rolex Live Information Engine (v2 §6+§32) — weather + web search.

Local-first policy:
  • Internet = information/tool source, NOT a replacement brain.
  • Every fetch is optional, cached, permission-gated, and failure-safe.
  • No key → feature reports "not configured", never crashes.

Sources:
  • Weather  : Open-Meteo (no API key needed) + geocoding API
  • Web search: SERPER API (optional key)
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("live")


class LiveError(RolexError):
    code = "LIVE_ERROR"


# --------------------------------------------------------------- cache
class LiveCache:
    """SQLite cache — offline fallback + repeated-query saver."""

    TTL = {
        "weather": 30 * 60,          # 30 min
        "search": 24 * 3600,         # 24 h
        "geocode": 7 * 86400,        # 7 days
        "web": 6 * 3600,             # 6 h
    }

    def __init__(self, db_path: str | None = None):
        self.db = Path(db_path or CONFIG.DATA_DIR / "live_cache.db")
        self.db.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._conn() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY, kind TEXT, data TEXT,
                    fetched REAL)""")
        except Exception as e:                                  # noqa: BLE001
            log.warning("cache init: %s", e)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db, timeout=5)
        c.row_factory = sqlite3.Row
        return c

    def get(self, key: str, kind: str, max_age: float | None = None
            ) -> dict | None:
        try:
            with self._conn() as c:
                row = c.execute("SELECT data, fetched FROM cache WHERE key=?",
                                (key,)).fetchone()
            if not row:
                return None
            age = time.time() - (row["fetched"] or 0)
            limit = max_age if max_age is not None else self.TTL.get(kind, 3600)
            if age > limit:
                return None
            return json.loads(row["data"])
        except Exception as e:                                  # noqa: BLE001
            log.debug("cache get: %s", e)
            return None

    def put(self, key: str, kind: str, data: dict) -> None:
        try:
            with self._conn() as c:
                c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
                          (key, kind, json.dumps(data, ensure_ascii=False),
                           time.time()))
        except Exception as e:                                  # noqa: BLE001
            log.debug("cache put: %s", e)

    def stats(self) -> dict:
        try:
            with self._conn() as c:
                n = c.execute("SELECT COUNT(*) n FROM cache").fetchone()["n"]
            return {"entries": n, "db": str(self.db)}
        except Exception:                                       # noqa: BLE001
            return {"entries": 0, "db": str(self.db)}


# ------------------------------------------------------------- weather
class WeatherTool:
    """Weather: OpenWeather (key) OR Open-Meteo (keyless) — same shape.

    v2.2 key chain: OPENWEATHER_API_KEY present → api.openweathermap.org
    (current + 5-day/3h forecast, mapped into the Open-Meteo response
    shape so report() is unchanged). No key → Open-Meteo keyless.
    Both cached; both offline-safe."""

    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FC_URL = "https://api.open-meteo.com/v1/forecast"
    OW_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
    OW_CUR_URL = "https://api.openweathermap.org/data/2.5/weather"
    OW_FC_URL = "https://api.openweathermap.org/data/2.5/forecast"

    # OpenWeather condition id → WMO code (report() describes WMO codes)
    _OW_WMO = {
        200: 95, 201: 95, 202: 96, 210: 95, 211: 95, 212: 96, 221: 95,
        230: 95, 231: 95, 232: 96,
        300: 51, 301: 51, 302: 53, 310: 51, 311: 51, 312: 55, 313: 53,
        314: 55, 321: 53,
        500: 51, 501: 63, 502: 65, 503: 65, 504: 65, 511: 65, 520: 80,
        521: 81, 522: 82, 531: 82,
        600: 71, 601: 71, 602: 73, 611: 71, 612: 71, 613: 71, 615: 71,
        616: 73, 620: 71, 621: 73, 622: 75,
        701: 45, 711: 45, 721: 45, 731: 45, 741: 45, 751: 45, 761: 45,
        762: 45, 771: 45, 781: 95,
        800: 0, 801: 1, 802: 2, 803: 3, 804: 3,
    }

    def __init__(self, cache: LiveCache | None = None, timeout: float = 10.0):
        self.cache = cache or LiveCache()
        self.timeout = timeout

    @property
    def ow_key(self) -> str:
        return os_getenv("OPENWEATHER_API_KEY", "")

    def _ow_wmo(self, ow_id) -> int:
        try:
            return self._OW_WMO.get(int(ow_id), 3)
        except (TypeError, ValueError):
            return 3

    # -- geocoding -----------------------------------------------
    def geocode(self, place: str) -> dict | None:
        if not place or not place.strip():
            return None
        place = place.strip()
        ck = f"geo:{place.lower()}"
        cached = self.cache.get(ck, "geocode")
        if cached:
            return cached
        results = []
        data = None
        # language=en first; Tamil-script names need language=ta fallback
        for lang in ("en", "ta"):
            q = urllib.parse.urlencode({"name": place, "count": 1,
                                        "language": lang, "format": "json"})
            try:
                with urllib.request.urlopen(f"{self.GEO_URL}?{q}",
                                            timeout=self.timeout) as r:
                    data = json.loads(r.read().decode("utf-8"))
            except Exception as e:                              # noqa: BLE001
                log.info("geocode offline: %s", e)
                return None
            results = (data or {}).get("results") or []
            if results:
                break
        if not results:
            return None
        hit = results[0]
        out = {"name": hit.get("name", place),
               "lat": hit.get("latitude"), "lon": hit.get("longitude"),
               "country": hit.get("country", ""),
               "admin": hit.get("admin1", "")}
        self.cache.put(ck, "geocode", out)
        return out

    # -- forecast ------------------------------------------------
    def forecast(self, place: str, days: int = 3) -> dict | None:
        geo = self.geocode(place)
        if geo is None:
            return None
        ck = f"fc:{place.lower()}:{days}"
        cached = self.cache.get(ck, "weather")
        if cached:
            cached["_cached"] = True
            return cached
        # v2.2: OPENWEATHER_API_KEY present → OpenWeather preferred
        out = None
        if self.ow_key:
            out = self._ow_forecast(geo, days)
        if out is None:                        # no key OR openweather failed
            out = self._om_forecast(geo, days)
        if out is None:
            return None
        self.cache.put(ck, "weather", out)
        return out

    # -- openweather (v2.2, key-gated) ----------------------------
    def _ow_forecast(self, geo: dict, days: int) -> dict | None:
        q = urllib.parse.urlencode(
            {"lat": geo["lat"], "lon": geo["lon"], "appid": self.ow_key,
             "units": "metric"})
        cur, fc = None, None
        try:
            with urllib.request.urlopen(f"{self.OW_CUR_URL}?{q}",
                                        timeout=self.timeout) as r:
                cur = json.loads(r.read().decode("utf-8"))
            with urllib.request.urlopen(f"{self.OW_FC_URL}?{q}",
                                        timeout=self.timeout) as r:
                fc = json.loads(r.read().decode("utf-8"))
        except Exception as e:                                  # noqa: BLE001
            log.info("openweather offline/error: %s", e)
            return None
        # translate → open-meteo shape (report() reads this)
        raw = {"current": {
            "temperature_2m": cur.get("main", {}).get("temp"),
            "apparent_temperature": cur.get("main", {}).get("feels_like"),
            "relative_humidity_2m": cur.get("main", {}).get("humidity"),
            "wind_speed_10m": cur.get("wind", {}).get("speed"),
            "weather_code": self._ow_wmo(
                (cur.get("weather") or [{}])[0].get("id")),
            "precipitation": cur.get("rain", {}).get("1h", 0),
        }}
        dmax, dmin, dcode, ddate = [], [], [], []
        seen = {}
        for item in (fc.get("list") or []):
            d = (item.get("dt_txt") or "")[:10]
            if not d:
                continue
            seen.setdefault(d, {"mx": [], "mn": [], "c": []})
            seen[d]["mx"].append(item.get("main", {}).get("temp_max"))
            seen[d]["mn"].append(item.get("main", {}).get("temp_min"))
            seen[d]["c"].append(self._ow_wmo(
                (item.get("weather") or [{}])[0].get("id")))
        for d in sorted(seen)[:max(1, min(7, int(days)))]:
            v = seen[d]
            mx = [x for x in v["mx"] if x is not None]
            mn = [x for x in v["mn"] if x is not None]
            dmax.append(round(max(mx), 1) if mx else None)
            dmin.append(round(min(mn), 1) if mn else None)
            dcode.append(v["c"][0])
            ddate.append(d)
        raw["daily"] = {"temperature_2m_max": dmax, "temperature_2m_min": dmin,
                        "weather_code": dcode, "time": ddate,
                        "precipitation_sum": []}
        return {"place": geo, "raw": raw, "_src": "openweather"}

    # -- open-meteo (keyless default) ------------------------------
    def _om_forecast(self, geo: dict, days: int) -> dict | None:
        params = {
            "latitude": geo["lat"], "longitude": geo["lon"],
            "current": ("temperature_2m,relative_humidity_2m,"
                        "apparent_temperature,precipitation,weather_code,"
                        "wind_speed_10m"),
            "daily": ("weather_code,temperature_2m_max,"
                      "temperature_2m_min,precipitation_sum"),
            "forecast_days": max(1, min(7, int(days))),
            "timezone": "auto",
        }
        q = urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(f"{self.FC_URL}?{q}",
                                        timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:                                  # noqa: BLE001
            log.info("forecast offline: %s", e)
            return None
        return {"place": geo, "raw": data, "_src": "open-meteo"}

    # -- formatting ----------------------------------------------
    _WMO = {
        0: ("clear sky ☀️", 0), 1: ("mainly clear 🌤️", 0),
        2: ("partly cloudy ⛅", 0), 3: ("overcast ☁️", 0),
        45: ("fog 🌫️", 1), 48: ("freezing fog 🌫️❄️", 2),
        51: ("light drizzle 🌦️", 1), 53: ("drizzle 🌦️", 1),
        55: ("dense drizzle 🌧️", 2),
        61: ("light rain 🌦️", 1), 63: ("rain 🌧️", 2), 65: ("heavy rain ⛈️", 3),
        71: ("light snow 🌨️", 1), 73: ("snow 🌨️", 2), 75: ("heavy snow ❄️", 3),
        80: ("rain showers 🌦️", 2), 81: ("showers 🌧️", 2), 82: ("violent showers ⛈️", 3),
        95: ("thunderstorm ⛈️", 3), 96: ("storm + hail ⛈️🧊", 3),
        99: ("severe storm + hail ⛈️🧊", 3),
    }

    @classmethod
    def describe_code(cls, code: int) -> tuple[str, int]:
        return cls._WMO.get(int(code or 0), ("unknown", 1))

    def report(self, place: str, days: int = 3) -> str:
        """Human weather report (bilingual). None-source → honest error."""
        data = self.forecast(place, days)
        if data is None:
            geo = self.geocode(place)
            if geo is None:
                return (f"🌤️ '{place}' என்ற இடம் கண்டுபிடிக்கப்படவில்லை / "
                        f"internet offline — cached data இல்லை.")
            return ("⚠️ இணையம் இல்லை / internet unavailable — "
                    "Open-Meteo reach ஆகவில்லை (offline mode).")
        cur = (data.get("raw") or {}).get("current") or {}
        daily = (data.get("raw") or {}).get("daily") or {}
        g = data.get("place") or {}
        desc, sev = self.describe_code(cur.get("weather_code"))
        lines = [f"🌤️ {g.get('name','?')}"
                 + (f", {g.get('admin','')}" if g.get("admin") else "")
                 + (f", {g.get('country','')}" if g.get("country") else "")]
        lines.append(f"   now: {cur.get('temperature_2m','?')}°C · "
                     f"{desc} · feels {cur.get('apparent_temperature','?')}°C")
        lines.append(f"   humidity {cur.get('relative_humidity_2m','?')}% · "
                     f"wind {cur.get('wind_speed_10m','?')} km/h")
        dmax = daily.get("temperature_2m_max") or []
        dmin = daily.get("temperature_2m_min") or []
        dcode = daily.get("weather_code") or []
        ddate = daily.get("time") or []
        for i in range(min(3, len(dmax))):
            d, sev = self.describe_code(dcode[i] if i < len(dcode) else 0)
            lines.append(f"   {ddate[i] if i < len(ddate) else '?'}: "
                         f"{dmin[i] if i < len(dmin) else '?'}°/"
                         f"{dmax[i] if i < len(dmax) else '?'}° {d}")
        if data.get("_cached"):
            lines.append("   (cache-லிருந்து / from cache)")
        return "\n".join(lines)

    # -- natural language ----------------------------------------
    _RE_W = re.compile(
        r"(?:weather|vaanilai|வானிலை|தட்பவெப்பம்|பவனிலை)\s*(?:in|at|of|la|il|இல்|ல்)?\s*"
        r"([A-Za-z\u0b80-\u0bff .-]+)?", re.I)
    _RE_W_TAMIL_ORDER = re.compile(  # "chennai la weather" - place first
        r"^([A-Za-z\u0b80-\u0bff .-]+?)\s*(?:la|il|in|at|இல்)?\s*(?:weather|vaanilai|வானிலை).*$", re.I)
    _PLACE_STOP = {"enna", "ethana", "eppo", "enga", "seri", "ke", "pa",
                   "tha", "boss", "guru", "na", "solli", "kudu", "pannu",
                   "irruka", "irukka", "irruku", "iruku", "enn", "va",
                   "ey", "aa", "ya", "da", "ra", "bro", "sir", "machi"}


    def parse_command(self, text: str) -> str:
        """'weather in chennai' / 'chennai la weather enna' /
        'வானிலை கோயம்புத்தூர்' / 'சென்னை வானிலை' → report."""
        t = (text or "").strip()
        low = t.lower()
        place = ""
        # 1) Tanglish/Tamil word order: place FIRST, then keyword
        m2 = self._RE_W_TAMIL_ORDER.match(low)
        if m2:
            place = m2.group(1)
        else:
            # 2) keyword first: 'weather in chennai'
            m = self._RE_W.search(t)
            if not m:
                return ""
            place = (m.group(1) or "")
        # strip Tanglish/Tamil filler + question words the regex may catch
        words = [w for w in place.split()
                 if w not in self._PLACE_STOP and w not in
                 ("la", "il", "enna", "ethana", "thaan", "mattum", "in",
                  "at", "of")]
        place = " ".join(words).strip(" .-")
        if not place:
            # remember last place / ask
            return ("📍 எந்த ஊர் / which place? "
                    "e.g. 'weather in Chennai', 'chennai la weather enna', "
                    "'வானிலை மதுரை'")
        return self.report(place)


# ---------------------------------------------------------- web search
class WebSearchTool:
    """Google-backed SERPER + Tavily fallback (both optional, .env/secrets).

    v2.2 key chain (all optional):
      • SERPER_API_KEY  → google.serper.dev (preferred, richer results)
      • TAVILY_API_KEY  → api.tavily.com (fallback when serper missing)
    No keys → cache/offline-safe reply. Never crashes."""

    URL = "https://google.serper.dev/search"
    TV_URL = "https://api.tavily.com/search"
    Ttl = 24 * 3600

    def __init__(self, cache: LiveCache | None = None,
                 api_key: str | None = None, timeout: float = 12.0):
        self.cache = cache or LiveCache()
        self._key_override = api_key or ""
        self.timeout = timeout

    # -- key resolution (live, no restart) ---------------------------
    @property
    def key(self) -> str:
        return self._key_override or os_getenv("SERPER_API_KEY", "")

    @property
    def tavily_key(self) -> str:
        return os_getenv("TAVILY_API_KEY", "")

    def available(self) -> bool:
        return bool(self.key or self.tavily_key)

    def search(self, query: str, n: int = 5) -> list[dict] | None:
        if not self.available():
            return None
        query = (query or "").strip()
        if not query:
            return None
        ck = f"q:{query.lower()}"
        cached = self.cache.get(ck, "search")
        if cached:
            return cached
        hits = self._serper(query, n) or self._tavily(query, n)
        if hits:
            self.cache.put(ck, "search", hits)
        return hits

    # -- serper -----------------------------------------------------
    def _serper(self, query: str, n: int) -> list[dict] | None:
        if not self.key:
            return None
        body = json.dumps({"q": query, "num": max(1, min(10, n))}).encode()
        req = urllib.request.Request(
            self.URL, data=body, method="POST",
            headers={"X-API-KEY": self.key,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:                                  # noqa: BLE001
            log.info("serper offline/error: %s", e)
            return None
        return [{"title": o.get("title", ""),
                 "link": o.get("link", ""),
                 "snippet": o.get("snippet", "")}
                for o in (data.get("organic") or [])[:n]]

    # -- tavily fallback --------------------------------------------
    def _tavily(self, query: str, n: int) -> list[dict] | None:
        if not self.tavily_key:
            return None
        body = json.dumps({
            "query": query, "max_results": max(1, min(10, n)),
            "search_depth": "basic"}).encode()
        req = urllib.request.Request(
            self.TV_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.tavily_key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:                                  # noqa: BLE001
            log.info("tavily offline/error: %s", e)
            return None
        hits = [{"title": o.get("title", ""),
                 "link": o.get("url", ""),
                 "snippet": o.get("content", "")}
                for o in (data.get("results") or [])[:n]]
        return hits or None

    def report(self, query: str, n: int = 5) -> str:
        hits = self.search(query, n)
        if hits is None:
            if not self.available():
                return ("🔍 SERPER_API_KEY / TAVILY_API_KEY "
                        "ஆகவில்லை — web search optional feature. "
                        "Settings → API Keys எடிக்குங்க.")
            return "⚠️ search தோல்வி / internet unavailable (offline mode)."
        if not hits:
            return f"🔍 '{query}' — results இல்லை / no results."
        lines = [f"🔍 Rolex Web Search · {query}"]
        for i, h in enumerate(hits, 1):
            lines.append(f"  {i}. {h['title']}")
            if h["snippet"]:
                lines.append(f"     {h['snippet'][:140]}")
            lines.append(f"     {h['link']}")
        return "\n".join(lines)

    # -- natural language ----------------------------------------
    _RE_S = re.compile(
        r"^(?:search|google|look\s*up|find)\s+(?:for\s+|the\s+)?(.+)$", re.I)

    def parse_command(self, text: str) -> str:
        m = self._RE_S.match((text or "").strip())
        if not m:
            return ""
        q = m.group(1).strip()
        if not q:
            return ""
        return self.report(q)


def os_getenv(name: str, default: str = "") -> str:
    """Env read that also sees data/secrets.json (rolex security)."""
    import os
    val = os.getenv(name, "")
    if val:
        return val
    try:
        from ..security.secrets import SECRETS
        return SECRETS.get(name) or default
    except Exception:                                           # noqa: BLE001
        return default


LIVE_CACHE = LiveCache()
WEATHER = WeatherTool(LIVE_CACHE)
WEBSEARCH = WebSearchTool(LIVE_CACHE)
