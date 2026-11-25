from pydantic	import BaseModel, Field


class DeliveryConfig(BaseModel):
	
	"""发送节流：分条停顿与每分钟/每小时条数上限"""
	
	burst_enable	: bool	= Field(default=True, description="分条之间是否加停顿")
	burst_interval_min	: float	= Field(default=1.0, description="分条停顿下限（秒）", ge=0, le=30)
	burst_interval_max	: float	= Field(default=3.0, description="分条停顿上限（秒）", ge=0, le=60)
	
	long_gap_probability: float	= Field(default=0.1, description="使用长停顿的概率", ge=0, le=1)
	long_gap_min		: float	= Field(default=2.5, description="长停顿下限（秒）", ge=0, le=60)
	long_gap_max		: float	= Field(default=5.0, description="长停顿上限（秒）", ge=0, le=120)
	
	max_send_per_minute	: int	= Field(default=8, description="每个会话每分钟最多发几条", ge=1, le=120)
	max_send_per_hour	: int	= Field(default=60, description="每个会话每小时最多发几条", ge=1, le=1200)
