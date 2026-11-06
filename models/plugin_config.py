from pydantic	import BaseModel, Field


class PluginConfig(BaseModel):
	
	enable	: bool	= Field(default=True, description="QQ通道的开关 关了就接收不到QQ信息了喵")
	buf_size: int	= Field(default=30, description="缓冲区大小", ge=0)
