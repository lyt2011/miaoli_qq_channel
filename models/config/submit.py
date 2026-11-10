from pydantic	import BaseModel, Field


class SubmitConfig(BaseModel):
	
	quiet	: float	= Field(default=8.0, description="静默窗口（秒）连续这么久没有新消息就提交", gt=0)
	
	chance	: float	= Field(default=0.1, description="没人叫我时 每条消息尝试开一次窗的概率", ge=0, le=1)
	cooldown: float	= Field(default=120.0, description="随机开窗的冷却（秒）从上次开成算起", ge=0)
