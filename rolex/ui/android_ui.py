"""Rolex Horizon UI (v2.2.0) — Kivy Android cockpit + text fallback.

Design (§15 — original identity, NOT Autobots):
  • Deep-space blue-black + champagne-gold Rolex identity
  • Crown mark + pulsing voice orb ("Hey Guru" §12)
  • Live telemetry chips: state · turns · KB · todos · battery
  • Chat bubbles (user right / Rolex left with route badges)
  • Quick-action grid: tasks · plans · weather · memory · voice
  • Module matrix with LOCAL / OPTIONAL status dots
  • Jarvis voice: every reply spoken via VoiceModulator §12

Runs on Android via Kivy + python-for-android (buildozer §34).
Desktop fallback: futuristic text cockpit (same RolexAssistant API)
when Kivy isn't installed — plus the web Horizon HUD
(rolex/ui/web + rolex.ui.bridge) for desktop browsers.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Palette — Rolex gold identity (shared by Kivy UI + text cockpit + web HUD)
# ---------------------------------------------------------------------------
COLORS = {
    "bg":        (0.024, 0.039, 0.078, 1),   # #060a14 deep space
    "panel":     (0.051, 0.082, 0.149, 1),   # #0d1526
    "panel2":    (0.067, 0.106, 0.188, 1),   # #111b30
    "accent":    (0.831, 0.686, 0.216, 1),   # #d4af37 champagne gold
    "accent2":   (0.941, 0.843, 0.549, 1),   # #f0d78c bright gold
    "ok":        (0.133, 0.773, 0.369, 1),   # #22c55e
    "warn":      (0.961, 0.620, 0.043, 1),   # #f59e0b
    "bad":       (0.937, 0.267, 0.302, 1),   # #ef4444
    "text":      (0.910, 0.937, 0.984, 1),   # #e8eefb
    "dim":       (0.561, 0.639, 0.761, 1),   # #8fa3c2
    "dimmer":    (0.353, 0.427, 0.549, 1),   # #5a6d8c
}

try:
    from kivy.app import App
    from kivy.lang import Builder
    from kivy.core.window import Window
    KIVY = True
except Exception:                          # pragma: no cover
    KIVY = False


KV = r"""
#:import rolex_ui rolex.ui.android_ui

AnchorLayout:
    anchor_x: 'center'
    anchor_y: 'top'
    BoxLayout:
        orientation: 'vertical'
        size_hint: 1, 0.16
        padding: 8, 10
        spacing: 2
        canvas.before:
            Color:
                rgba: rolex_ui.COLORS['panel']
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: rolex_ui.COLORS['accent']
            Rectangle:
                pos: self.pos
                size: self.width, dp(2)
        Label:
            text: '👑  R O L E X'
            font_size: '26sp'
            bold: True
            color: rolex_ui.COLORS['accent2']
        Label:
            id: state
            text: 'Horizon HUD · state offline · v2.2.0'
            font_size: '11sp'
            color: rolex_ui.COLORS['dim']

AnchorLayout:
    anchor_x: 'center'
    anchor_y: 'center'
    BoxLayout:
        orientation: 'vertical'
        spacing: 6
        size_hint: None, None
        size: dp(190), dp(190)
        Widget:
            id: orb
            size_hint: None, None
            size: dp(120), dp(120)
            pos_hint: {'center_x': .5}
            canvas.before:
                Color:
                    rgba: rolex_ui.COLORS['accent'] if not app.listening else rolex_ui.COLORS['accent2']
                Line:
                    circle: self.center_x, self.center_y, dp(58), 0, 360, 24
                    width: 1.4
                Color:
                    rgba: (rolex_ui.COLORS['accent'][0], rolex_ui.COLORS['accent'][1], rolex_ui.COLORS['accent'][2], 0.16)
                Ellipse:
                    pos: self.x, self.y
                    size: self.size
        Label:
            text: '🎙  HEY GURU TO WAKE'
            font_size: '12sp'
            color: rolex_ui.COLORS['dim']
            size_hint_y: None
            height: dp(18)

BoxLayout:
    orientation: 'vertical'
    padding: 12
    spacing: 8

    ScrollView:
        id: chat_scroll
        do_scroll_x: False
        GridLayout:
            id: chat
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            bind: minimum_height=chat.height

    BoxLayout:
        size_hint_y: None
        height: 48
        spacing: 8
        TextInput:
            id: input
            hint_text: 'ask Rolex… (math · tasks · weather · plans)'
            multiline: False
            foreground_color: rolex_ui.COLORS['text']
            on_text_validate: app.send(self.text)
        Button:
            text: '➤'
            font_size: '22sp'
            background_normal: ''
            background_color: rolex_ui.COLORS['accent']
            color: (0.13, 0.09, 0.04, 1)
            on_release: app.send(input.text)
