from collections	import deque
from typing			import Any, Deque, Dict, List, Optional, Tuple

import time
import random
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
		self.rolled_at  : Dict[str, float]  = {}
		self.followups  : Dict[str, Tuple[float, int]]  = {}
		self.revisions  : Dict[str, int]  = {}
	
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
		self.revisions[thread_id] = self.revisions.get(thread_id, 0) + 1
		
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
	
	def roll_dice(self, thread_id: str, chance: float, cooldown: float) -> bool:
		
		"""冷却期外才有机会摇中 只判定 不改状态
		
		摇不中不占冷却 否则一段对话里只能摇一次 概率会低到几乎不触发
		真正开成窗之后由调用方 mark_rolled 启动冷却 —— 让位 / 满了不算数
		"""
		
		now = time.monotonic()
		
		# 从没摇中过的会话给 -inf 免得进程刚启动时 uptime 小于冷却就直接挡掉
		if now - self.rolled_at.get(thread_id, float("-inf")) < cooldown:
			return False
		
		return random.random() < chance
	
	def mark_rolled(self, thread_id: str) -> None:
		
		"""记一次随机开窗 冷却从这里开始算"""
		
		self.rolled_at[thread_id] = time.monotonic()
	
	def open_followup(self, thread_id: str, minutes: int, max_messages: int) -> None:
		if minutes <= 0 or max_messages <= 0:
			self.followups.pop(thread_id, None)
			return None
		self.followups[thread_id] = (time.monotonic() + minutes * 60, max_messages)
	
	def consume_followup(self, thread_id: str) -> bool:
		window = self.followups.get(thread_id)
		if window is None:
			return False
		until, remaining = window
		if time.monotonic() >= until or remaining <= 0:
			self.followups.pop(thread_id, None)
			return False
		if remaining == 1:
			self.followups.pop(thread_id, None)
		else:
			self.followups[thread_id] = (until, remaining - 1)
		return True
	
	def close_followup(self, thread_id: str) -> None:
		self.followups.pop(thread_id, None)
	
	def revision(self, thread_id: str) -> int:
		return self.revisions.get(thread_id, 0)
	
	def count(self, thread_id: str) -> int:
		
		"""这个会话现在积压了多少条"""
		
		bucket = self.data.get(thread_id)
		
		return len(bucket) if bucket else 0
	
	def has_addressed(self, thread_id: str) -> bool:
		
		"""这个会话的积压里有没有「冲我来的」事件"""
		
		bucket = self.data.get(thread_id)
		
		return any(addressed for _, addressed in bucket) if bucket else False
	
	def ready_threads(self) -> List[str]:
		
		"""所有该开一次窗的会话 按「第一次收到消息」的先后排列"""
		
		return list(self.data)
	
	def pop_window(self, thread_id: str, limit: Optional[int] = None) -> Optional[Tuple[List[Any], int]]:
		"""取走积压，返回（最近事件，较早省略数）。"""
		bucket = self.data.pop(thread_id, None)
		self.revisions.pop(thread_id, None)
		if not bucket:
			return None
		max_items = max(1, min(limit, self.cap)) if limit is not None else max(1, self.cap)
		selected = list(range(max(0, len(bucket) - max_items), len(bucket)))
		latest_addressed = next(
			(index for index in range(len(bucket) - 1, -1, -1) if bucket[index][1]),
			None,
		)
		if latest_addressed is not None and latest_addressed not in selected:
			selected = [latest_addressed, *selected[-(max_items - 1):]] if max_items > 1 else [latest_addressed]
		selected = sorted(set(selected))
		omitted = len(bucket) - len(selected)
		if omitted:
			LOGGER.info(f"会话 {thread_id} 本窗省略 {omitted} 条较早消息")
		events = [bucket[index][0] for index in selected]
		return events, omitted
