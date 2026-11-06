from pydantic	import Field

from .base	import MediaMessage

from typing	import Any, Dict, Literal, Optional


class ImageMessage(MediaMessage):
	type		: Literal["image"]	= Field(default="image", description="image 消息")
	summary		: Optional[str]		= Field(default=None, description="显示摘要")
	sub_type	: Optional[int]		= Field(default=None, description="图片子类型 0为普通图片 1为表情包")

	def to_ob11(self) -> Dict[str, Any]:
		
		data = {"file": self.file}

		if self.url is not None:
			data["url"] = self.url

		if self.path is not None:
			data["path"] = self.path

		if self.name is not None:
			data["name"] = self.name

		if self.thumb is not None:
			data["thumb"] = self.thumb

		if self.summary is not None:
			data["summary"] = self.summary

		if self.sub_type is not None:
			data["sub_type"] = self.sub_type

		return {"type": self.type, "data": data}
