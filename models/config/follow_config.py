from pydantic	import BaseModel, Field


class FollowConfig(BaseModel):
	
	"""跟随模式：被叫之后的一段时间里 该会话的消息跳过缓冲默认静默/随机策略 下个 tick 就提交
	
	跟随有自己的一套限流与时长 和 social 的普通提交策略分开
	"""
	
	enable				: bool	= Field(default=False, description="是否启用跟随；关闭后被叫之外不再自动接话")
	duration_minutes	: int	= Field(default=10, description="一次跟随最长持续（分钟）；每次成功提交后重新计时", ge=1, le=240)
	merge_quiet_seconds	: float	= Field(default=10.0, description="跟随中消息要安静这么久才合并提交（秒）；连发的一串消息会并成一窗", ge=0, le=120)
	min_interval_seconds: float	= Field(default=3.0, description="跟随中两次提交的最小间隔（秒）", ge=0, le=600)
	max_submit_per_minute		: int	= Field(default=2, description="跟随中每分钟最多提交几次", ge=1, le=60)
	max_submit_per_hour			: int	= Field(default=30, description="跟随中每小时最多提交几次", ge=1, le=600)
