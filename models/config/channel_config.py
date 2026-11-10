from pydantic	import BaseModel, Field


class ChannelConfig(BaseModel):
	
	buf_size: int	= Field(default=2, description="就绪区上限（条）", ge=0)
