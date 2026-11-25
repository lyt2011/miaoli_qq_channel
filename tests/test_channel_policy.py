from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module					# noqa: E402


policy = load_module("wake_policy_under_test", Path(__file__).parents[1] / "core/channel/wake_policy.py")


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
	assert policy.is_reply_allowed("group", "a" * 500, 500)
	assert not policy.is_reply_allowed("group", "a" * 501, 500)
	assert policy.is_reply_allowed("private", "a" * 5000, 500)
