from typing	import Optional

import base64
import logging

import httpx


LOGGER = logging.getLogger("QQChannelTTS")


async def synthesize(text: str, url: str, key: str, model: str, voice: str, style: str) -> Optional[bytes]:
	
	"""用 MiMo 语音合成把文本转成 wav 字节
	
	模型只朗读 assistant 角色的内容 语气指令放在 user 角色
	非流式 一次请求拿完整音频 全程内存不落盘
	
	失败或拿到空音频时返回 None 由调用方回退到文字
	"""
	
	messages = []
	
	if style:
		messages.append({"role": "user", "content": style})
	
	messages.append({"role": "assistant", "content": text})
	
	body = {
		"model"		: model,
		"messages"	: messages,
		"audio"		: {"format": "wav", "voice": voice},
	}
	
	try:
		async with httpx.AsyncClient(timeout=180.0) as client:
			response = await client.post(
				url,
				headers	= {"Authorization": f"Bearer {key}"},
				json	= body,
			)
		
		if response.status_code != 200:
			LOGGER.warning("语音合成失败 HTTP %s %s", response.status_code, response.text[:200])
			return None
		
		buffer = base64.b64decode(response.json()["choices"][0]["message"]["audio"]["data"])
	
	except Exception:
		LOGGER.warning("语音合成失败 回退到文字", exc_info=True)
		return None
	
	if not buffer:
		LOGGER.warning("语音合成返回空音频 回退到文字")
		return None
	
	return buffer
