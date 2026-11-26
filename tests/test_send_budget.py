from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module							# noqa: E402


modules	= load_module("send_budget_under_test", Path(__file__).parents[1] / "utils" / "send_budget.py")

allow	= modules.allow
reset	= modules.reset
clear	= modules.clear
used	= modules.used


def test_allow_counts_up_to_limit():
	reset("group-1")
	
	assert allow("group-1", "messages", 2) is True
	assert allow("group-1", "messages", 2) is True
	assert allow("group-1", "messages", 2) is False
	assert used("group-1", "messages") == 2


def test_allow_is_per_kind():
	reset("group-1")
	
	assert allow("group-1", "messages", 1) is True
	assert allow("group-1", "messages", 1) is False
	assert allow("group-1", "memes", 1) is True


def test_reset_clears_counts():
	reset("group-1")
	allow("group-1", "memes", 1)
	assert allow("group-1", "memes", 1) is False
	
	reset("group-1")
	assert allow("group-1", "memes", 1) is True


def test_clear_forgets_thread():
	reset("group-1")
	allow("group-1", "messages", 1)
	clear("group-1")
	
	assert used("group-1", "messages") == 0
	assert allow("group-1", "messages", 1) is True


def test_zero_limit_and_missing_thread_allow():
	reset("group-1")
	
	assert allow("group-1", "messages", 0) is True
	assert allow(None, "messages", 1) is True
