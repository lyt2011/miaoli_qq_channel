from pydantic	import Field

from .base		import BaseMessage
from .inline	import AtMessage, TextMessage, ReplyMessage
from .media		import FileMessage, ImageMessage, VideoMessage, RecordMessage

from typing	import Annotated, List, Union


Messages = List[
	Annotated[
		Union[
			TextMessage,
			AtMessage,
			ReplyMessage,
			ImageMessage,
			RecordMessage,
			VideoMessage,
			FileMessage,
		],
		Field(discriminator="type")
	]
]


__all__ = [
	"BaseMessage",
	"TextMessage",
	"AtMessage",
	"ReplyMessage",
	"ImageMessage",
	"RecordMessage",
	"VideoMessage",
	"FileMessage",
	"Messages",
]
