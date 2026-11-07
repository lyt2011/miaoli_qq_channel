from pydantic	import BaseModel, Field


class MessageConfig(BaseModel):
	
	buf_size: int	= Field(default=30, description="消息缓冲区大小", ge=0)
