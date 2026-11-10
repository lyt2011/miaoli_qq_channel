from ncatbot.event.qq	import MessageEvent

from miaoli_bot.consts		import GROUP_PREFIX, PRIVATE_PREFIX
from miaoli_bot.protocols	import BaseChannelMessage, Content

from typing	import List, Literal, Tuple

import json


def thread_id_of(event: MessageEvent) -> str:
	"""QQ 事件 → 会话标识 (group-<群号> / private-<QQ号>)
	
	用 event.is_group_msg() 判来源 与主包拼接规则一致 前缀直接取主包的常量
	"""
	if event.is_group_msg():
		return f"{GROUP_PREFIX}{event.group_id}"
	
	return f"{PRIVATE_PREFIX}{event.user_id}"


def split_thread_id(thread_id: str) -> Tuple[Literal["group", "private"], str]:
	"""会话标识 → (发送模式, 会话号) 与 thread_id_of 互为逆运算"""
	if thread_id.startswith(GROUP_PREFIX):
		return "group", thread_id[len(GROUP_PREFIX):]
	
	if thread_id.startswith(PRIVATE_PREFIX):
		return "private", thread_id[len(PRIVATE_PREFIX):]
	
	raise ValueError(f"不支持的会话标识: {thread_id}")


def split_text(text: str, delimiter: str) -> List[str]:
	"""按分隔符切分 切成几段就发几条 空段丢弃"""
	return [piece.strip() for piece in text.split(delimiter) if piece.strip()]


def content_to_text(content: Content) -> str:
	"""把主包交回的正文压成纯文本 只认 text 块 别的显式不支持"""
	
	if isinstance(content, str):
		return content
	
	pieces = []
	for block in content:
		if not isinstance(block, dict):
			raise NotImplementedError(f"QQ 通道不支持该内容块: {type(block).__name__}")
		
		kind = block.get("type")
		if kind != "text":
			raise NotImplementedError(f"QQ 通道不支持内容块类型: {kind}")
		
		pieces.append(block.get("text", ""))
	
	return "".join(pieces)


def is_private(event: MessageEvent, bot_id: str, nickname: str) -> bool:
	"""私聊一律算「冲我来的」"""
	return not event.is_group_msg()


def is_at_me(event: MessageEvent, bot_id: str, nickname: str) -> bool:
	"""群里 @ 了我"""
	return event.message.is_at(bot_id, all_except=True)


def is_name_mentioned(event: MessageEvent, bot_id: str, nickname: str) -> bool:
	"""消息正文里出现了我的名字 名字为空时不命中"""
	return bool(nickname) and nickname in event.message.text


ADDRESSING_GUARDS = (is_private, is_at_me, is_name_mentioned)


def is_addressed(event: MessageEvent, bot_id: str, nickname: str) -> bool:
	
	"""这条消息有没有证据表明是冲我来的
	
	False 表示「看不出证据」而不是「确定不是冲我来的」——
	没证据的消息仍要留在上下文里 只是不该由它开窗
	"""
	
	if not isinstance(event, MessageEvent):
		return False
	
	# 自己刚发出去的不能再算一次 否则自激
	if str(event.user_id) == str(bot_id):
		return False
	
	return any(guard(event, bot_id, nickname) for guard in ADDRESSING_GUARDS)


class QQChannelMessage(BaseChannelMessage):
	
	"""QQ 事件的最小包装 一个实例 = 一个会话的一回合"""
	
	def __init__(self, events: List[MessageEvent]) -> None:
		self.events = events
	
	@property
	def thread_id(self) -> str:
		return thread_id_of(self.events[0]) if self.events else ""
	
	@property
	def platform(self) -> str:
		return "qq"
	
	def to_content(self) -> Content:
		"""整套事件序列化成一份 JSON 字符串 没有事件时给空串"""
		
		if not self.events:
			return ""
		
		return json.dumps(
			[event._data.model_dump(mode="json") for event in self.events],
			ensure_ascii=False)


class WakeMessage(BaseChannelMessage):
	
	"""定时唤醒 不是 QQ 事件 由主包的唤醒插件推过来
	
	正文必须自带提示词 主包会把它当普通渠道消息一样送进图
	"""
	
	def __init__(self, thread_id: str, content: str) -> None:
		self.content  = content
		self._thread_id  = thread_id
	
	@property
	def thread_id(self) -> str:
		return self._thread_id
	
	@property
	def platform(self) -> str:
		return "qq"
	
	def to_content(self) -> Content:
		return self.content
