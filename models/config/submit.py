from pydantic	import BaseModel, Field


class SubmitConfig(BaseModel):
	
	interval		: float	= Field(default=60.0, description="提交间隔（秒）", gt=0)
	min_submit_score: float	= Field(default=1.0, description="提交所需的最低分数", ge=0)
