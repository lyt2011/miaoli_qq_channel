from pydantic	import BaseModel, Field


class SubmitConfig(BaseModel):
	
	"""入口白名单与回复上限 会话节奏相关的配置在 SocialConfig"""
	
	group_whitelist	: list[str]	= Field(default_factory=list, description="允许参与群聊的群号；空列表拒绝所有群")
	at_only_in_group	: bool		= Field(default=False, description="群内仅 @ 触发；昵称与关键词判定关闭")
	nickname_variants	: list[str]	= Field(default_factory=list, description="额外唤醒昵称")
	
	max_reply_chars	: int	= Field(default=500, description="自动群回复最大字符数，超限整条不发送", ge=40, le=4000)
