"""Tests for Phase 10 - Task & Automation Engine (temp DB)."""
import sys
import tempfile
import os
import time as _time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.automation.engine import TaskEngine, Task, Priority


def _engine():
    tmp = tempfile.mkdtemp()
    return TaskEngine(db_path=os.path.join(tmp, "tasks.db"))


# ----------------------------------------------------------------- tests
def test_add_reminder_and_fire():
    e = _engine()
    t = e.add_reminder("check motor", _time.time() - 1)  # already due
    assert t.kind == "reminder" and t.max_runs == 1
    fired = e.tick()
    assert len(fired) == 1 and fired[0].id == t.id
    # one-shot: disabled after firing
    assert t.enabled is False
    assert t.n_runs == 1
    assert e.tick() == []           # not fired again
    print("PASS test_add_reminder_and_fire")


def test_future_reminder_not_fired():
    e = _engine()
    e.add_reminder("later", _time.time() + 3600)
    assert e.tick() == []
    print("PASS test_future_reminder_not_fired")


def test_parse_reminder_in_minutes():
    e = _engine()
    t = e.parse_reminder_text(
        "remind me in 10 minutes to check the battery")
    assert t is not None
    assert t.title == "check the battery"
    assert 590 <= t.at - _time.time() <= 610     # ~10 minutes
    print("PASS test_parse_reminder_in_minutes")


def test_parse_reminder_at_time():
    e = _engine()
    t = e.parse_reminder_text("remind me at 09:30 pm to sleep")
    assert t is not None
    import datetime as dt
    target = dt.datetime.fromtimestamp(t.at)
    assert target.hour == 21 and target.minute == 30
    print("PASS test_parse_reminder_at_time")


def test_parse_reminder_at_time_am():
    e = _engine()
    t = e.parse_reminder_text("reminder at 6:00 am gym")
    assert t is not None
    import datetime as dt
    target = dt.datetime.fromtimestamp(t.at)
    assert target.hour == 6 and target.minute == 0
    assert t.title == "gym"
    print("PASS test_parse_reminder_at_time_am")


def test_parse_recurring_every():
    e = _engine()
    t = e.parse_recurring_text("every 5 minutes check temperature")
    assert t is not None
    assert t.kind == "recurring"
    assert t.every == 300
    assert t.title == "check temperature"
    print("PASS test_parse_recurring_every")


def test_recurring_fires_multiple_times():
    e = _engine()
    t = e.add_recurring("heartbeat", every=0.05)   # 50 ms
    now = _time.time()
    # first due
    fired1 = e.tick(now=now + 0.06)
    assert len(fired1) == 1
    # second due
    fired2 = e.tick(now=now + 0.13)
    assert len(fired2) == 1
    assert t.n_runs == 2
    assert t.enabled is True        # keeps running
    print("PASS test_recurring_fires_multiple_times")


def test_priority_order_and_upcoming():
    e = _engine()
    now = _time.time()
    e.add_reminder("low", now + 100, priority=Priority.LOW)
    e.add_reminder("urgent", now + 200, priority=Priority.CRITICAL)
    e.add_reminder("mid", now + 50, priority=Priority.NORMAL)
    up = e.upcoming(3)
    # earliest first, priority breaks ties
    assert [t.title for t in up] == ["mid", "low", "urgent"]
    print("PASS test_priority_order_and_upcoming")


def test_cancel_and_snooze():
    e = _engine()
    t = e.add_reminder("cancel me", _time.time() + 60)
    assert e.cancel(t.id) is True
    assert e.get(t.id) is None
    assert e.cancel("nope") is False

    t2 = e.add_reminder("snooze me", _time.time() + 60)
    e.snooze(t2.id, 300)
    assert t2.next_due >= _time.time() + 299
    print("PASS test_cancel_and_snooze")


def test_callbacks():
    e = _engine()
    calls = []
    e.register_callback("log_health", lambda t: calls.append(t.title))
    t = e.add_schedule("log health", _time.time() - 1,
                       action="callback",
                       payload={"callback": "log_health"})
    fired = e.tick()
    assert len(fired) == 1
    assert calls == ["log health"]
    print("PASS test_callbacks")


def test_event_triggers():
    e = _engine()
    calls = []
    e.register_callback("on_boot", lambda t: calls.append("boot"))
    e.add_trigger("boot hook", event="boot",
                  action="callback", payload={"callback": "on_boot"})
    fired = e.handle_event("boot")
    assert len(fired) == 1
    assert calls == ["boot"]
    # unrelated event does not fire
    assert e.handle_event("shutdown") == []
    print("PASS test_event_triggers")


def test_history_and_stats():
    e = _engine()
    e.add_reminder("hist", _time.time() - 1)
    e.tick()
    h = e.history(5)
    assert len(h) == 1 and h[0]["status"] == "ok"
    assert h[0]["title"] == "hist"
    s = e.stats()
    assert s["total"] == 1 and s["active"] == 0  # fired one-shot
    print("PASS test_history_and_stats")


def test_persistence_reload():
    e = _engine()
    e.add_reminder("persist", _time.time() + 60)
    e.add_recurring("loop", every=120)
    # brand new engine on the same DB
    e2 = TaskEngine(db_path=e.db_path)
    assert e2.get_pending_count() >= 2 if hasattr(e2, "get_pending_count") \
        else len(e2.tasks) >= 2
    assert e2.tasks["persist" if "persist" in e2.tasks
                   else list(e2.tasks)[0]] is not None
    titles = {t.title for t in e2.tasks.values()}
    assert "persist" in titles and "loop" in titles
    print("PASS test_persistence_reload")


def test_command_task_never_executes_shell():
    """Security: 'command' tasks are logged, never executed."""
    e = _engine()
    t = e.add_schedule("danger", _time.time() - 1, action="command",
                       payload={"command": "rm -rf /"})
    e.tick()
    h = e.history(5)
    assert h[0]["status"] == "skip"
    assert t.n_runs == 0
    print("PASS test_command_task_never_executes_shell")


def test_singleton_importable():
    from rolex.automation import TASKS, TaskEngine
    assert isinstance(TASKS, TaskEngine)
    st = TASKS.stats()
    assert "total" in st and "active" in st
    print("PASS test_singleton_importable")


if __name__ == "__main__":
    test_add_reminder_and_fire()
    test_future_reminder_not_fired()
    test_parse_reminder_in_minutes()
    test_parse_reminder_at_time()
    test_parse_reminder_at_time_am()
    test_parse_recurring_every()
    test_recurring_fires_multiple_times()
    test_priority_order_and_upcoming()
    test_cancel_and_snooze()
    test_callbacks()
    test_event_triggers()
    test_history_and_stats()
    test_persistence_reload()
    test_command_task_never_executes_shell()
    test_singleton_importable()
    print("ALL AUTOMATION TESTS PASSED")
