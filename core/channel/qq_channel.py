from miaoli_bot.api			import store_recall
from miaoli_bot.protocols	import BaseChannel, Content

from ...consts				import READY_BUFFER, PLUGIN_CONFIG
from ...utils				import easier_send
from .qq_channel_message	import (
	QQChannelMessage,
	content_to_text,
	split_text,
	split_thread_id,
)

from typing	import FrozenSet, List

import random
import asyncio


class QQChannel(BaseChannel):
	
	"""把 QQ 事件环形缓冲暴露成 miaoli_bot 的消息通道"""
	
	@property
	def name(self) -> str:
		return "qq"
	
	@property
	def platforms(self) -> FrozenSet[str]:
		return frozenset({"qq"})
	
	async def drain(self) -> List[QQChannelMessage]:
		
		"""取走就绪区里的全部消息 一次取空
		
		不能 await：外层 wait_for 一旦取消 已经取出的消息就没了
		"""
		
		ready = store_recall(READY_BUFFER)
		if not ready:
			return []
		
		# 原地复制再清空 保住 store 里那个列表的引用
		messages = list(ready)
		ready.clear()
		
		return messages
	
	async def reply(self, platform: str, thread_id: str, content: Content) -> None:
		
		"""按会话标识把正文发回 QQ 分隔符切分成多条消息 每段按配置模拟打字"""
		
		if platform not in self.platforms:
			raise ValueError(f"QQ 通道不支持平台: {platform}")
		
		text  = content_to_text(content)
		mode, chat_id  = split_thread_id(thread_id)
		config    = store_recall(PLUGIN_CONFIG)
		
		if config.split.enable:
			pieces = split_text(text, config.split.delimiter)
		
		else:
			pieces = [text.strip()] if text.strip() else []
		
		for piece in pieces:
			
			# 按字数估算打字耗时 两个速度都是 0 时等于不等待
			if config.typing.enable:
				max_speed  = config.typing.base_speed + config.typing.speed_offset
				min_speed  = config.typing.base_speed - config.typing.speed_offset
				ram_speed  = random.uniform(min_speed, max_speed)
				
				await asyncio.sleep(len(piece) * ram_speed)
			
			await easier_send(
				mode		= mode,
				chat_id		= chat_id,
				ob11_message	= [{"type": "text", "data": {"text": piece}}],
			)
