"""Tests for Phase 13 - Voice + Vision (offline, temp DBs, no network)."""
import builtins
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.voice.wake import WakeWord, WAKE
from rolex.voice.stt import SpeechToText, STT, typed_input
from rolex.voice.tts import TextToSpeech, TTS, speak_line
from rolex.voice.vision import (Vision, Camera, VISION, CAMERA,
                                VisionError, sniff_format, basic_info)
from rolex.voice.voice import VoiceLoop, VOICE
from rolex.automation.engine import TaskEngine
from rolex.memory.store import MemoryStore

FIX = Path(__file__).resolve().parent / "fixtures"


def _tasks() -> TaskEngine:
    tmp = tempfile.mkdtemp()
    return TaskEngine(db_path=os.path.join(tmp, "tasks.db"))


def _memory() -> MemoryStore:
    tmp = tempfile.mkdtemp()
    return MemoryStore(db_path=os.path.join(tmp, "mem.db"))


def _loop(tasks=None) -> VoiceLoop:
    return VoiceLoop(memory=_memory(), tasks=tasks or _tasks())


# ------------------------------------------------------------ wake word
def test_wake_word_exact():
    ok, cmd = WAKE.detect("Hey Guru")
    assert ok is True and cmd == ""
    ok, cmd = WAKE.detect("  hey   GURU  ")
    assert ok is True
    print("PASS test_wake_word_exact")


def test_wake_word_with_command():
    ok, cmd = WAKE.detect("hey guru calculate 5*5")
    assert ok is True and cmd == "calculate 5*5"
    ok, cmd = WAKE.detect("hey guru what is ohms law")
    assert ok is True and "ohms law" in cmd
    print("PASS test_wake_word_with_command")


def test_wake_word_stt_mishears():
    # fuzzy + common mishear tolerance
    for phrase in ("hey gurru", "hi guruuu", "hey google", "hello guru"):
        ok, _ = WAKE.detect(phrase)
        assert ok is True, f"missed wake: {phrase}"
    print("PASS test_wake_word_stt_mishears")


def test_wake_word_negative():
    for phrase in ("hey siri", "hello world", "calculate 5*5",
                   "vanakkam machine", "what is gravity"):
        ok, cmd = WAKE.detect(phrase)
        assert ok is False, f"false wake: {phrase}"
        assert cmd == phrase
    print("PASS test_wake_word_negative")


def test_wake_word_standalone_guru():
    ok, cmd = WAKE.detect("guru 25*4")
    assert ok is True and cmd == "25*4"
    print("PASS test_wake_word_standalone_guru")


# ----------------------------------------------------------------- stt
def test_stt_honest_capabilities_and_fallback():
    caps = STT.available()
    assert "library" in caps and "microphone" in caps and caps["offline"]
    # listen() without mic → typed fallback → "" (never crashes)
    val = SpeechToText(quiet=True).listen()
    assert isinstance(val, str)
    print("PASS test_stt_honest_capabilities_and_fallback")


def test_typed_input_reads_stdin():
    orig = builtins.input
    builtins.input = lambda p="": "hello rolex"
    try:
        assert typed_input() == "hello rolex"
        builtins.input = lambda p="": ""
        assert typed_input() == ""
    finally:
        builtins.input = orig
    print("PASS test_typed_input_reads_stdin")


# ----------------------------------------------------------------- tts
def test_tts_never_crashes():
    t = TextToSpeech(enabled=True)
    result = t.speak("Rolex test line")       # may be False (no engine)
    assert isinstance(result, bool)
    caps = t.available()
    assert "pyttsx3" in caps and "enabled" in caps
    t.disabled = True                          # arbitrary attr is fine
    assert t.speak("") is False                # empty never speaks
    print("PASS test_tts_never_crashes")


def test_speak_line_prints():
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        speak_line("Rolex says hi")
    assert "Rolex says hi" in buf.getvalue()
    print("PASS test_speak_line_prints")


# -------------------------------------------------------------- vision
def test_vision_sniff_and_dims():
    info = basic_info(FIX / "sample.png")
    assert info["format"] == "png"
    assert info["width"] == 64 and info["height"] == 48
    print("PASS test_vision_sniff_and_dims")


def test_vision_jpeg_magic():
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / "fake.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
    assert sniff_format(p) == "jpeg"
    print("PASS test_vision_jpeg_magic")


