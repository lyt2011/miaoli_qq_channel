from pydantic	import BaseModel, Field


class SubmitConfig(BaseModel):
	
	quiet	: float	= Field(default=8.0, description="静默窗口（秒）连续这么久没有新消息就提交", gt=0)
	
	chance	: float	= Field(default=0.05, description="未寻址群消息的随机触发概率", ge=0, le=1)
	cooldown: float	= Field(default=120.0, description="随机触发冷却（秒）从开窗成功算起", ge=0)
	
	group_whitelist	: list[str]	= Field(default_factory=list, description="允许参与群聊的群号；空列表拒绝所有群")
	at_only_in_group	: bool	= Field(default=False, description="群内仅 @ 触发；回复后的跟随窗口仍生效")
	nickname_variants	: list[str]	= Field(default_factory=list, description="额外唤醒昵称")
	followup_minutes	: int	= Field(default=5, description="群回复成功后跟随窗口时长（分钟）；0关闭", ge=0, le=60)
	followup_messages	: int	= Field(default=8, description="跟随窗口内最多接收的普通群消息数；0关闭", ge=0, le=200)
	recent_chat_limit	: int	= Field(default=8, description="唤醒时携带的最近消息条数，至少包含触发消息", ge=0, le=200)
	max_reply_chars	: int	= Field(default=500, description="自动群回复最大字符数，超限整条不发送", ge=40, le=4000)
