"""Rolex Horizon UI — Kivy Android cockpit + text fallback."""
from __future__ import annotations

COLORS = {
    "bg": (0.024, 0.039, 0.078, 1),
    "panel": (0.051, 0.082, 0.149, 1),
    "panel2": (0.067, 0.106, 0.188, 1),
    "accent": (0.831, 0.686, 0.216, 1),
    "accent2": (0.941, 0.843, 0.549, 1),
    "ok": (0.133, 0.773, 0.369, 1),
    "warn": (0.961, 0.620, 0.043, 1),
    "bad": (0.937, 0.267, 0.302, 1),
    "text": (0.910, 0.937, 0.984, 1),
    "dim": (0.561, 0.639, 0.761, 1),
    "dimmer": (0.353, 0.427, 0.549, 1),
}

try:
    from kivy.app import App
    from kivy.lang import Builder
    from kivy.core.window import Window
    from kivy.uix.label import Label
    KIVY = True
except Exception:  # pragma: no cover
    App = object
    Builder = None
    Window = None
    Label = None
    KIVY = False


KV = r"""
#:import rolex_ui rolex.ui.android_ui

BoxLayout:
    orientation: 'vertical'
    padding: 0
    spacing: 0

    AnchorLayout:
        anchor_x: 'center'
        anchor_y: 'top'
        size_hint_y: 0.16
        BoxLayout:
            orientation: 'vertical'
            size_hint: 1, 1
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
                text: 'ROLEX AI'
                font_size: '26sp'
                bold: True
                color: rolex_ui.COLORS['accent2']
            Label:
                id: state
                text: 'Rolex Horizon · starting'
                font_size: '11sp'
                color: rolex_ui.COLORS['dim']

    AnchorLayout:
        anchor_x: 'center'
        anchor_y: 'center'
        size_hint_y: 0.44
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
                text: 'HEY GURU · READY'
                font_size: '12sp'
                color: rolex_ui.COLORS['dim']
                size_hint_y: None
                height: dp(18)

    BoxLayout:
        orientation: 'vertical'
        padding: 12
        spacing: 8
        size_hint_y: 0.40

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
                text: 'SEND'
                font_size: '16sp'
                background_normal: ''
                background_color: rolex_ui.COLORS['accent']
                color: (0.13, 0.09, 0.04, 1)
                on_release: app.send(input.text)
"""


