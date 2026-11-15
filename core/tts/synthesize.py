from typing	import Optional

import edge_tts
import logging


LOGGER = logging.getLogger("QQChannelTTS")


async def synthesize(text: str, voice: str, pitch: str, rate: str) -> Optional[bytes]:
	
	"""用 edge-tts 合成 mp3 字节 全程在内存里不落盘
	
	失败或拿到空音频时返回 None 由调用方回退到文字发送
	"""
	
	buffer = bytearray()
	
	try:
		communicate	= edge_tts.Communicate(text, voice, pitch=pitch, rate=rate)
		
		async for chunk in communicate.stream():
			if chunk["type"] == "audio":
				buffer += chunk["data"]
	
	except Exception:
		LOGGER.warning("语音合成失败 回退到文字发送", exc_info=True)
		return None
	
	if not buffer:
		LOGGER.warning("语音合成返回空音频 回退到文字发送")
		return None
	
	return bytes(buffer)
