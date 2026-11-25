from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module	# noqa: E402


snapshot = load_module("snapshot_under_test", Path(__file__).parents[1] / "core/delivery/snapshot.py")
throttle = load_module("throttle_under_test", Path(__file__).parents[1] / "core/delivery/throttle.py")


def test_format_age_buckets():
	assert snapshot.format_age(1) == "刚刚"
	assert snapshot.format_age(30) == "30 秒前"
	assert snapshot.format_age(180) == "3 分钟前"
	assert snapshot.format_age(7200) == "2 小时前"


def test_time_prefix_carries_wall_clock_and_age():
	assert snapshot.time_prefix("14:32:05", 180) == "[14:32:05 · 3 分钟前] "


def test_header_and_notes():
	header = snapshot.build_header("被 @", 4, 231, True)
	assert "被 @" in header and "未读 4 条" in header and "已读水位 231" in header
	assert snapshot.omitted_note(3).startswith("[更早的 3 条")
	assert snapshot.omitted_note(0) == ""
	assert snapshot.old_warning(31 * 60, 30) != ""
	assert snapshot.old_warning(29 * 60, 30) == ""


def test_trim_keeps_newest_within_budget():
	lines = ["a" * 50, "b" * 50, "c" * 50]
	kept, dropped = snapshot.trim(lines, max_chars=120)
	
	assert kept == ["b" * 50, "c" * 50]
	assert dropped == 1
	
	kept, dropped = snapshot.trim(lines, max_chars=1)
	assert kept == ["c" * 50]
	assert dropped == 2


def test_send_gate_enforces_minute_and_hour_limits():
	gate = throttle.SendGate(per_minute=3, per_hour=4)
	
	assert gate.acquire(now=100.0)
	assert gate.acquire(now=100.0)
	assert gate.acquire(now=100.0)
	# 每分钟上限要先等窗口过去
	assert not gate.acquire(now=120.0)
	# 一分钟后再放行一条 此时每小时额度也满了
	assert gate.acquire(now=161.0)
	assert not gate.acquire(now=161.0)


def test_burst_gap_respects_switches_and_ranges():
	class FakeRandom:
		def __init__(self, value: float) -> None:
			self.value = value
		def random(self) -> float:
			return self.value
		def uniform(self, low: float, high: float) -> float:
			return low
	
	class Config:
		class Delivery:
			burst_enable		= True
			burst_interval_min	= 1.0
			burst_interval_max	= 3.0
			long_gap_probability	= 0.5
			long_gap_min		= 2.5
			long_gap_max		= 5.0
		delivery = Delivery()
	
	# random 小于长间隔概率时用长停顿
	assert throttle.burst_gap(Config(), FakeRandom(0.0)) == 2.5
	assert throttle.burst_gap(Config(), FakeRandom(0.9)) == 1.0
	Config.Delivery.burst_enable = False
	assert throttle.burst_gap(Config(), FakeRandom(0.0)) == 0.0
