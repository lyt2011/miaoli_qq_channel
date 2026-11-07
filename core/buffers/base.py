from typing	import Any, List
from abc	import ABC, abstractmethod


class BaseBuffer(ABC):
	
	"""缓冲区的基类"""
	
	@abstractmethod
	def get_length(self) -> int: ...
	
	@abstractmethod
	def get_data(self) -> List[Any]: ...

	@abstractmethod
	def consume(self, count: int) -> List[Any]: ...
	
	@abstractmethod
	def record(self, data: Any) -> None: ...
