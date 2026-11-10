from collections  import deque
from typing      import Any, Deque, Dict, List, Optional, Tuple

import logging


LOGGER = logging.getLogger("miaoli_qq_channel/thread_backlog")


class ThreadBacklog:
	
	"""每个会话一条积压队列
	
	记录的时候就地算好「有没有证据表明这条是冲我来的」 之后不再重算
	一条消息进来是同步 O(1) 的 不碰网络 不 await
	"""
	
	def __init__(self, cap: int) -> None:
		self.cap  = cap
		self.data  : Dict[str, Deque[Tuple[Any, bool]]]  = {}
	
	@property
	def active_threads(self) -> int:
		"""当前有积压的会话数 打日志用"""
		return len(self.data)
	
	def record(self, thread_id: str, event: Any, addressed: bool) -> None:
		
		"""把一条事件记进它所属会话的积压队列 超限时只丢最旧的「未寻址」"""
		
		bucket = self.data.get(thread_id)
		if bucket is None:
			bucket = self.data[thread_id] = deque()
		
		bucket.append((event, addressed))
		
		if len(bucket) > self.cap:
			self._shrink(thread_id, bucket)
	
	def _shrink(self, thread_id: str, bucket: Deque[Tuple[Any, bool]]) -> None:
		
		"""丢最旧的一条未寻址事件 全是寻址的就让它超限"""
		
		for index, (_, addressed) in enumerate(bucket):
			if not addressed:
				del bucket[index]
				return None
		
		# 全是「冲我来的」 丢谁都是漏 允许超限但要说一声（只在刚越界时打一次）
		if len(bucket) == self.cap + 1:
			LOGGER.warning(f"会话 {thread_id} 积压全是待回消息 已超限到 {len(bucket)} 条")
	
	def ready_threads(self) -> List[str]:
		
		"""所有该开一次窗的会话 按「第一次收到消息」的先后排列"""
		
		return list(self.data)
	
	def pop_window(self, thread_id: str) -> Optional[List[Any]]:
		
		"""把这个会话的积压整个取走 返回「旧 → 新」的事件列表"""
		
		bucket = self.data.pop(thread_id, None)
		if not bucket:
			return None
		
		events = [event for event, _ in bucket]
		
		# 超限的会话（全是寻址消息）只把最新的 cap 条送进图 免得一窗灌爆上下文
		if len(events) > self.cap:
			LOGGER.warning(f"会话 {thread_id} 单窗 {len(events)} 条 "
				f"超过上限 {self.cap} 只取最新的 {self.cap} 条")
			events = events[-self.cap:]
		
		return events
