from .base	import BaseBuffer

from collections	import deque
from typing			import Any, List


class MessageBuffer(BaseBuffer):
	
	"""消息缓冲区 新的在列表头"""
	
	def __init__(self, size: int) -> None:
		self.size, self.buf = size, deque(maxlen=size)
	
	def get_length(self) -> int:
		return len(self.buf)
	
	def get_data(self) -> List[Any]:
		return list(self.buf)
	
	def record(self, data: Any) -> None:
		"""把新数据记录到缓冲头"""
		self.buf.appendleft(data)
	
	def consume(self, count: int) -> List[Any]:
		
		"""把最新的 count 条踢出缓冲区"""
		
		# 0 到 count被踢出
		# count 到最后被保留
		popped	= self.get_data()[:count]
		kept	= self.get_data()[count:]
		
		# 用保留信息+原始大小重写缓冲区
		self.buf = deque(kept, maxlen=self.size)
		
		return popped
	
	def drain_into(self, other: "MessageBuffer") -> None:
		
		"""把全部消息按「旧 → 新」搬进另一个缓冲区"""
		
		for event in reversed(self.consume(self.get_length())):
			other.record(event)
