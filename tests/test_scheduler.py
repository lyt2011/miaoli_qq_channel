from pathlib	import Path
from types		import SimpleNamespace

import sys


sys.path.insert(0, str(Path(__file__).parent))

from fakes	import FakeEvent, make_config, make_entry	# noqa: E402
from loader	import load_package							# noqa: E402


modules = load_package("scheduler_under_test", {
	"policy"	: "core/social/policy.py",
	"state"		: "core/social/state.py",
	"queue"		: "core/buffers/message_queue.py",
	"scheduler"	: "core/social/scheduler.py",
})

Scheduler			= modules["scheduler"].Scheduler
SocialStore			= modules["state"].SocialStore
MessageBufferStore	= modules["queue"].MessageBufferStore
WakeReason			= modules["policy"].WakeReason


class Harness:
	
	def __init__(self, monkeypatch, **social_overrides) -> None:
		monkeypatch.setattr(modules["state"].random, "uniform", lambda low, high: low)
		monkeypatch.setattr(modules["state"], "roll_chance", lambda chance: False)
		
		self.config		= make_config(**social_overrides)
		self.buffers	= MessageBufferStore(cap=30)
		self.social		= SocialStore()
		self.ready		= []
		self.notified	= []
		self.scheduler	= Scheduler(
			config		= self.config,
			buffers		= self.buffers,
			social		= self.social,
			ready		= self.ready,
			make_message= self.make_message,
			notify		= lambda: self.notified.append(1),
		)
	
	def make_message(self, entries, omitted, reason, delivered):
		return SimpleNamespace(
			thread_id		= "group-1",
			entries			= entries,
			reason			= reason,
			delivered_seq	= delivered,
		)
	
	def feed(self, event, addressed: bool, now: float):
		entry = self.buffers.record("group-1", event, addressed, now=now)
		self.social.on_message("group-1", entry, self.config, now)
		
		return entry
	
	def drain(self):
		window = list(self.ready)
		self.ready.clear()
		
		return window


def test_waits_for_quiet_before_submitting(monkeypatch):
	harness = Harness(monkeypatch)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	
	assert harness.scheduler.tick(now=103.0) == 0
	assert harness.ready == []
	
	assert harness.scheduler.tick(now=109.0) == 1
	assert len(harness.ready) == 1
	assert harness.ready[0].reason is WakeReason.AT
	assert harness.notified == [1]
	assert harness.social.session("group-1").pending is None
	assert harness.social.session("group-1").in_flight


def test_in_flight_window_blocks_until_reply_finishes(monkeypatch):
	harness = Harness(monkeypatch, max_submit_per_minute=2)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	harness.scheduler.tick(now=109.0)
	harness.drain()
	
	harness.feed(FakeEvent(at_me=True), True, 110.0)
	assert harness.scheduler.tick(now=119.0) == 0
	
	harness.social.on_reply_finished("group-1", True, 120.0, harness.config)
	assert harness.scheduler.tick(now=121.0) == 1


def test_rate_limit_blocks_second_submit_within_a_minute(monkeypatch):
	harness = Harness(monkeypatch, max_submit_per_minute=1)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	assert harness.scheduler.tick(now=109.0) == 1
	harness.drain()
	
	harness.social.on_reply_finished("group-1", True, 110.0, harness.config)
	harness.feed(FakeEvent(at_me=True), True, 120.0)
	
	assert harness.scheduler.tick(now=129.0) == 0
	assert harness.ready == []


def test_plain_message_never_submits_while_diving(monkeypatch):
	harness = Harness(monkeypatch)
	harness.feed(FakeEvent(text="随便聊聊"), False, 100.0)
	
	for now in (109.0, 130.0, 300.0):
		assert harness.scheduler.tick(now=now) == 0
	
	assert harness.ready == []


def test_active_state_does_not_follow_up_by_default(monkeypatch):
	harness = Harness(monkeypatch)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	harness.scheduler.tick(now=109.0)
	harness.drain()
	harness.social.on_reply_finished("group-1", True, 120.0, harness.config)
	
	# 刚说完话 别人继续聊天：默认不主动接话 不跑图
	harness.feed(FakeEvent(text="然后呢"), False, 200.0)
	for now in (203.0, 209.0, 260.0):
		assert harness.scheduler.tick(now=now) == 0
	assert harness.ready == []


def test_following_thread_waits_merge_quiet(monkeypatch):
	harness = Harness(monkeypatch, enable_follow=True)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	assert harness.scheduler.tick(now=109.0) == 1
	harness.drain()
	harness.social.on_reply_finished("group-1", True, 110.0, harness.config)
	
	# 跟随中走合并窗口：连发要安静 10 秒才交，理由=跟随
	harness.feed(FakeEvent(text="然后呢"), False, 111.0)
	assert harness.scheduler.tick(now=112.0) == 0
	assert harness.scheduler.tick(now=121.0) == 1
	assert harness.ready[0].reason is WakeReason.FOLLOW


def test_follow_interval_blocks_next_tick(monkeypatch):
	harness = Harness(monkeypatch, enable_follow=True, follow_min_interval_seconds=10.0)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	assert harness.scheduler.tick(now=109.0) == 1
	harness.drain()
	harness.social.on_reply_finished("group-1", True, 110.0, harness.config)
	
	harness.feed(FakeEvent(text="然后呢"), False, 111.0)
	# 合并窗口没到
	assert harness.scheduler.tick(now=112.0) == 0
	# 安静满 10 秒，且距上次提交 12 秒 ≥ 最小间隔 10 秒
	assert harness.scheduler.tick(now=121.0) == 1


def test_follow_merges_burst_into_one_window(monkeypatch):
	harness = Harness(monkeypatch, enable_follow=True)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	assert harness.scheduler.tick(now=109.0) == 1
	harness.drain()
	harness.social.on_reply_finished("group-1", True, 110.0, harness.config)
	
	# 跟随中连发三条：合并窗口从最后一条算起
	for now in (111.0, 113.0, 115.0):
		harness.feed(FakeEvent(text="刷屏"), False, now)
	assert harness.scheduler.tick(now=121.0) == 0
	assert harness.scheduler.tick(now=126.0) == 1
	assert len(harness.ready) == 1
	assert len(harness.ready[0].entries) == 3


def test_follow_expires_after_duration(monkeypatch):
	harness = Harness(monkeypatch, enable_follow=True, follow_duration_minutes=1)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	harness.scheduler.tick(now=109.0)
	harness.drain()
	harness.social.on_reply_finished("group-1", True, 110.0, harness.config)
	
	# 110 + 60 秒后跟随到期 回潜水，普通消息重新走 quiet/chance
	harness.feed(FakeEvent(text="还在吗"), False, 200.0)
	for now in (202.0, 210.0, 260.0):
		assert harness.scheduler.tick(now=now) == 0
	assert harness.ready == []
	assert harness.social.session("group-1").state.value == "diving"


def test_ready_buffer_dedupes_same_thread(monkeypatch):
	harness = Harness(monkeypatch)
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	harness.ready.append(SimpleNamespace(thread_id="group-1"))
	
	assert harness.scheduler.tick(now=109.0) == 0
	assert len(harness.ready) == 1


def test_full_ready_buffer_blocks_submit(monkeypatch):
	harness = Harness(monkeypatch)
	harness.config.channel.buf_size = 0
	harness.feed(FakeEvent(at_me=True), True, 100.0)
	
	assert harness.scheduler.tick(now=109.0) == 0
	assert harness.ready == []
