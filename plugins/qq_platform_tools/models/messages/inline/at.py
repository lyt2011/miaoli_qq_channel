from pydantic	import Field

from ..base	import BaseMessage

from typing	import Any, Dict, Literal


class AtMessage(BaseMessage):
	type	: Literal["at"]	= Field(default="at", description="at 消息")
	user_id	: str			= Field(..., description="要艾特的用户id")

	def to_ob11(self) -> Dict[str, Any]:
		return {"type": self.type, "data": {"qq": self.user_id}}
