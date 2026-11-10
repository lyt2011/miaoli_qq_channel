from ncatbot.utils	import get_log
from ncatbot.core	import registrar
from ncatbot.plugin	import NcatBotPlugin
from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api	import please_run_graph, register_channel, store_recall, store_set

from account_injector.consts	import PLUGIN_CONFIG as ACCOUNT_CONFIG

from .models	import PluginConfig
from .core	import (
	QQChannel,
	QQChannelMessage,
	ThreadBacklog,
	is_addressed,
	thread_id_of,
)
from .consts	import MESSAGE_BUFFER, PLUGIN_CONFIG, RAW_CONFIG, READY_BUFFER

from typing	import Callable, List, Optional, Union

import asyncio


PLUGIN_NAME	= "喵璃のQQ通道"
LOGGER		= get_log(PLUGIN_NAME)


class MiaoLiQQChannel(NcatBotPlugin):
	
	"""把 QQ 事件缓冲起来 并以消息通道的形式提供给 miaoli_bot"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list	: List[Callable[[], None]]	= []
		
		self.deamon	: Optional[asyncio.Task]	= None
	
	async def on_load(self) -> None:
		
		# 校验配置
		config = PluginConfig.model_validate(self.config)
		
		# 把配置塞共享容器
		self.undo_list.append(store_set(RAW_CONFIG, self.config))
		self.undo_list.append(store_set(PLUGIN_CONFIG, config))
		
		# 构建积压区/就绪区
		self.undo_list.append(store_set(MESSAGE_BUFFER, ThreadBacklog(cap=config.message.buf_size)))
		self.undo_list.append(store_set(READY_BUFFER, []))
		
		# 注册消息渠道
		self.undo_list.append(register_channel(QQChannel()))
		
		self.logger.info(f"{PLUGIN_NAME} 已加载")
	
	async def on_close(self) -> None:
		
		if self.deamon:
			self.deamon.cancel()
		
		for undo in self.undo_list:
			undo()
		
		self.logger.info(f"{PLUGIN_NAME} 已卸载")
	
	@registrar.on_startup()
	async def create_deamon(self) -> None:
		
		def _restart_deamon(task: asyncio.Task) -> None:
			
			# 被取消的任务不重启
			if task.cancelled():
				self.logger.info(f"提交任务已取消")
				return None
			
			if exception := task.exception():
				
				# 创建提交任务并把自己作为完成回调
				self.deamon = asyncio.create_task(self.auto_submit())
				self.deamon.add_done_callback(_restart_deamon)
				
				self.logger.error(f"提交任务运行异常: "
					f"{type(exception).__name__}: {exception}", exc_info=exception)
				
				return None
			
			# 对于已完成的不重启
			self.logger.info(f"提交任务正常结束")
			
			return None
		
		# 创建自动提交并添加回调
		self.deamon = asyncio.create_task(self.auto_submit())
		self.deamon.add_done_callback(_restart_deamon)
	
	@registrar.on_message()
	async def backlog_anything(self, event: MessageEvent) -> None:
		
		"""私聊 event 和群聊 event 都记录进各自会话的积压区"""
		
		account	= store_recall(ACCOUNT_CONFIG, default=None)
		backlog	= store_recall(MESSAGE_BUFFER, default=None)
		
		if account is None or backlog is None:
			return None
		
		# 入区时就把「是不是冲我来的」算好 之后不再重算
		backlog.record(
			thread_id	= thread_id_of(event),
			event		= event,
			addressed	= is_addressed(event, account.bot_id, account.bot_nickname),
		)
		
		return None
	
	async def auto_submit(self) -> None:
		
		"""把积压区里该开窗的会话搬进就绪区 搬完就唤醒主包"""
		
		config = store_recall(PLUGIN_CONFIG)
		
		while True:
			
			# 每轮先等待扫描间隔 避免 continue 跳过等待导致忙循环
			await asyncio.sleep(config.submit.interval)
			
			backlog	= store_recall(MESSAGE_BUFFER, default=None)
			ready	= store_recall(READY_BUFFER, default=None)
			
			if backlog is None or ready is None:
				continue
			
			woke = False
			
			for thread_id in backlog.ready_threads():
				
				# 就绪区满了 本轮到此为止 剩下的下轮再来
				if len(ready) >= config.channel.buf_size:
					break
				
				# 同一个会话已经在就绪区里排着队 不重复投递
				if any(message.thread_id == thread_id for message in ready):
					continue
				
				events = backlog.pop_window(thread_id)
				if not events:
					continue
				
				ready.append(QQChannelMessage(events))
				woke = True
			
			if woke:
				please_run_graph()
		
		return None
