from pydantic	import BaseModel, Field


class SubmitConfig(BaseModel):
	
	quiet: float	= Field(default=8.0, description="静默窗口（秒）连续这么久没有新消息就提交", gt=0)
