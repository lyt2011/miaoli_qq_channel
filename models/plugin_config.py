from pydantic	import BaseModel, Field

from .config	import ChannelConfig, MessageConfig, SubmitConfig, JudgeConfig


class PluginConfig(BaseModel):
	
	enable	: bool	= Field(default=True, description="QQ通道的开关 关了就接收不到QQ信息了喵")
	
	channel	: ChannelConfig	= Field(default_factory=ChannelConfig, description="渠道配置")
	message	: MessageConfig	= Field(default_factory=MessageConfig, description="消息配置")
	submit	: SubmitConfig	= Field(default_factory=SubmitConfig, description="提交配置")
	judge	: JudgeConfig	= Field(default_factory=JudgeConfig, description="条件节点配置")
