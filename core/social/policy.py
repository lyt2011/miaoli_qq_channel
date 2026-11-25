from enum	import StrEnum
from typing	import Any, Iterable, Optional

import re
import random


class WakeReason(StrEnum):
	
	"""一次提交的唤醒理由 同时决定快照里的提示与日志"""
	
	AT			= "at"
	NAME		= "name"
	KEYWORD		= "keyword"
	QUESTION	= "question"
	QUOTE		= "quote"
	CHANCE		= "chance"
	ACTIVE		= "active"


REASON_LABEL = {
	WakeReason.AT		: "被 @",
	WakeReason.NAME		: "被叫到名字",
	WakeReason.KEYWORD	: "命中关键词",
	WakeReason.QUESTION	: "看起来在问 AI",
	WakeReason.QUOTE	: "消息被引用",
	WakeReason.CHANCE	: "随机开窗",
	WakeReason.ACTIVE	: "聊天状态跟一句",
}

PRIORITY = {
	WakeReason.AT		: 100,
	WakeReason.NAME		: 90,
	WakeReason.KEYWORD	: 70,
	WakeReason.QUESTION	: 60,
	WakeReason.QUOTE	: 50,
	WakeReason.CHANCE	: 10,
	WakeReason.ACTIVE	: 0,
}

# 像在问 AI 的句子 只做粗判定 宁可漏判也别误判
QUESTION_PATTERN = re.compile(
	r"[?？]|吗|呢|怎么|为什么|为啥|什么|啥|谁|哪|多少|多久|几点|是不是|能不能|可不可以"
)


def message_text(event: Any) -> str:
	
	"""取正文 拿不到就给空串"""
	
	message = getattr(event, "message", None)
	if message is None:
		return ""
	
	return getattr(message, "text", "") or ""


def is_question(text: str) -> bool:
	return bool(text) and bool(QUESTION_PATTERN.search(text))


def is_keyword(text: str, keywords: Iterable[str]) -> bool:
	folded = text.casefold()
	return any(candidate and candidate.casefold() in folded for candidate in keywords)


def is_quote(event: Any) -> bool:
	
	"""消息里带引用段就算命中 近似判定：不解析引用链 也不确认引的是谁"""
	
	message = getattr(event, "message", None)
	if message is None:
		return False
	
	return any(type(segment).__name__ == "Reply" for segment in message)


def is_at_me(event: Any, bot_id: str) -> bool:
	
	"""duck 类型判 @ 免得把 ncatbot 拖进纯逻辑模块的测试依赖"""
	
	message = getattr(event, "message", None)
	if message is None:
		return False
	
	is_at = getattr(message, "is_at", None)
	if not callable(is_at):
		return False
	
	try:
		return bool(is_at(bot_id, all_except=True))
	except Exception:
		return False


def classify(event: Any, addressed: bool, wake: Any, bot_id: str) -> Optional[WakeReason]:
	
	"""这条消息为什么值得开窗 返回 None 表示没有证据"""
	
	if addressed:
		if not event.is_group_msg() or is_at_me(event, bot_id):
			return WakeReason.AT
		if wake.name:
			return WakeReason.NAME
		return None
	
	text = message_text(event)
	if wake.keyword and is_keyword(text, wake.keyword_list):
		return WakeReason.KEYWORD
	
	if wake.question and is_question(text):
		return WakeReason.QUESTION
	
	if wake.quote and is_quote(event):
		return WakeReason.QUOTE
	
	return None


def roll_chance(chance: float) -> bool:
	return random.random() < chance
