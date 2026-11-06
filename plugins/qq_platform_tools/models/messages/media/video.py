from pydantic	import Field

from .base	import MediaMessage

from typing	import Any, Dict, Literal


class VideoMessage(MediaMessage):
	type: Literal["video"]	= Field(default="video", description="video 消息")

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

		return {"type": self.type, "data": data}
