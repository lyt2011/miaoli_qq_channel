from account_injector.consts	import PLUGIN_CONFIG as ACCOUNT_CONFIG

from miaoli_qq_channel.core	import MustReply

from ncatbot.event.qq	import MessageEvent

from miaoli_bot.api	import store_recall

from typing	import Any, Optional, Sequence


async def name_mentioned(data: Sequence[Any]) -> Optional[MustReply]:
	
	"""被叫到机器人昵称必回"""
	
	nickname = store_recall(ACCOUNT_CONFIG).bot_nickname.strip()
	
	# 昵称空串时任何文本都算命中
	if not nickname:
		return None
	
	for event in data:
		
		if not isinstance(event, MessageEvent):
			continue
		
		if nickname in event.message.text:
			return MustReply(reason="被叫昵称")
	
	return None
