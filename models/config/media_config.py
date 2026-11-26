from pydantic	import BaseModel, Field

from typing	import Optional


class MediaConfig(BaseModel):
	
	enable			: bool			= Field(default=True, description="入站媒体缓存：消息进来就把图片下载到本地 模型直接 read_image 看")
	path			: Optional[str]	= Field(default=None, description="缓存目录 留空用插件的 data/media")
	max_megabytes	: int			= Field(default=20, description="单个文件大小上限（MB）", ge=1, le=200)
	max_files		: int			= Field(default=500, description="缓存目录最多保留多少个文件", ge=0, le=10000)
	timeout_seconds	: float			= Field(default=10.0, description="单个下载超时（秒）", ge=1, le=60)
