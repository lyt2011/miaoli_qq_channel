from ncatbot.event.qq	import MessageEvent

from .render_segment	import render_segment

from datetime	import datetime


TIME_FORMAT = "%Y-%m-%d %H:%M"


def _who(event: MessageEvent) -> str:
	"""群名片优先 其次昵称 最后退回 QQ 号"""
	
	sender = event.sender
	
	card = getattr(sender, "card", None)
	if card:
		return card
	
	return sender.nickname or event.user_id


def _meta(event: MessageEvent) -> str:
	"""元信息 队列里放群信息(有的话) 时间 消息 id"""
	
	pieces = []
	
	group_id = getattr(event._data, "group_id", None)
	if event.is_group_msg() and group_id:
		group_name = getattr(event._data, "group_name", None)
		pieces.append(f"群{group_id} {group_name}" if group_name else f"群{group_id}")
	
	pieces.append(datetime.fromtimestamp(event.time).strftime(TIME_FORMAT))
	pieces.append(f"#{event.message_id}")
	
	return " ".join(pieces)


def render_event(event: MessageEvent) -> str:
	
	"""一个事件 → 元信息行 + 每段一行
	
	元信息用 # 开头是为了让模型一眼看出这条不属于正文 也方便人读日志
	"""
	
	head = f"# [{_meta(event)}] {_who(event)}({event.user_id}):"
	
	if not event.message:
		return head
	
	return head + "\n" + "\n".join(render_segment(segment) for segment in event.message)
