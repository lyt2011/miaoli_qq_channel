from pydantic	import Field

from ..base	import BaseMessage

from typing	import Any, Dict, Literal


class TextMessage(BaseMessage):
	type: Literal["text"]	= Field(default="text", description="text 消息")
	text: str				= Field(..., description="要发送的文本内容")

	def to_ob11(self) -> Dict[str, Any]:
		return {"type": self.type, "data": {"text": self.text}}
