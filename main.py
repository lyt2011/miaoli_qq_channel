from ncatbot.utils		import get_log
from ncatbot.core		import registrar
from ncatbot.plugin		import NcatBotPlugin
from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api	import please_run_graph, register_channel, store_recall, store_set

from .models	import PluginConfig
from .consts	import MESSAGE_BUFFER, PLUGIN_CONFIG, RAW_CONFIG, READY_BUFFER
from .core		import (
	QQChannel,
	QQChannelMessage,
	CorpusWriter,
	ThreadBacklog,
	is_addressed,
	thread_id_of,
)

from pathlib	import Path
from typing		import Callable, Dict, List, Optional

import asyncio


PLUGIN_NAME	= "喵璃のQQ通道"
LOGGER		= get_log(PLUGIN_NAME)

# 语料记录 配置里 path 留空时写到这里
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "corpus.jsonl"


class MiaoLiQQChannel(NcatBotPlugin):
	
	"""把 QQ 事件缓冲起来 并以消息通道的形式提供给 miaoli_bot"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list	: List[Callable[[], None]]	= []
		
		# 句柄表不是业务状态 业务数据都在共享容器里
		self.tasks	: Dict[str, asyncio.Task]	= {}
		
		# 语料记录器 没开就是 None
		self.writer	: Optional[CorpusWriter]	= None
	
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
		
		# 语料记录是可选能力 不开就完全不影响原有的通道行为
		if config.corpus.enable:
			path = Path(config.corpus.path) if config.corpus.path else DEFAULT_CORPUS_PATH
			self.writer = CorpusWriter(
				path		= path,
				encoding	= config.corpus.encoding,
				flush		= config.corpus.flush,
			)
			self.writer.open()
			self.logger.info(f"{PLUGIN_NAME} 语料记录已开启 写入 {path}")
		
		self.logger.info(f"{PLUGIN_NAME} 已加载")
	
	async def on_close(self) -> None:
		
		# 先取消所有观察任务 用快照免得边遍历边被回调 pop 掉
		for task in list(self.tasks.values()):
			task.cancel()
		
		self.tasks.clear()
		
		for undo in self.undo_list:
			undo()
		
		if self.writer is not None:
			self.writer.close()
			self.writer = None
		
		self.logger.info(f"{PLUGIN_NAME} 已卸载")
	
	@registrar.on_message()
	async def backlog_anything(self, event: MessageEvent) -> None:
		
		"""私聊 event 和群聊 event 都记录进各自会话的积压区"""
		
		# 语料记录放在最前面 后面的任何分支都不影响它
		if self.writer is not None:
			self.writer.write(event)
		
		config	= store_recall(PLUGIN_CONFIG, default=None)
		backlog	= store_recall(MESSAGE_BUFFER, default=None)
		
		if config is None or backlog is None:
			return None
		
		thread_id	= thread_id_of(event)
		addressed	= is_addressed(event, config.account.bot_id, config.account.bot_nickname)
		
		# 入区时就把「是不是冲我来的」算好 之后不再重算
		backlog.record(
			thread_id	= thread_id,
			event		= event,
			addressed	= addressed,
		)
		
		# 冲我来的：起观察期 等对方补充完再一起交
		if addressed:
			self.watch_thread(thread_id)
			
			return None
		
		# 已经在观察期里了就让它一并带走 不插队打断 debounce
		task = self.tasks.get(thread_id)
		if task is not None and not task.done():
			return None
		
		# 没人叫我：摇骰子 命中就立刻交（不等补充，本来也没人在跟我说话）
		if not backlog.roll_dice(thread_id, config.submit.chance, config.submit.cooldown):
			return None
		
		# 就绪区里已经有人排队时让位 免得随机开窗挤掉被 @ 的那条
		# 没开成就不启动冷却 下一条消息还能再摇
		if not self.submit_window(thread_id, require_empty=True):
			self.logger.debug(f"{thread_id} 随机开窗让位（就绪区非空或已满）")
			return None
		
		backlog.mark_rolled(thread_id)
		self.logger.info(f"{thread_id} 随机开窗（未寻址）")
		
		return None
	
	def watch_thread(self, thread_id: str) -> None:
		
		"""给这个会话起一个观察任务 提交成功或会话空了它自己退出"""
		
		task = self.tasks.get(thread_id)
		
		# 已经有一个活着的观察任务就不重复起
		# 注意不能只判 in：add_done_callback 的回调是排进队列的
		# 会残留已经跑完但还没被 pop 掉的任务
		if task is not None and not task.done():
			return None
		
		task = asyncio.create_task(self.watch_until_quiet(thread_id))
		self.tasks[thread_id] = task
		
		def _retire(finished: asyncio.Task) -> None:
			
			# 只清自己那一份 免得把后来者从字典里 pop 掉
			if self.tasks.get(thread_id) is finished:
				self.tasks.pop(thread_id, None)
			
			if finished.cancelled():
				return None
			
			if exception := finished.exception():
				self.logger.error(f"{thread_id} 观察任务异常: "
					f"{type(exception).__name__}: {exception}", exc_info=exception)
			
			return None
		
		task.add_done_callback(_retire)
		
		return None
	
	async def watch_until_quiet(self, thread_id: str) -> None:
		
		"""等这个会话安静下来 再把整段积压交给就绪区
		
		只有提交成功才退出。就绪区满了就一直等下去 ——
		一旦提前放开 那段对话就再没有任何东西会来开窗了
		"""
		
		config	= store_recall(PLUGIN_CONFIG)
		backlog	= store_recall(MESSAGE_BUFFER)
		last	= backlog.count(thread_id)
		
		while True:
			
			# 先等一个静默窗口 首次进来也要等
			await asyncio.sleep(config.submit.quiet)
			
			backlog	= store_recall(MESSAGE_BUFFER)
			current	= backlog.count(thread_id)
			
			# 窗口内又有人说话 重新计时
			if current != last:
				last = current
				continue
			
			# 还是没搬成（就绪区满 / 已在排队）就别放开 下一轮再来
			if not self.submit_window(thread_id):
				last = current
				continue
			
			return None
	
	def submit_window(self, thread_id: str, require_empty: bool = False) -> bool:
		
		"""把这个会话的积压搬进就绪区 搬完了返回 True
		
		全程同步 中间一个 await 都不许有：多个观察任务会同时醒来 靠这个互斥
		require_empty 给随机开窗用：有人在排队就让位 别挤掉被 @ 的那条
		"""
		
		config	= store_recall(PLUGIN_CONFIG)
		ready	= store_recall(READY_BUFFER)
		backlog	= store_recall(MESSAGE_BUFFER)
		
		if len(ready) >= config.channel.buf_size:
			return False
		
		if require_empty and ready:
			return False
		
		# 同一个会话已经在就绪区里排着队 不重复投递
		if any(message.thread_id == thread_id for message in ready):
			return False
		
		events = backlog.pop_window(thread_id)
		if not events:
			return True
		
		ready.append(QQChannelMessage(events))
		please_run_graph()
		
		return True
