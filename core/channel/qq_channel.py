from miaoli_bot.api			import store_recall
from miaoli_bot.protocols	import BaseChannel

from ...consts				import EVENT_BUFFER
from .qq_channel_message	import QQChannelMessage


class QQChannel(BaseChannel):
	
	"""把 QQ 事件环形缓冲暴露成 miaoli_bot 的消息通道"""
	
	@property
	def name(self) -> str:
		return "qq"
	
	async def drain(self) -> QQChannelMessage:
		
		"""取走缓冲区里全部未读事件 取完即空 按「旧 → 新」返回"""
		
		event_buffer = store_recall(EVENT_BUFFER)
		
		length	= len(event_buffer)
		events	= event_buffer.pop(length)[::-1]
		
		return QQChannelMessage(events)