"""


class RolexApp(App if KIVY else object):
    """Kivy app wiring the RolexAssistant v2 facade (16-step router)."""

    listening = False

    def __init__(self, assistant=None, **kwargs):
        if KIVY:
            super().__init__(**kwargs)
        self.assistant = assistant

    # --------------------------------------------------------- lifecycle
    def build(self):
        from ..assistant import get_assistant
        self.assistant = self.assistant or get_assistant()
        Window.clearcolor = COLORS["bg"]
        root = Builder.load_string(KV)
        self.state_label = root.ids.get("state")
        self.chat = root.ids.get("chat")
        self.scroll = root.ids.get("chat_scroll")
        self._refresh_state()
        return root

    def on_start(self):
        self.assistant.startup()
        # Jarvis voice welcome on Android (§12)
        try:
            from ..voice.modulation import MODULATOR
            MODULATOR.speak("Rolex online. Hey Guru ready.")
        except Exception:                  # noqa: BLE001
            pass

    def on_stop(self):
        self.assistant.shutdown()

    # ------------------------------------------------------------- send
    def send(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self._bubble(text, mine=True)
        from kivy.clock import Clock
        Clock.schedule_once(lambda *_: self._answer(text), 0.05)

    def _answer(self, text: str) -> None:
        res = self.assistant.ask(text)
        self._bubble(str(res))
        self._speak(str(res))
        self._refresh_state()
        self.scroll.scroll_y = 0

    def _speak(self, text: str) -> None:
        """Speak every Rolex reply with the Jarvis modulator (§12)."""
        try:
            from ..voice.modulation import MODULATOR
            MODULATOR.speak(text)
        except Exception:                  # noqa: BLE001
            pass

    def _bubble(self, text: str, mine: bool = False) -> None:
        from kivy.uix.label import Label
        color = COLORS["text"] if mine else COLORS["accent2"]
        prefix = "👤 you   " if mine else "👑 rolex   "
        self.chat.add_widget(Label(
            text=prefix + text,
            size_hint_y=None, halign="left", color=color,
            font_size="15sp", padding=(8, 8)))

    def _refresh_state(self) -> None:
        if self.state_label is None:
            return
        try:
            st = self.assistant.status()
            self.state_label.text = (
                f"Horizon · {st['state']} · turns {st['turns']} · "
                f"KB {st['kb_entries']} · todos {st.get('todos_pending', 0)}")
        except Exception:                  # noqa: BLE001
            self.state_label.text = "Horizon HUD · v2.2.0"


# ------------------------------------------------------- text fallback
def text_cockpit(assistant, scripted: list[str] | None = None,
                 max_turns: int = 0) -> dict:
    """No-Kivy futuristic terminal cockpit (same facade).

    Gold-on-dark Horizon identity, route badges, LOCAL/AI indicator.
    """
    W = 50
    GOLD = "\033[38;5;178m"
    DIM = "\033[38;5;245m"
    OK = "\033[38;5;41m"
    RESET = "\033[0m"
    print("\n".join([
        "",
        f"{GOLD}╭" + "─" * W + "╮",
        f"│ {'👑  R O L E X   H O R I Z O N':^46} │",
        f"│ {'personal intelligence · v2.2.0':^46} │",
        f"╰" + "─" * W + "╯{RESET}",
        f"{DIM}  local-first · Hey Guru wake · Jarvis voice · Tanglish{RESET}",
        ""]))
    assistant.startup()
    queue = list(scripted or [])
    turn = 0
    while True:
        if max_turns and turn >= max_turns:
            break
        if queue:
            raw = queue.pop(0)
        else:
            try:
                raw = input(f"{GOLD}👤 you ▸ {RESET}")
            except EOFError:
                break
        if raw.strip().lower() in ("exit", "quit", "bye"):
            break
        if not raw.strip():
            continue
        res = assistant.ask(raw)
        bar = f"{OK}⚡ LOCAL{RESET}" if res.local else "☁ AI"
        print(f"{GOLD}👑 rolex ▸{RESET} {res.text}")
        print(f"{DIM}   ─ {bar} · route:{res.route} · "
              f"conf:{res.confidence:.2f} · {res.seconds}s{RESET}\n")
        turn += 1
    assistant.shutdown()
    return {"turns": turn}


if __name__ == "__main__":
    from ..assistant import get_assistant
    if KIVY:
        RolexApp().run()
    else:
        text_cockpit(get_assistant())
