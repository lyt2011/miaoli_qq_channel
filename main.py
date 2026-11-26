from ncatbot.utils					import get_log
from ncatbot.core					import registrar
from ncatbot.plugin					import NcatBotPlugin
from ncatbot.event.qq				import MessageEvent
from ncatbot.types.common.segment	import Image

from miaoli_bot.api	import please_run_graph, register_channel, store_recall, store_set

from .models	import PluginConfig
from .consts	import (
	MESSAGE_BUFFER,
	PLUGIN_CONFIG,
	RAW_CONFIG,
	READY_BUFFER,
	SOCIAL_STORE,
)
from .core	import (
	MediaCache,
	QQChannel,
	QQChannelMessage,
	CorpusWriter,
	MessageBufferStore,
	Scheduler,
	SocialStore,
	WakeDecision,
	WakeReason,
	is_addressed,
	is_authorized,
	thread_id_of,
)

from pathlib	import Path
from typing		import Callable, List, Optional

import asyncio
import time


PLUGIN_NAME	= "喵璃のQQ通道"
LOGGER		= get_log(PLUGIN_NAME)

# 语料记录 配置里 path 留空时写到这里
DEFAULT_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "corpus.jsonl"

# 入站媒体缓存 配置里 path 留空时用这个目录
DEFAULT_MEDIA_PATH = Path(__file__).resolve().parent / "data" / "media"


