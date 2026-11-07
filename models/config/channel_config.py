from pydantic	import BaseModel, Field


class ChannelConfig(BaseModel):
	
	buf_size: int	= Field(default=30, description="通道缓冲区大小", ge=0)
