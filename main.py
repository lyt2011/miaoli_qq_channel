from ncatbot.core		import registrar
from ncatbot.plugin		import NcatBotPlugin
from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api		import store_set, store_recall, register_channel

from .core			import QQChannel, EventBuffer
from .models		import PluginConfig
from .consts		import EVENT_BUFFER, PLUGIN_CONFIG

from typing	import Callable, List


PLUGIN_NAME	= "喵璃のQQ通道"


class MiaoLiQQChannel(NcatBotPlugin):
	
	"""把 QQ 事件缓冲起来 并以消息通道的形式提供给 miaoli_bot"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list: List[Callable[[], None]]	= []
	
	async def on_load(self) -> None:
		
		config = PluginConfig.model_validate(self.config)
		
		self.undo_list.append(store_set(PLUGIN_CONFIG, config))
		self.undo_list.append(store_set(EVENT_BUFFER, EventBuffer(size=config.buf_size)))
		self.undo_list.append(register_channel(QQChannel()))
		
		self.logger.info(f"{PLUGIN_NAME} 已加载 size={config.buf_size}")
	
	async def on_close(self) -> None:
		
		for undo in self.undo_list:
			undo()
		
		self.logger.info(f"{PLUGIN_NAME} 已卸载")
	
	@registrar.on_message()
	async def record_anything(self, event: MessageEvent) -> None:
		
		"""私聊 event 和群聊 event 都记录"""
		
		event_buffer = store_recall(EVENT_BUFFER, default=None)
		if event_buffer is not None:
			event_buffer.record(event)
		
		return None
