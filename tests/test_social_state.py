from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from fakes	import FakeEvent, make_config, make_entry	# noqa: E402
from loader	import load_package							# noqa: E402


modules = load_package("social_under_test", {
	"policy"	: "core/social/policy.py",
	"state"		: "core/social/state.py",
})

state = modules["state"]
SocialStore = state.SocialStore
ChatState = state.ChatState
WakeReason = modules["policy"].WakeReason


def quiet_store(monkeypatch):
	monkeypatch.setattr(state.random, "uniform", lambda low, high: low)
	monkeypatch.setattr(state, "roll_chance", lambda chance: False)
	
	return SocialStore()


def test_addressed_message_pends_and_enters_chat_state(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config()
	
	reason = store.on_message("group-1", make_entry(FakeEvent(at_me=True), addressed=True), config, now=100.0)
	session = store.session("group-1")
	
	assert reason is WakeReason.AT
	assert session.pending.reason is WakeReason.AT
	assert session.state is ChatState.ACTIVE
	assert store.decide("group-1", 100.0, config).reason is WakeReason.AT


def test_plain_message_stays_diving_when_chance_misses(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config(chance=0.0)
	
	assert store.on_message("group-1", make_entry(FakeEvent(text="随便聊聊"), addressed=False), config, now=100.0) is None
	assert store.session("group-1").state is ChatState.DIVING
	assert store.decide("group-1", 200.0, config) is None


def test_chance_can_wake_diving_session(monkeypatch):
	store = quiet_store(monkeypatch)
	monkeypatch.setattr(state, "roll_chance", lambda chance: True)
	config = make_config(chance=1.0)
	
	reason = store.on_message("group-1", make_entry(FakeEvent(text="随便聊聊"), addressed=False), config, now=100.0)
	
	assert reason is WakeReason.CHANCE
	assert store.session("group-1").state is ChatState.DIVING


def test_active_session_does_not_follow_up_by_default(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config()
	session = store.session("group-1")
	session.state = ChatState.ACTIVE
	session.last_message_at = 100.0
	session.last_reply_at = 100.0
	
	# 聊天中也不主动接话：普通消息不提交 只有被叫或随机概率才会开窗
	for now in (103.0, 109.0, 161.0, 600.0):
		assert store.decide("group-1", now, config) is None


def test_active_session_follows_up_when_enabled(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config(follow_up=True, follow_quiet=8.0, speak_cooldown_seconds=60.0)
	session = store.session("group-1")
	session.state = ChatState.ACTIVE
	session.last_message_at = 100.0
	session.last_reply_at = 100.0
	
	# 静默没到
	assert store.decide("group-1", 103.0, config) is None
	# 静默到了但刚说完话
	assert store.decide("group-1", 109.0, config) is None
	# 冷却过了
	assert store.decide("group-1", 161.0, config).reason is WakeReason.ACTIVE


def test_follow_up_uses_its_own_quiet_window(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config(follow_up=True, follow_quiet=30.0, speak_cooldown_seconds=0.0)
	session = store.session("group-1")
	session.state = ChatState.ACTIVE
	session.last_message_at = 100.0
	session.last_reply_at = 100.0
	
	# 比 quiet(8s) 长很多的跟随静默：31 秒刚够 30 秒
	assert store.decide("group-1", 120.0, config) is None
	assert store.decide("group-1", 131.0, config).reason is WakeReason.ACTIVE


def test_submit_rate_limit_is_per_minute_and_private_is_exempt(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config(max_submit_per_minute=1)
	decision = state.WakeDecision(WakeReason.AT, 100, 100.0)
	
	store.on_submit("group-1", 100.0, decision)
	store.session("group-1").in_flight = False
	assert not store.can_submit("group-1", 110.0, config)
	assert store.can_submit("group-1", 161.0, config)
	assert store.can_submit("private-1", 100.0, config)


def test_reply_finished_records_speech_and_resets_in_flight(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config()
	decision = state.WakeDecision(WakeReason.AT, 100, 100.0)
	store.on_submit("group-1", 100.0, decision)
	
	store.on_reply_finished("group-1", True, 130.0, config)
	session = store.session("group-1")
	
	assert not session.in_flight
	assert session.last_reply_at == 130.0
	assert session.state is ChatState.ACTIVE
	
	other = store.session("group-2")
	other.in_flight = True
	
	store.on_reply_finished("group-2", False, 140.0, config)
	assert not store.session("group-2").in_flight
	assert store.session("group-2").last_reply_at == 0.0


def test_expire_clears_timeouts_and_returns_to_diving(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config()
	session = store.session("group-1")
	session.in_flight = True
	session.in_flight_since = 100.0
	session.state = ChatState.ACTIVE
	session.active_until = 150.0
	session.last_message_at = 100.0
	
	store.expire("group-1", 400.0, config)
	
	assert not session.in_flight
	assert session.state is ChatState.DIVING


def test_idle_chat_state_returns_to_diving(monkeypatch):
	store = quiet_store(monkeypatch)
	config = make_config()
	session = store.session("group-1")
	session.state = ChatState.ACTIVE
	session.active_until = 10000.0
	session.last_message_at = 100.0
	session.state_since = 100.0
	
	store.expire("group-1", 100.0 + 6 * 60 + 1, config)
	
	assert session.state is ChatState.DIVING


def test_prune_drops_idle_sessions(monkeypatch):
	store = quiet_store(monkeypatch)
	session = store.session("group-1")
	session.last_message_at = 100.0
	session.state_since = 100.0
	
	store.prune(100.0 + 7200, idle_seconds=3600)
	
	assert "group-1" not in store.sessions
