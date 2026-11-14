from pydantic	import BaseModel, Field

from .config	import (
	AccountConfig,
	ChannelConfig,
	CorpusConfig,
	MessageConfig,
	SplitConfig,
	SubmitConfig,
	TypingConfig,
)


class PluginConfig(BaseModel):
	
	enable	: bool	= Field(default=True, description="QQ通道的开关 关了就接收不到QQ信息了喵")
	
	account	: AccountConfig	= Field(..., description="账号信息")
	
	channel	: ChannelConfig	= Field(default_factory=ChannelConfig, description="渠道配置")
	corpus	: CorpusConfig	= Field(default_factory=CorpusConfig, description="语料记录配置")
	message	: MessageConfig	= Field(default_factory=MessageConfig, description="消息配置")
	submit	: SubmitConfig	= Field(default_factory=SubmitConfig, description="扫描配置")
	split	: SplitConfig	= Field(default_factory=SplitConfig, description="输出分割配置")
	typing	: TypingConfig	= Field(default_factory=TypingConfig, description="打字速度配置")
