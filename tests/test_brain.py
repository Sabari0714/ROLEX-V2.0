"""Phase 3 test — Local Brain (language, intents, entities, context, flow)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rolex.brain import NLU, LanguageDetector, LANG   # noqa: E402
from rolex.brain.reasoning import Reasoner            # noqa: E402


def test_language_detection():
    d = LanguageDetector()
    assert d.detect("Hello how are you").lang == LANG.ENGLISH
    assert d.detect("வணக்கம் எப்படி இருக்கீங்க").lang == LANG.TAMIL
    assert d.detect("enna panra").lang == LANG.TANGlish
    assert d.detect("enna solra").tanglish_hits


def test_intents():
    nlu = NLU()
    assert nlu.analyze("hi").intent == "greeting"
    assert nlu.analyze("hello").intent == "greeting"
    assert nlu.analyze("what is 12 * 5").intent == "math"
    assert nlu.analyze("ohms law 12V 2A").intent == "engineering"
    assert nlu.analyze("what time is it").intent == "time_now"
    assert nlu.analyze("convert 5 km to miles").intent == "unit_convert"
    assert nlu.analyze("who are you").intent == "identity"
    assert nlu.analyze("explain transformer working").intent == "knowledge"
    assert nlu.analyze("thanks").intent == "thanks"


def test_entities():
    nlu = NLU()
    r = nlu.analyze("12 plus 8")
    assert 12.0 in r.entities["numbers"] and 8.0 in r.entities["numbers"]
    r2 = nlu.analyze("ohm law 12V 2A")
    assert (12.0, "V") in [(n, u) for n, u in r2.entities["value_units"]]
    r3 = nlu.analyze("rendu moonu")
    assert 2.0 in r3.entities["numbers"] and 3.0 in r3.entities["numbers"]


def test_math_local_rule():
    nlu = NLU()
    for q in ["5+3", "25 percent of 200", "sqrt 144", "10 x 4",
              "vagai 100 5", "square root of 81"]:
        r = nlu.analyze(q)
        assert nlu.is_local(r.intent) or r.intent == "math", f"must be local: {q}"


def test_followup():
    nlu = NLU()
    nlu.analyze("explain ohms law")
    r = nlu.analyze("tell me more")
    assert r.is_followup
    assert "ohms law" in r.merged_text


def test_reasoner():
    rz = Reasoner()
    assert "bigger" in rz.compare(5, 7) or "7" in rz.compare(5, 7)
    assert rz.is_prime(7) and not rz.is_prime(8)
    assert rz.days_between("2024-01-01", "2024-01-31") == 30
    assert rz.count_words("one two three") == 3


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            print(f"PASS {k}")
    print("PHASE 3 BRAIN: ALL OK")
