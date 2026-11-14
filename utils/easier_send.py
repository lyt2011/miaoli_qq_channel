from ncatbot.types.napcat.message	import SendMessageResult

from miaoli_bot.api	import get_ncatbot_api

from typing	import Any, Dict, List, Literal, Optional, Union


async def easier_send(
	mode		: Literal["group", "private"],
	chat_id		: Union[str, int],
	ob11_message: List[Dict[str, Any]],
	ncatbot_api	: Optional[Any]	= None
) -> SendMessageResult:
	
	"""更便捷的消息发送 api"""
	
	# 可替换的 ncatbot api 便于测试
	ncatbot_api = ncatbot_api or get_ncatbot_api()
	
	if mode == "group":
		coro = (ncatbot_api.qq.messaging.
			send_group_msg(group_id=chat_id, message=ob11_message))
	
	elif mode == "private":
		coro = (ncatbot_api.qq.messaging.
			send_private_msg(user_id=chat_id, message=ob11_message))
	
	else:
		raise ValueError(f"不支持的发送模式: {mode}")
	
	return await coro
