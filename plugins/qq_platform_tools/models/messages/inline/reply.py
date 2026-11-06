from pydantic	import Field

from ..base	import BaseMessage

from typing	import Any, Dict, Literal


class ReplyMessage(BaseMessage):
	type		: Literal["reply"]	= Field(default="reply", description="reply 消息")
	message_id	: str				= Field(..., description="要回复的消息id")

	def to_ob11(self) -> Dict[str, Any]:
		return {"type": self.type, "data": {"id": self.message_id}}
