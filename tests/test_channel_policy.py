from pathlib	import Path

import importlib.util


ROOT = Path(__file__).parents[1]


def load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


policy = load_module("wake_policy_under_test", ROOT / "core/channel/wake_policy.py")
backlog_module = load_module("thread_backlog_under_test", ROOT / "core/buffers/thread_backlog.py")
ThreadBacklog = backlog_module.ThreadBacklog


def test_group_authorization_fails_closed_and_normalizes_ids():
	assert not policy.is_authorized(True, "g1", "u1", "bot", [])
	assert policy.is_authorized(True, "123", "u1", "bot", [123])
	assert not policy.is_authorized(True, "124", "u1", "bot", [123])


def test_private_messages_need_no_whitelist_but_ignore_bot_echo():
	assert policy.is_authorized(False, "", "admin", "bot", [])
	assert policy.is_authorized(False, "", "other", "bot", [])
	assert not policy.is_authorized(False, "", "bot", "bot", [])


def test_nickname_match_is_normalized_and_ignores_empty_aliases():
	assert policy.is_name_mentioned("喵 璃，在吗？", ["喵璃"])
	assert policy.is_name_mentioned("hello MIAOLI!", ["miaoli"])
	assert not policy.is_name_mentioned("普通聊天", ["喵璃", ""])
	assert not policy.is_name_mentioned("anything", [""])


def test_group_reply_limit_is_inclusive_and_private_is_unlimited():
	assert policy.is_reply_allowed("group", "12345", 5)
	assert not policy.is_reply_allowed("group", "123456", 5)
	assert policy.is_reply_allowed("private", "x" * 5000, 5)


def test_backlog_revision_detects_replacement_at_capacity():
	backlog = ThreadBacklog(cap=2)
	backlog.record("g", "old", False)
	backlog.record("g", "second", False)
	backlog.record("g", "new", False)
	assert backlog.count("g") == 2
	assert backlog.revision("g") == 3


def test_recent_window_reports_omissions_and_keeps_at_least_trigger():
	backlog = ThreadBacklog(cap=10)
	for value in range(5):
		backlog.record("g", value, False)
	assert backlog.pop_window("g", limit=2) == ([3, 4], 3)
	backlog.record("g", "trigger", True)
	assert backlog.pop_window("g", limit=0) == (["trigger"], 0)


def test_recent_window_keeps_latest_addressed_message():
	backlog = ThreadBacklog(cap=10)
	backlog.record("g", "addressed", True)
	backlog.record("g", "followup-1", False)
	backlog.record("g", "followup-2", False)
	assert backlog.pop_window("g", limit=2) == (["addressed", "followup-2"], 1)


def test_random_trigger_cooldown_is_per_thread(monkeypatch):
	clock = [100.0]
	monkeypatch.setattr(backlog_module.time, "monotonic", lambda: clock[0])
	monkeypatch.setattr(backlog_module.random, "random", lambda: 0.0)
	backlog = ThreadBacklog(cap=10)
	assert backlog.roll_dice("g1", chance=0.1, cooldown=60)
	backlog.mark_rolled("g1")
	assert not backlog.roll_dice("g1", chance=1, cooldown=60)
	assert backlog.roll_dice("g2", chance=1, cooldown=60)
	clock[0] += 61
	assert backlog.roll_dice("g1", chance=1, cooldown=60)


def test_followup_window_has_time_and_message_limits(monkeypatch):
	clock = [100.0]
	monkeypatch.setattr(backlog_module.time, "monotonic", lambda: clock[0])
	backlog = ThreadBacklog(cap=10)
	backlog.open_followup("g", minutes=1, max_messages=2)
	assert backlog.consume_followup("g")
	assert backlog.consume_followup("g")
	assert not backlog.consume_followup("g")
	backlog.open_followup("g", minutes=1, max_messages=2)
	clock[0] += 61
	assert not backlog.consume_followup("g")
