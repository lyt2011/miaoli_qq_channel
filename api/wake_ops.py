from miaoli_bot.api	import please_run_graph, store_recall

from ..consts	import PLUGIN_CONFIG, READY_BUFFER
from ..core	import WakeMessage, split_thread_id

import logging


LOGGER = logging.getLogger("miaoli_qq_channel/wake")


def push_wake_message(thread_id: str, content: str) -> bool:
	
	"""把一个定时唤醒塞进就绪区 主包会把它当普通渠道消息送进图
	
	返回 True 表示已投递 False 表示本轮满了/重复了（都是瞬态 下轮再来就好）
	空正文直接抛 ValueError：主包在上游就会把它丢掉 到这里已经是设计错误
	"""
	
	split_thread_id(thread_id)
	
	if not content.strip():
		raise ValueError("唤醒消息必须带正文 空消息会被主包当成无内容丢掉")
	
	config  = store_recall(PLUGIN_CONFIG)
	ready  = store_recall(READY_BUFFER)
	
	if len(ready) >= config.channel.buf_size:
		LOGGER.info(f"就绪区已满({len(ready)}) 本轮拒收唤醒 {thread_id}")
		return False
	
	if any(message.thread_id == thread_id for message in ready):
		LOGGER.info(f"{thread_id} 已在就绪区里 本轮不重复投递")
		return False
	
	ready.append(WakeMessage(thread_id, content))
	please_run_graph()
	
	return True
