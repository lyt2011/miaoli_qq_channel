from ncatbot.utils		import get_log
from ncatbot.core		import registrar
from ncatbot.plugin		import NcatBotPlugin
from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api	import store_set, store_recall, register_channel

from .models	import PluginConfig
from .core		import QQChannel, MessageBuffer, MustReply, JudgeDecider
from .consts	import (
	CHANNEL_BUFFER,
	MESSAGE_BUFFER,
	RAW_CONFIG,
	PLUGIN_CONFIG,
	JUDGE_DECIDER,
)

from typing	import Callable, List, Union

import asyncio


PLUGIN_NAME	= "喵璃のQQ通道"
LOGGER		= get_log(PLUGIN_NAME)


class MiaoLiQQChannel(NcatBotPlugin):
	
	"""把 QQ 事件缓冲起来 并以消息通道的形式提供给 miaoli_bot"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list	: List[Callable[[], None]]	= []
		self.deamon		: Union[asyncio.Task, None]	= None
	
	async def on_load(self) -> None:
		
		# 校验配置
		config = PluginConfig.model_validate(self.config)
		
		# 把配置塞共享容器
		self.undo_list.append(store_set(RAW_CONFIG, self.config))
		self.undo_list.append(store_set(PLUGIN_CONFIG, config))
		
		# 构建渠道/消息缓冲区/决策者
		channel_buffer	= MessageBuffer(size=config.channel.buf_size)
		message_buffer	= MessageBuffer(size=config.message.buf_size)
		judge_decider	= JudgeDecider(atimeout=config.judge.timeout)
		
		# 缓冲区/决策者也塞共享容器
		self.undo_list.append(store_set(CHANNEL_BUFFER, channel_buffer))
		self.undo_list.append(store_set(MESSAGE_BUFFER, message_buffer))
		self.undo_list.append(store_set(JUDGE_DECIDER, judge_decider))
		
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
		
		"""私聊 event 和群聊 event 都记录进积压缓冲区"""
		
		# 记录进积压缓冲区 等待提交器将其提交至通道缓冲区
		backlog_buffer = store_recall(MESSAGE_BUFFER, default=None) # HACK: 注意这里我还没有做评分 所以直接写 CHANNEL_BUFFER
		if backlog_buffer is not None:
			backlog_buffer.record(event)
		
		return None
	
	async def auto_submit(self) -> None:
		
		"""搬运积压缓冲区的数据去渠道缓冲区"""
		
		config = store_recall(PLUGIN_CONFIG)
		
		channel_buffer	= store_recall(CHANNEL_BUFFER)
		message_buffer	= store_recall(MESSAGE_BUFFER)
		judge_decider	= store_recall(JUDGE_DECIDER)
		
		while True:
			
			# 每轮先等待提交间隔 避免 continues 跳过等待导致忙循环
			await asyncio.sleep(config.submit.interval)
			
			# 防止键被 drop
			if message_buffer is None or channel_buffer is None:
				return None
			
			# 没数据则跳过
			if not (events := message_buffer.get_data()):
				LOGGER.info(f"积压缓冲区没有任何数据 跳过")
				continue
			
			decision = await judge_decider.decide(events)
			
			if isinstance(decision, float):
				
				# 对于分数不及格的打个日志并中断
				if decision < config.submit.min_submit_score:
					
					LOGGER.info(f"本次 socpe: {decision} < "
						f"min_submit_score: {config.submit.min_submit_score} 跳过")

					continue
				
				else:
					LOGGER.info(f"本次 socpe: {decision} >= "
						f"min_submit_score: {config.submit.min_submit_score} 满足")
			
			elif isinstance(decision, MustReply):
				LOGGER.info(f"因为 {decision.reason} 必须回复")
			
			# 把积压区清空并丢进渠道缓冲区
			message_buffer.drain_into(channel_buffer)
			
		return None
