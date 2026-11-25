from typing	import Any, Callable, List

import asyncio
import time
import logging

from .policy	import REASON_LABEL
from .state		import SocialStore


LOGGER = logging.getLogger("miaoli_qq_channel/scheduler")


class Scheduler:
	
	"""每秒 tick 一次 把「攒够了 + 该说话了」的会话提交给主包
	
	所有状态都在 Buffer / SocialStore 里 这里只做判定与提交 不保存业务状态
	"""
	
	def __init__(
		self,
		config		: Any,
		buffers		: Any,
		social		: SocialStore,
		ready		: List[Any],
		make_message: Callable[..., Any],
		notify		: Callable[[], None],
		clock		: Callable[[], float] = time.monotonic,
	) -> None:
		self.config			= config
		self.buffers		= buffers
		self.social			= social
		self.ready			= ready
		self.make_message	= make_message
		self.notify			= notify
		self.clock			= clock
		self.tick_seconds	= max(0.1, float(config.social.tick_seconds))
		self.task			: Any = None
	
	def start(self) -> None:
		if self.task is None or self.task.done():
			self.task = asyncio.create_task(self.run())
	
	def stop(self) -> None:
		if self.task is not None:
			self.task.cancel()
			self.task = None
	
	async def run(self) -> None:
		while True:
			try:
				self.tick()
			except Exception:
				LOGGER.exception("调度 tick 异常 已跳过本轮")
			await asyncio.sleep(self.tick_seconds)
	
	def tick(self, now: Any = None) -> int:
		
		"""推进所有会话 返回本轮提交数（测试直接调这个）"""
		
		current = self.clock() if now is None else now
		submitted = 0
		
		for thread_id in self.buffers.threads():
			self.social.expire(thread_id, current, self.config)
			if self.submit_if_due(thread_id, current):
				submitted += 1
		
		self.social.prune(current)
		self.buffers.prune(current, 3600.0)
		
		return submitted
	
	def submit_if_due(self, thread_id: str, now: float) -> bool:
		
		"""该会话现在该不该交一窗 全程同步 靠 ready 里的去重做互斥"""
		
		config	= self.config
		social	= self.social
		
		if not self.buffers.count(thread_id):
			return False
		
		session = social.session(thread_id)
		if session.in_flight:
			return False
		
		# 静默没到 等下一轮；跟随中的会话不走这条 下个 tick 就交
		if not social.is_following(thread_id, config, now):
			if now - self.buffers.last_message_at(thread_id) < config.social.quiet:
				return False
		
		# 就绪区里已经有这个会话 或已经满了
		if any(getattr(message, "thread_id", "") == thread_id for message in self.ready):
			return False
		if len(self.ready) >= config.channel.buf_size:
			return False
		
		if not social.can_submit(thread_id, now, config):
			return False
		
		decision = social.decide(thread_id, now, config)
		if decision is None:
			return False
		
		entries = self.buffers.take(thread_id, limit=config.snapshot.unread_limit)
		if not entries:
			return False
		
		delivered = self.buffers.delivered_seq(thread_id)
		message = self.make_message(entries, 0, decision.reason, delivered)
		self.ready.append(message)
		social.on_submit(thread_id, now, decision, config)
		self.notify()
		
		LOGGER.info(
			f"开窗 {thread_id} 理由={REASON_LABEL[decision.reason]} "
			f"未读={len(entries)} 水位={delivered}"
		)
		
		return True
