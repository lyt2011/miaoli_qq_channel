from pydantic	import Field

from ..base	import BaseMessage

from typing	import Optional


class MediaMessage(BaseMessage):

	"""
	带文件载荷的媒体段基类

	image / record / video / file 四个段共用这套字段
	to_ob11 由各子类自行实现
	"""

	file	: str			= Field(..., description="本地绝对路径 http(s):// file:/// 或 base64://")
	url		: Optional[str]	= Field(default=None, description="会覆盖 file")
	path	: Optional[str]	= Field(default=None, description="本地路径 优先级最低")
	name	: Optional[str]	= Field(default=None, description="显示的文件名")
	thumb	: Optional[str]	= Field(default=None, description="封面图")
