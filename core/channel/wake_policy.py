from typing	import Iterable

import re


def normalize_nickname(text: str) -> str:
	return re.sub(r"[\s，。！？、,.!?~～:：;；\"'“”‘’()（）\[\]【】<>《》]+", "", text).casefold()


def is_name_mentioned(text: str, nicknames: Iterable[str]) -> bool:
	normalized_text = normalize_nickname(text)
	return bool(normalized_text) and any(
		candidate and normalize_nickname(candidate) in normalized_text
		for candidate in nicknames
	)


def is_authorized(
	is_group: bool,
	group_id: str,
	user_id: str,
	bot_id: str,
	group_whitelist: Iterable[str],
) -> bool:
	"""群聊白名单 fail-closed；私聊不限制用户，但忽略机器人自身回声。"""
	if str(user_id) == str(bot_id):
		return False
	return not is_group or str(group_id) in {str(item) for item in group_whitelist}


def is_reply_allowed(mode: str, text: str, max_group_chars: int) -> bool:
	return mode != "group" or len(text) <= max_group_chars
