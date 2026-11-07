from account_injector.consts	import PLUGIN_CONFIG as ACCOUNT_CONFIG

from miaoli_qq_channel.core	import MustReply

from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api	import store_recall

from typing	import Any, Optional, Sequence


async def at_me(data: Sequence[Any]) -> Optional[MustReply]:
	
	"""被 @ 必回 @全体 不算"""
	
	bot_id = store_recall(ACCOUNT_CONFIG).bot_id
	
	for event in data:
		
		if not isinstance(event, MessageEvent):
			continue
		
		# is_at 的 all_except=True 会把 @全体 排除掉
		if event.message.is_at(bot_id, all_except=True):
			return MustReply(reason="被@")
	
	return None
