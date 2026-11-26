from pydantic	import BaseModel, Field

from .config	import (
	AccountConfig,
	ChannelConfig,
	CorpusConfig,
	DeliveryConfig,
	FollowConfig,
	MediaConfig,
	MessageConfig,
	SnapshotConfig,
	SocialConfig,
	SubmitConfig,
	SplitConfig,
	TypingConfig,
	VoiceConfig,
)


class PluginConfig(BaseModel):
	
	enable	: bool	= Field(default=True, description="QQ通道的开关 关了就接收不到QQ信息了喵")
	
	account	: AccountConfig	= Field(..., description="账号信息")
	
	channel	: ChannelConfig	= Field(default_factory=ChannelConfig, description="渠道配置")
	corpus	: CorpusConfig	= Field(default_factory=CorpusConfig, description="语料记录配置")
	delivery: DeliveryConfig	= Field(default_factory=DeliveryConfig, description="发送节流配置")
	follow	: FollowConfig	= Field(default_factory=FollowConfig, description="跟随模式配置")
	media	: MediaConfig = Field(default_factory=MediaConfig, description="入站媒体缓存配置")
	message	: MessageConfig	= Field(default_factory=MessageConfig, description="消息配置")
	snapshot: SnapshotConfig	= Field(default_factory=SnapshotConfig, description="未读快照配置")
	social	: SocialConfig	= Field(default_factory=SocialConfig, description="会话状态机配置")
	submit	: SubmitConfig	= Field(default_factory=SubmitConfig, description="入口白名单配置")
	split	: SplitConfig	= Field(default_factory=SplitConfig, description="输出分割配置")
	typing	: TypingConfig	= Field(default_factory=TypingConfig, description="打字速度配置")
	voice	: VoiceConfig	= Field(default_factory=VoiceConfig, description="语音发送配置")
