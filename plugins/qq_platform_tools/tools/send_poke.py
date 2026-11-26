from langchain_core.tools	import tool

from pydantic	import BaseModel, Field

from miaoli_qq_channel.consts	import PLUGIN_CONFIG
from miaoli_qq_channel.utils	import allow_send
from miaoli_bot.api				import get_ncatbot_api, get_thread_id, store_recall

from typing	import Optional


class ToolSchema(BaseModel):
	user_id	: str			= Field(..., description="目标用户")
	group_id: Optional[str]	= Field(default=None, description="目标群号 可选")
	

@tool(args_schema=ToolSchema)
async def send_poke(user_id: str, group_id: Optional[str]) -> str:

	"""
	戳一戳 user_id 对应的用户
	group_id 存在值时 -> 戳 group_id 群的 user_id
	group_id 不存在值时 -> 在私聊戳 user_id
	"""
	
	channel_config = store_recall(PLUGIN_CONFIG)
	if channel_config is not None:
		budget = channel_config.send_budget
		if budget.enable and not allow_send(get_thread_id(), "pokes", budget.max_pokes):
			return "[本轮戳一戳次数已用完 别再戳了]"
	
	ncatbot_api	= get_ncatbot_api()
	
	try:
		
		if group_id:
			await ncatbot_api.qq.messaging.send_poke(group_id=group_id, user_id=user_id)
		
		else:
			await ncatbot_api.qq.messaging.friend_poke(user_id=user_id)
	
	except Exception as e:
		return f"[戳 {user_id} 失败: {type(e).__name__}: {e}]"
	
	return f"[成功戳了 {user_id}]"
