from pathlib	import Path
from types		import SimpleNamespace

import sys


sys.path.insert(0, str(Path(__file__).parent))

from fakes	import FakeEvent, make_config	# noqa: E402
from loader	import load_package				# noqa: E402


modules = load_package("replay_under_test", {
	"policy"	: "core/social/policy.py",
	"state"		: "core/social/state.py",
	"queue"		: "core/buffers/message_queue.py",
	"scheduler"	: "core/social/scheduler.py",
})

Scheduler			= modules["scheduler"].Scheduler
SocialStore			= modules["state"].SocialStore
MessageBufferStore	= modules["queue"].MessageBufferStore
WakeReason			= modules["policy"].WakeReason


class Replay:
	
	"""按秒回放一串带时间戳的事件 顺便替主包把就绪区取走、模拟回复完成"""
	
	def __init__(self, monkeypatch, **social_overrides) -> None:
		monkeypatch.setattr(modules["state"].random, "uniform", lambda low, high: low)
		monkeypatch.setattr(modules["state"], "roll_chance", lambda chance: False)
		
		self.config		= make_config(**social_overrides)
		self.buffers	= MessageBufferStore(cap=30)
		self.social		= SocialStore()
		self.ready		= []
		self.submits	= []
		self.clock		= 0.0
		self.scheduler	= Scheduler(
			config		= self.config,
			buffers		= self.buffers,
			social		= self.social,
			ready		= self.ready,
			make_message= self.make_message,
			notify		= self.on_notify,
		)
	
	def make_message(self, entries, omitted, reason, delivered):
		return SimpleNamespace(
			thread_id		= "group-1",
			entries			= entries,
			reason			= reason,
			delivered_seq	= delivered,
		)
	
	def on_notify(self) -> None:
		self.submits.append(self.clock)
	
	def say(self, text: str, addressed: bool, at_me: bool = False) -> None:
		event = FakeEvent(text=text, at_me=at_me)
		entry = self.buffers.record("group-1", event, addressed, now=self.clock)
		self.social.on_message("group-1", entry, self.config, self.clock)
	
	def run(self, seconds: float) -> None:
		
		"""一秒一秒推进 期间主包取窗即视为立刻回复完成"""
		
		end = self.clock + seconds
		while self.clock < end:
			self.clock += 1.0
			self.scheduler.tick(now=self.clock)
			
			if self.ready:
				for message in self.ready:
					self.assert_single_window(message)
				self.ready.clear()
				self.social.on_reply_finished("group-1", True, self.clock, self.config)
	
	def assert_single_window(self, message) -> None:
		assert message.entries, "空窗口不该被提交"


def test_burst_of_plain_chat_does_not_run_once_per_message(monkeypatch):
	replay = Replay(monkeypatch)
	
	# 潜水状态：20 条普通消息，没有一条应该自己开窗
	for index in range(20):
		replay.say(f"闲聊 {index}", addressed=False)
		replay.run(10.0)
	
	assert replay.submits == []
	assert replay.buffers.count("group-1") == 20


def test_addressed_wake_then_plain_chat_does_not_reopen(monkeypatch):
	replay = Replay(monkeypatch)
	
	replay.say("喵璃在吗", addressed=True, at_me=True)
	replay.run(10.0)
	assert replay.submits == [8.0]
	
	# 之后 4 分钟一直有人聊天：默认不跟话 一条都不该再开窗
	for index in range(24):
		replay.say(f"接着聊 {index}", addressed=False)
		replay.run(10.0)
	
	assert replay.submits == [8.0]


def test_follow_up_when_enabled_is_rate_limited(monkeypatch):
	replay = Replay(monkeypatch, follow_up=True)
	
	replay.say("喵璃在吗", addressed=True, at_me=True)
	replay.run(10.0)
	assert replay.submits == [8.0]
	
	for index in range(24):
		replay.say(f"接着聊 {index}", addressed=False)
		replay.run(10.0)
	
	assert 2 <= len(replay.submits) <= 5
	assert len(replay.submits) < 24


def test_full_quiet_window_batches_messages_into_one_window(monkeypatch):
	replay = Replay(monkeypatch)
	
	for index in range(6):
		replay.say(f"连发 {index}", addressed=index == 5, at_me=index == 5)
		replay.run(2.0)
	replay.run(10.0)
	
	assert replay.submits == [18.0]
