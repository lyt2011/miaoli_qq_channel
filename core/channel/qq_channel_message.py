from ncatbot.event.qq	import MessageEvent

from miaoli_bot.protocols	import ChannelMessage

from typing	import List


class QQChannelMessage(ChannelMessage):
	
	"""QQ 事件的最小包装 直接给出序列化后的 JSON"""
	
	def __init__(self, events: List[MessageEvent]) -> None:
		self.events = events
	
	@property
	def raw(self) -> List[MessageEvent]:
		return list(self.events)
	
	def to_structured(self) -> List[str]:
		return [event._data.model_dump_json() for event in self.events]