class RolexApp(App if KIVY else object):
    """Kivy app.  UI is created before the assistant so startup failures are visible."""

    listening = False

    def __init__(self, assistant=None, **kwargs):
        if KIVY:
            super().__init__(**kwargs)
        self.assistant = assistant
        self.state_label = None
        self.chat = None
        self.scroll = None

    def build(self):
        if not KIVY:  # pragma: no cover
            return None

        Window.clearcolor = COLORS["bg"]
        root = Builder.load_string(KV)
        self.state_label = root.ids.get("state")
        self.chat = root.ids.get("chat")
        self.scroll = root.ids.get("chat_scroll")

        # Now initialize the core. Any failure becomes a visible diagnostic
        # inside the already-created Kivy window instead of killing the app.
        if self.assistant is None:
            try:
                from ..assistant import get_assistant
                self.assistant = get_assistant()
            except Exception as exc:  # noqa: BLE001
                self._show_startup_error(exc)
                return root

        self._refresh_state()
        return root

    def on_start(self):
        # Render the first frame before starting the large assistant graph.
        # This prevents a slow/failing core import from looking like a
        # completely failed Android launch.
        if self.assistant is None:
            return
        try:
            from kivy.clock import Clock
            Clock.schedule_once(self._finish_startup, 0.15)
        except Exception as exc:  # noqa: BLE001
            self._show_startup_error(exc)

    def _finish_startup(self, *_args):
        try:
            report = self.assistant.startup()
            failed = [k for k, v in report.items() if v == 'failed']
            if failed and self.state_label is not None:
                self.state_label.text = 'Rolex · DEGRADED · ' + ', '.join(failed)
        except Exception as exc:  # noqa: BLE001
            self._show_startup_error(exc)
            return
        try:
            from ..voice.modulation import MODULATOR
            MODULATOR.speak("Rolex online. Hey Guru ready.")
        except Exception:  # noqa: BLE001
            pass

    def on_stop(self):
        if self.assistant is not None:
            try:
                self.assistant.shutdown()
            except Exception:
                pass

    def _show_startup_error(self, exc: Exception) -> None:
        msg = f"STARTUP ERROR\n{type(exc).__name__}: {exc}"
        if self.state_label is not None:
            self.state_label.text = 'Rolex · STARTUP ERROR'
        if self.chat is not None and Label is not None:
            self.chat.add_widget(Label(
                text=msg,
                size_hint_y=None,
                height=dp(100) if False else 100,
                color=COLORS['bad'],
                font_size='13sp',
                halign='left',
            ))

    def send(self, text: str) -> None:
        text = (text or '').strip()
        if not text or self.assistant is None:
            return
        self._bubble(text, mine=True)
        from kivy.clock import Clock
        Clock.schedule_once(lambda *_: self._answer(text), 0.05)

    def _answer(self, text: str) -> None:
        try:
            res = self.assistant.ask(text)
            self._bubble(str(res))
            self._speak(str(res))
            self._refresh_state()
            if self.scroll is not None:
                self.scroll.scroll_y = 0
        except Exception as exc:  # noqa: BLE001
            self._bubble(f"STARTUP/CORE ERROR: {type(exc).__name__}: {exc}")

    def _speak(self, text: str) -> None:
        try:
            from ..voice.modulation import MODULATOR
            MODULATOR.speak(text)
        except Exception:
            pass

    def _bubble(self, text: str, mine: bool = False) -> None:
        if self.chat is None or Label is None:
            return
        color = COLORS['text'] if mine else COLORS['accent2']
        prefix = 'you   ' if mine else 'rolex   '
        self.chat.add_widget(Label(
            text=prefix + text,
            size_hint_y=None,
            halign='left',
            color=color,
            font_size='15sp',
            padding=(8, 8),
        ))

    def _refresh_state(self) -> None:
        if self.state_label is None or self.assistant is None:
            return
        try:
            st = self.assistant.status()
            self.state_label.text = (
                f"Rolex · {st['state']} · turns {st['turns']} · "
                f"KB {st['kb_entries']} · todos {st.get('todos_pending', 0)}"
            )
        except Exception:
            self.state_label.text = 'Rolex Horizon'


def text_cockpit(assistant, scripted: list[str] | None = None,
                 max_turns: int = 0) -> dict:
    """No-Kivy futuristic terminal cockpit using the same facade."""
    W = 50
    GOLD = '\033[38;5;178m'
    DIM = '\033[38;5;245m'
    OK = '\033[38;5;41m'
    RESET = '\033[0m'
    print('\n'.join([
        '',
        f"{GOLD}╭" + '─' * W + '╮',
        f"│ {'ROLEX HORIZON':^46} │",
        f"│ {'personal intelligence · local-first':^46} │",
        f"╰" + '─' * W + '╯{RESET}',
        f"{DIM}  local-first · Hey Guru wake · Jarvis voice · Tanglish{RESET}",
        '',
    ]))
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
                raw = input(f'{GOLD}you ▸ {RESET}')
            except EOFError:
                break
        if raw.strip().lower() in ('exit', 'quit', 'bye'):
            break
        if not raw.strip():
            continue
        res = assistant.ask(raw)
        bar = f'{OK}LOCAL{RESET}' if res.local else 'AI'
        print(f'{GOLD}rolex ▸{RESET} {res.text}')
        print(f'{DIM}   ─ {bar} · route:{res.route} · conf:{res.confidence:.2f} · {res.seconds}s{RESET}\n')
        turn += 1
    assistant.shutdown()
    return {'turns': turn}
