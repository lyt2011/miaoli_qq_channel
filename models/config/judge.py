from pydantic	import BaseModel, Field


class JudgeConfig(BaseModel):
	
	timeout: float	= Field(default=3.0, description="单个条件节点的超时（秒）", gt=0)
