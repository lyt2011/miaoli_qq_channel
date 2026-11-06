from pydantic	import BaseModel, Field

from typing	import Any, Dict
from abc	import ABC, abstractmethod


class BaseMessage(BaseModel, ABC):
	type: str	= Field(..., description="消息的类型")

	@abstractmethod
	def to_ob11(self) -> Dict[str, Any]:
		"""转成 OB11 的消息段"""
		raise NotImplementedError()
