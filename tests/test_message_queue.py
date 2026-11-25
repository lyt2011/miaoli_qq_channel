from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module					# noqa: E402


queue_module = load_module("message_queue_under_test", Path(__file__).parents[1] / "core/buffers/message_queue.py")
MessageBufferStore = queue_module.MessageBufferStore


def test_record_assigns_sequence_and_updates_last_message_time():
	store = MessageBufferStore(cap=10)
	first = store.record("g1", "msg-1", addressed=False)
	second = store.record("g1", "msg-2", addressed=True)
	
	assert [first.seq, second.seq] == [1, 2]
	assert store.count("g1") == 2
	assert store.last_message_at("g1") == second.at
	assert first.wall_time.count(":") == 2


def test_shrink_only_drops_oldest_unaddressed_message():
	store = MessageBufferStore(cap=3)
	store.record("g1", "a", addressed=False)
	store.record("g1", "b", addressed=False)
	store.record("g1", "c", addressed=True)
	store.record("g1", "d", addressed=True)
	
	entries = store.take("g1")
	assert [entry.event for entry in entries] == ["b", "c", "d"]


def test_take_clears_unread_and_respects_limit():
	store = MessageBufferStore(cap=10)
	for index in range(5):
		store.record("g1", f"m{index}", addressed=False)
	
	entries = store.take("g1", limit=2)
	assert [entry.event for entry in entries] == ["m3", "m4"]
	assert store.count("g1") == 0


def test_delivered_watermark_only_moves_forward():
	store = MessageBufferStore(cap=10)
	store.mark_delivered("g1", 5)
	store.mark_delivered("g1", 3)
	assert store.delivered_seq("g1") == 5


def test_prune_removes_idle_empty_sessions():
	store = MessageBufferStore(cap=10)
	store.record("g1", "a", addressed=False, now=100.0)
	store.take("g1")
	store.record("g2", "b", addressed=False, now=4900.0)
	
	store.prune(now=5000.0, idle_seconds=3600)
	
	assert store.threads() == ["g2"]
