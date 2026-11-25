from collections	import deque
from typing			import Any, Deque, Optional

import time
import random


MINUTE_SECONDS = 60.0
HOUR_SECONDS = 3600.0


class SendGate:
	
	"""每个会话的发送频率账本 条数按实际发出的消息算"""
	
	def __init__(self, per_minute: int, per_hour: int) -> None:
		self.per_minute	= max(1, per_minute)
		self.per_hour	= max(1, per_hour)
		self.stamps		: Deque[float]	= deque()
	
	def acquire(self, now: Optional[float] = None) -> bool:
		
		"""能不能再发一条 能的话记账并返回 True"""
		
		current = time.monotonic() if now is None else now
		self._prune(current)
		
		if self._count(MINUTE_SECONDS, current) >= self.per_minute:
			return False
		if self._count(HOUR_SECONDS, current) >= self.per_hour:
			return False
		
		self.stamps.append(current)
		
		return True
	
	def _count(self, window: float, now: float) -> int:
		return sum(1 for stamp in self.stamps if now - stamp < window)
	
	def _prune(self, now: float) -> None:
		while self.stamps and now - self.stamps[0] > HOUR_SECONDS:
			self.stamps.popleft()


def burst_gap(config: Any, rng: Any = None) -> float:
	
	"""分条之间的停顿 有概率换成更长的停顿"""
	
	delivery = config.delivery
	if not delivery.burst_enable:
		return 0.0
	
	source	= rng if rng is not None else random
	low		= min(delivery.burst_interval_min, delivery.burst_interval_max)
	high	= max(delivery.burst_interval_min, delivery.burst_interval_max)
	
	if source.random() < delivery.long_gap_probability:
		low		= min(delivery.long_gap_min, delivery.long_gap_max)
		high	= max(delivery.long_gap_min, delivery.long_gap_max)
	
	return source.uniform(low, high)
