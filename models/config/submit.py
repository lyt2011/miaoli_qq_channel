from pydantic	import BaseModel, Field


class SubmitConfig(BaseModel):
	
	interval: float	= Field(default=3.0, description="扫描间隔（秒）", gt=0)
