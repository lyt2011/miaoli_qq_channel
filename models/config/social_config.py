from pydantic	import BaseModel, Field


class WakeConfig(BaseModel):
	
	"""唤醒条件开关 从「这条消息像不像在叫我」升级到状态机之后的附加判定"""
	
	at			: bool			= Field(default=True, description="群里 @ 我")
	name		: bool			= Field(default=True, description="正文里叫到昵称")
	keyword		: bool			= Field(default=False, description="命中关键词族")
	keyword_list: list[str]		= Field(default_factory=list, description="关键词族；keyword 打开时生效")
	question	: bool			= Field(default=False, description="像在问 AI/提问的句子")
	quote		: bool			= Field(default=False, description="有人引用消息（近似判定，不解析引用链）")


class SocialConfig(BaseModel):
	
	"""会话社交状态机：diving 潜水 / active 聊天中
	
	所有提交都要过 quiet 静默与限流；一条消息不会再单独拉起一次跑图
	"""
	
	enabled		: bool	= Field(default=True, description="是否启用状态机；关闭后退回「被叫即提交」的旧行为")
	tick_seconds: float	= Field(default=1.0, description="调度器 tick 间隔（秒）", gt=0, le=10)
	quiet		: float	= Field(default=8.0, description="静默窗口（秒）连续这么久没有新消息才提交", ge=0, le=120)
	
	chance		: float	= Field(default=0.05, description="潜水时普通消息的随机唤醒概率", ge=0, le=1)
	chance_cooldown_seconds	: float	= Field(default=120.0, description="随机唤醒成功后的冷却（秒）", ge=0)
	
	max_submit_per_minute	: int	= Field(default=1, description="每个会话每分钟最多提交几次", ge=1, le=60)
	max_submit_per_hour		: int	= Field(default=12, description="每个会话每小时最多提交几次", ge=1, le=600)
	speak_cooldown_seconds	: float	= Field(default=60.0, description="距上次成功发言的冷却（秒）", ge=0, le=3600)
	
	active_min_minutes	: int	= Field(default=15, description="聊天状态最短持续（分钟）", ge=1, le=240)
	active_max_minutes	: int	= Field(default=30, description="聊天状态最长持续（分钟）", ge=1, le=480)
	idle_minutes		: int	= Field(default=6, description="聊天状态下多久没人说话就回潜水（分钟）", ge=1, le=240)
	
	in_flight_timeout_seconds	: float	= Field(default=240.0, description="在途窗口超时（秒）超了就放行下一轮", ge=10, le=3600)
	
	wake		: WakeConfig	= Field(default_factory=WakeConfig, description="唤醒条件")