def test_vision_describe():
    d = VISION.describe(FIX / "sample.png")
    assert "PNG" in d and "64x48" in d
    print("PASS test_vision_describe")


def test_vision_missing_raises():
    try:
        sniff_format(FIX / "nope.png")
        raise AssertionError("missing file must raise")
    except VisionError:
        pass
    print("PASS test_vision_missing_raises")


def test_camera_honest_unavailable():
    caps = CAMERA.available()
    assert isinstance(caps, dict)
    try:
        CAMERA.capture()
        raise AssertionError("capture must fail without backend")
    except VisionError:
        pass
    print("PASS test_camera_honest_unavailable")


# ---------------------------------------------------------- voice loop
def test_loop_math_local_no_ai():
    loop = _loop()
    reply = loop.handle_utterance("hey guru 15% of 200")
    assert reply.startswith("⚡") and "30" in reply
    print("PASS test_loop_math_local_no_ai")


def test_loop_wake_only_acknowledges():
    loop = _loop()
    reply = loop.handle_utterance("hey guru")
    assert "yes" in reply.lower()
    print("PASS test_loop_wake_only_acknowledges")


def test_loop_greeting():
    loop = _loop()
    reply = loop.handle_utterance("hey guru vanakkam")
    assert "Rolex" in reply
    print("PASS test_loop_greeting")


def test_loop_command():
    loop = _loop()
    reply = loop.handle_utterance("hey guru /version")
    assert "ROLEX" in reply or "1.0" in reply
    print("PASS test_loop_command")


def test_loop_reminder():
    tasks = _tasks()
    loop = _loop(tasks=tasks)
    reply = loop.handle_utterance(
        "hey guru remind me in 5 minutes to check motor")
    assert "🔔" in reply and "check motor" in reply
    assert len(tasks.upcoming()) == 1
    print("PASS test_loop_reminder")


def test_loop_knowledge_local():
    loop = _loop()
    reply = loop.handle_utterance("hey guru what is a transformer")
    assert reply.startswith("📘") and "transformer" in reply.lower()
    print("PASS test_loop_knowledge_local")


def test_loop_memory_records_exchange():
    loop = _loop()
    loop.handle_utterance("hey guru 2**8")
    turns = loop.memory.recent_turns(4)
    texts = " | ".join(t.text for t in turns)
    assert "2**8" in texts and "256" in texts
    print("PASS test_loop_memory_records_exchange")


def test_loop_scripted_run_and_summary():
    loop = _loop()
    out = loop.run(max_turns=3,
                   scripted=["hey guru", "12*12", "what is a diode"])
    assert loop.turns == 3
    assert out["turns"] == 3 and "session_seconds" in out
    assert "stt" in out and "tts" in out
    print("PASS test_loop_scripted_run_and_summary")


def test_loop_unknown_goes_to_answer_engine():
    # no AI keys in test env → answer engine offline fallback (no crash)
    loop = _loop()
    reply = loop.handle_utterance(
        "hey guru who invented the telephone")
    assert isinstance(reply, str) and len(reply) > 5
    print("PASS test_loop_unknown_goes_to_answer_engine")


def test_voice_singletons_importable():
    assert WAKE is not None and STT is not None and TTS is not None
    assert VISION is not None and CAMERA is not None and VOICE is not None
    print("PASS test_voice_singletons_importable")


if __name__ == "__main__":
    test_wake_word_exact()
    test_wake_word_with_command()
    test_wake_word_stt_mishears()
    test_wake_word_negative()
    test_wake_word_standalone_guru()
    test_stt_honest_capabilities_and_fallback()
    test_typed_input_reads_stdin()
    test_tts_never_crashes()
    test_speak_line_prints()
    test_vision_sniff_and_dims()
    test_vision_jpeg_magic()
    test_vision_describe()
    test_vision_missing_raises()
    test_camera_honest_unavailable()
    test_loop_math_local_no_ai()
    test_loop_wake_only_acknowledges()
    test_loop_greeting()
    test_loop_command()
    test_loop_reminder()
    test_loop_knowledge_local()
    test_loop_memory_records_exchange()
    test_loop_scripted_run_and_summary()
    test_loop_unknown_goes_to_answer_engine()
    test_voice_singletons_importable()
    print("ALL VOICE+VISION TESTS PASSED")
