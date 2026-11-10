from langgraph.runtime	import Runtime

from miaoli_bot.api		import store_recall
from miaoli_bot.models	import GraphRuntimeContext, GraphState

from ..consts	import PLUGIN_CONFIG

from typing	import Any, Dict


async def inject_account(state: GraphState, runtime: Runtime[GraphRuntimeContext]) -> Dict[str, Any]:

	"""给系统提示词注入账号信息"""
	
	account = store_recall(PLUGIN_CONFIG).account
	
	account_info = [
		f"administrator id: {account.admin_id}",
		f"administrator nickname: {account.admin_nickname}",
		f"bot id: {account.bot_id}",
		f"bot nickname: {account.bot_nickname}",
	]

	return {"prompts": {"account-info": "\n".join(account_info)}}
