from pydantic	import BaseModel, Field


class VoiceConfig(BaseModel):
	
	"""语音配置 按概率把一条文字换成 MiMo 语音合成的语音"""
	
	enable		: bool	= Field(default=False, description="是否启用语音发送")
	probability	: float	= Field(default=0, ge=0, le=1, description="每一条改成语音的概率 0 到 1")
	
	mimo_url	: str	= Field(default="https://api.xiaomimimo.com/v1/chat/completions", description="MiMo 语音合成的接口地址")
	mimo_key	: str	= Field(default="", description="MiMo 的 API Key 只写在 config.yaml 里 仓库里留空")
	
	model		: str	= Field(default="mimo-v2.5-tts", description="语音合成模型")
	voice		: str	= Field(default="冰糖", description="预置音色 ID")
	style		: str	= Field(default="", description="语气指令 放在 user 角色 留空则只传朗读文本")
	
	max_chars	: int	= Field(default=30, description="超过这么多字的一条不转语音 直接发文字")
	min_chars	: int	= Field(default=10, description="不足这么多字的一条不转语音 直接发文字")
