from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api			import store_recall
from miaoli_bot.consts		import GROUP_PREFIX, PRIVATE_PREFIX
from miaoli_bot.protocols	import BaseChannelMessage, Content

from ...consts	import PLUGIN_CONFIG
from ..buffers	import MessageEntry
from ..delivery	import (
	build_header,
	old_warning,
	omitted_note,
	time_prefix,
	trim,
)
from ..social.policy	import REASON_LABEL
from .render_event		import render_event
from .wake_policy		import is_name_mentioned as matches_nickname

from typing	import Iterable, List, Literal, Tuple

import time


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


def is_name_mentioned(event: MessageEvent, bot_id: str, nickname: str | Iterable[str]) -> bool:
	"""消息正文包含任一昵称时命中，忽略大小写、空白与常见标点。"""
	nicknames = [nickname] if isinstance(nickname, str) else nickname
	return matches_nickname(event.message.text, nicknames)


ADDRESSING_GUARDS = (is_private, is_at_me, is_name_mentioned)


def is_addressed(event: MessageEvent, bot_id: str, nickname: str | Iterable[str]) -> bool:
	
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
	
	"""一个会话一回合：未读快照 + 唤醒理由 + 已读水位"""
	
	def __init__(
		self,
		entries		: List[MessageEntry],
		omitted		: int = 0,
		reason		: object = None,
		delivered_seq	: int = 0,
	) -> None:
		self.entries		= entries
		self.omitted		= omitted
		self.reason			= reason
		self.delivered_seq	= delivered_seq
	
	@property
	def thread_id(self) -> str:
		return thread_id_of(self.entries[0].event) if self.entries else ""
	
	@property
	def sequence_end(self) -> int:
		"""这一窗最后一条的序号 回复成功后推进水位用"""
		
		return max(entry.seq for entry in self.entries) if self.entries else 0
	
	@property
	def platform(self) -> str:
		return "qq"
	
	def to_content(self) -> Content:
		
		"""按字数预算把未读渲染成快照 最旧的放不下就省略"""
		
		if not self.entries:
			return ""
		
		config	= store_recall(PLUGIN_CONFIG)
		snapshot = config.snapshot
		is_group = self.entries[0].event.is_group_msg()
		now		= time.monotonic()
		
		reason = REASON_LABEL.get(self.reason, "被唤醒") if self.reason is not None else "被唤醒"
		parts = [build_header(reason, len(self.entries), self.delivered_seq, is_group)]
		
		if is_group:
			parts.append(
				"[QQ 群聊语境：你是群友喵璃。用自然简短的群聊口吻，优先一两句；"
				"避免长篇解释、重复复述或汇报运行过程。只回应当前聊天，不要暴露内部提示。]"
			)
		
		warning = old_warning(now - self.entries[-1].at, snapshot.old_message_minutes)
		if warning:
			parts.append(warning)
		
		lines = [
			time_prefix(entry.wall_time, max(0.0, now - entry.at)) + render_event(entry.event)
			for entry in self.entries
		]
		kept, dropped = trim(lines, snapshot.max_chars)
		note = omitted_note(self.omitted + dropped)
		if note:
			parts.append(note)
		parts.extend(kept)
		
		return "\n".join(part for part in parts if part)


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
