from pydantic	import BaseModel, Field


class SnapshotConfig(BaseModel):
	
	"""交给模型的未读快照：条数、字数预算、时间前缀与旧消息警告"""
	
	unread_limit	: int	= Field(default=30, description="一次最多带多少条未读", ge=1, le=200)
	max_chars		: int	= Field(default=6000, description="快照正文总字数上限，超了从最旧的开始省略", ge=200, le=40000)
	old_message_minutes	: int	= Field(default=30, description="最新一条超过这么久就提醒「这是旧账」", ge=1, le=1440)