class MiaoLiQQChannel(NcatBotPlugin):
	
	"""把 QQ 事件缓冲起来 并以消息通道的形式提供给 miaoli_bot"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list	: List[Callable[[], None]]	= []
		
		# 调度器句柄 状态机关掉时是 None
		self.scheduler	: Optional[Scheduler]		= None
		
		# 语料记录器 没开就是 None
		self.writer		: Optional[CorpusWriter]	= None
		
		# 入站媒体缓存 关掉就是 None
		self.media_cache: Optional[MediaCache] = None
		self.media_tasks: set = set()
	
	async def on_load(self) -> None:
		
		# 校验配置
		config = PluginConfig.model_validate(self.config)
		
		# 把配置塞共享容器
		self.undo_list.append(store_set(RAW_CONFIG, self.config))
		self.undo_list.append(store_set(PLUGIN_CONFIG, config))
		
		# 构建积压区/社交状态/就绪区
		buffers = MessageBufferStore(cap=config.message.buf_size)
		social	= SocialStore()
		ready	: List[QQChannelMessage] = []
		
		self.undo_list.append(store_set(MESSAGE_BUFFER, buffers))
		self.undo_list.append(store_set(SOCIAL_STORE, social))
		self.undo_list.append(store_set(READY_BUFFER, ready))
		
		# 注册消息渠道
		self.undo_list.append(register_channel(QQChannel()))
		
		# 图片进来就缓存到本地 模型看到的是本地路径 不会拿到过期链接
		if config.media.enable:
			media_path = Path(config.media.path) if config.media.path else DEFAULT_MEDIA_PATH
			self.media_cache = MediaCache(
				root			= media_path,
				max_megabytes	= config.media.max_megabytes,
				max_files		= config.media.max_files,
				timeout_seconds	= config.media.timeout_seconds,
			)
			self.logger.info(f"{PLUGIN_NAME} 入站媒体缓存已开启 写入 {media_path}")
		
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
		
		# 状态机开着才跑调度器 关掉退回「被叫即提交」
		if config.social.enabled:
			self.scheduler = Scheduler(
				config		= config,
				buffers		= buffers,
				social		= social,
				ready		= ready,
				make_message= self.make_message,
				notify		= please_run_graph,
			)
			self.scheduler.start()
			self.logger.info(
				f"{PLUGIN_NAME} 状态机调度器已启动 "
				f"tick={config.social.tick_seconds}s 静默={config.social.quiet}s "
				f"提交上限={config.social.max_submit_per_minute}/分 {config.social.max_submit_per_hour}/时"
			)
		
		self.logger.info(f"{PLUGIN_NAME} 已加载")
	
	async def on_close(self) -> None:
		
		if self.scheduler is not None:
			self.scheduler.stop()
			self.scheduler = None
		
		for undo in self.undo_list:
			undo()
		
		self.undo_list.clear()
		
		for task in list(self.media_tasks):
			task.cancel()
		self.media_tasks.clear()
		self.media_cache = None
		
		if self.writer is not None:
			self.writer.close()
			self.writer = None
		
		self.logger.info(f"{PLUGIN_NAME} 已卸载")
	
	def make_message(
		self,
		entries			: List[object],
		omitted			: int,
		reason			: WakeReason,
		delivered_seq	: int,
	) -> QQChannelMessage:
		
		"""调度器不认 QQ 类型 窗口对象在这里造"""
		
		return QQChannelMessage(entries, omitted=omitted, reason=reason, delivered_seq=delivered_seq)
	
	@registrar.on_message()
	async def backlog_anything(self, event: MessageEvent) -> None:
		
		"""私聊 event 和群聊 event 都记录进各自会话的积压区"""
		
		config	= store_recall(PLUGIN_CONFIG, default=None)
		buffers	= store_recall(MESSAGE_BUFFER, default=None)
		social	= store_recall(SOCIAL_STORE, default=None)
		if config is None or buffers is None or social is None:
			return None
		
		is_group = event.is_group_msg()
		user_id = str(event.user_id)
		group_id = str(event.group_id) if is_group else ""
		if not is_authorized(
			is_group, group_id, user_id, config.account.bot_id,
			config.submit.group_whitelist,
		):
			return None
		
		if self.writer is not None:
			self.writer.write(event)
		
		thread_id	= thread_id_of(event)
		addressed	= self.addressed_of(event, config)
		entry		= buffers.record(thread_id, event, addressed)
		now			= time.monotonic()
		
		# 图片一进来就下载 等窗口提交时链接还没过期
		self.schedule_media_cache(event)
		
		# 状态机：只记账与判定 什么时候提交交给调度器
		if self.scheduler is not None:
			social.on_message(thread_id, entry, config, now)
			return None
		
		# 状态机关掉：被叫到就立刻交一窗（旧行为）
		if addressed:
			self.submit_now(thread_id, buffers, social, config, now)
		
		return None
	
	def schedule_media_cache(self, event: MessageEvent) -> None:
		
		"""把这条消息里的图片丢给缓存器 后台下载 不阻塞入队"""
		
		if self.media_cache is None:
			return None
		
		for segment in event.message or []:
			if not isinstance(segment, Image):
				continue
			
			url = getattr(segment, "url", "")
			if not url or self.media_cache.path_for(url):
				continue
			
			name = getattr(segment, "file_name", "") or getattr(segment, "file", "")
			task = asyncio.create_task(self.media_cache.cache(url, name))
			self.media_tasks.add(task)
			task.add_done_callback(self.media_tasks.discard)
		
		return None
	
	def addressed_of(self, event: MessageEvent, config: PluginConfig) -> bool:
		
		"""是否「冲我来的」 群里 at_only 时只认 @"""
		
		if event.is_group_msg() and config.submit.at_only_in_group:
			return event.message.is_at(config.account.bot_id, all_except=True)
		
		nicknames = [config.account.bot_nickname, *config.submit.nickname_variants]
		
		return is_addressed(event, config.account.bot_id, nicknames)
	
	def submit_now(
		self,
		thread_id	: str,
		buffers		: MessageBufferStore,
		social		: SocialStore,
		config		: PluginConfig,
		now			: float,
	) -> None:
		
		"""状态机关闭时的退化路径：不看限流 被叫就交一窗"""
		
		ready = store_recall(READY_BUFFER)
		
		if len(ready) >= config.channel.buf_size:
			return None
		if any(getattr(message, "thread_id", "") == thread_id for message in ready):
			return None
		
		entries = buffers.take(thread_id, limit=config.snapshot.unread_limit)
		if not entries:
			return None
		
		reason = WakeReason.AT if any(entry.addressed for entry in entries) else WakeReason.CHANCE
		ready.append(QQChannelMessage(entries, 0, reason, buffers.delivered_seq(thread_id)))
		
		session		= social.session(thread_id)
		decision	= session.pending or WakeDecision(reason, 0, now)
		social.on_submit(thread_id, now, decision, config)
		please_run_graph()
		
		return None
