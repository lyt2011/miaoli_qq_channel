from collections	import deque
from dataclasses	import dataclass
from typing			import Any, Deque, Dict, List, Optional

import time
import logging


LOGGER = logging.getLogger("miaoli_qq_channel/message_queue")


@dataclass
class MessageEntry:
	
	"""积压区里的一条消息 入区时就把它算成「是不是冲我来的」"""
	
	seq			: int
	event		: Any
	addressed	: bool
	at			: float
	wall_time	: str


class ThreadQueue:
	
	"""一个会话的未读队列 水位与时间戳都挂在这里"""
	
	def __init__(self, cap: int) -> None:
		self.cap			= max(1, cap)
		self.unread			: Deque[MessageEntry]	= deque()
		self.seq			= 0
		self.delivered_seq	= 0
		self.last_message_at	= 0.0
	
	def record(self, event: Any, addressed: bool, wall_time: str, now: Optional[float] = None) -> MessageEntry:
		self.seq += 1
		entry = MessageEntry(
			seq			= self.seq,
			event		= event,
			addressed	= addressed,
			at			= time.monotonic() if now is None else now,
			wall_time	= wall_time,
		)
		self.unread.append(entry)
		self.last_message_at = entry.at
		if len(self.unread) > self.cap:
			self._shrink()
		return entry
	
	def _shrink(self) -> None:
		
		"""超限时只丢最旧的一条「看不出冲我来的」 全是寻址的允许超限并告警"""
		
		for index, entry in enumerate(self.unread):
			if not entry.addressed:
				del self.unread[index]
				return None
		
		if len(self.unread) == self.cap + 1:
			LOGGER.warning(f"未读队列全是待回消息 已超限到 {len(self.unread)} 条")
	
	def take(self, limit: Optional[int] = None) -> List[MessageEntry]:
		
		"""取走整段未读（最多 limit 条 默认 cap） 更早的不会留在队列里"""
		
		if not self.unread:
			return []
		max_items = self.cap if limit is None else max(1, min(limit, self.cap))
		entries = list(self.unread)[-max_items:]
		self.unread.clear()
		return entries
	
	def mark_delivered(self, seq: int) -> None:
		self.delivered_seq = max(self.delivered_seq, seq)
	
	def count(self) -> int:
		return len(self.unread)


class MessageBufferStore:
	
	"""所有会话的未读队列 按会话号分桶"""
	
	def __init__(self, cap: int) -> None:
		self.cap	= max(1, cap)
		self.queues	: Dict[str, ThreadQueue]	= {}
	
	def queue(self, thread_id: str) -> ThreadQueue:
		queue = self.queues.get(thread_id)
		if queue is None:
			queue = self.queues[thread_id] = ThreadQueue(self.cap)
		return queue
	
	def record(
		self,
		thread_id	: str,
		event		: Any,
		addressed	: bool,
		now			: Optional[float] = None,
	) -> MessageEntry:
		return self.queue(thread_id).record(
			event, addressed, time.strftime("%H:%M:%S"), now=now
		)
	
	def take(self, thread_id: str, limit: Optional[int] = None) -> List[MessageEntry]:
		return self.queue(thread_id).take(limit)
	
	def mark_delivered(self, thread_id: str, seq: int) -> None:
		self.queue(thread_id).mark_delivered(seq)
	
	def count(self, thread_id: str) -> int:
		queue = self.queues.get(thread_id)
		return queue.count() if queue is not None else 0
	
	def delivered_seq(self, thread_id: str) -> int:
		queue = self.queues.get(thread_id)
		return queue.delivered_seq if queue is not None else 0
	
	def last_message_at(self, thread_id: str) -> float:
		queue = self.queues.get(thread_id)
		return queue.last_message_at if queue is not None else 0.0
	
	def threads(self) -> List[str]:
		return list(self.queues)
	
	def prune(self, now: float, idle_seconds: float) -> None:
		
		"""清掉空队列且很久没动静的会话 免得会话数只增不减"""
		
		for thread_id in list(self.queues):
			queue = self.queues[thread_id]
			if queue.count():
				continue
			if now - queue.last_message_at < idle_seconds:
				continue
			self.queues.pop(thread_id, None)
