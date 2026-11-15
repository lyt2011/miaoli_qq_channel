from pydantic	import BaseModel, Field


class VoiceConfig(BaseModel):
	
	"""语音配置 按概率把要发的一条文字换成 edge-tts 合成的语音"""
	
	enable		: bool	= Field(default=False, description="是否启用语音发送")
	probability	: float	= Field(default=0, ge=0, le=1, description="每一条改成语音的概率 0 到 1")
	voice		: str	= Field(default="zh-CN-XiaoyiNeural", description="edge-tts 音色全名")
	pitch		: str	= Field(default="+16Hz", description="音调 例如 +16Hz / -10Hz")
	rate		: str	= Field(default="+0%", description="语速 例如 +10% / -5%")
	max_chars	: int	= Field(default=30, description="超过这么多字的一条不转语音 直接发文字")
	min_chars	: int	= Field(default=10, description="不足这么多字的一条不转语音 直接发文字")
