from miaoli_bot.api			import store_recall
from miaoli_bot.protocols	import BaseChannel, Content

from ...consts				import MESSAGE_BUFFER, PLUGIN_CONFIG, READY_BUFFER, SOCIAL_STORE
from ...models				import PluginConfig
from ...utils				import easier_send
from ..delivery				import SendGate, burst_gap
from ..markdown				import strip_markdown
from ..social				import SocialStore
from ..tts					import strip_tail_symbols, synthesize
from .wake_policy			import is_reply_allowed
from .qq_channel_message	import (
	QQChannelMessage,
	content_to_text,
	split_text,
	split_thread_id,
)

from typing	import Dict, FrozenSet, List, Literal, Union

import base64
import random
import asyncio
import logging
import time


LOGGER = logging.getLogger("QQChannel")

# 回复正文的分条依据 空行即一条
SEPARATOR	= "\n\n"

# 一句话收尾的句号 文字发出去之前去掉
FULL_STOP	= "。"


class QQChannel(BaseChannel):
	
	"""把 QQ 事件环形缓冲暴露成 miaoli_bot 的消息通道"""
	
	def __init__(self) -> None:
		super().__init__()
		
		# thread_id -> 发送频率账本
		self.gates			: Dict[str, SendGate]	= {}
		# thread_id -> 这一窗最后一行的序号 回复成功后推进水位
		self.window_seq		: Dict[str, int]		= {}
	
	@property
	def name(self) -> str:
		return "qq"
	
	@property
	def platforms(self) -> FrozenSet[str]:
		return frozenset({"qq"})
	
	async def drain(self) -> List[object]:
		
		"""取走就绪区里的全部消息 一次取空
		
		不能 await：外层 wait_for 一旦取消 已经取出的消息就没了
		"""
		
		ready = store_recall(READY_BUFFER)
		if not ready:
			return []
		
		# 原地复制再清空 保住 store 里那个列表的引用
		messages = list(ready)
		ready.clear()
		
		for message in messages:
			if isinstance(message, QQChannelMessage):
				self.window_seq[message.thread_id] = message.sequence_end
		
		return messages
	
	async def reply(self, platform: str, thread_id: str, content: Content) -> None:
		
		"""剥掉 markdown 后按空行切成几条 语音与文字都逐条发
		
		markdown 在语音分支之前剥 剥完换行结构原样保留 分条依据就是原文的空行
		语音的骰子仍按整条回复掷一次 命中就每条各合成一段语音
		太长或太短 以及合成与发送失败 都回退到文字
		发送完统一回报状态机：推进水位 / 记录发言时间 / 清在途标记
		"""
		
		if platform not in self.platforms:
			raise ValueError(f"QQ 通道不支持平台: {platform}")
		
		mode, chat_id	= split_thread_id(thread_id)
		config			= store_recall(PLUGIN_CONFIG)
		seq_end			= self.window_seq.pop(thread_id, 0)
		sent			= False
		
		try:
			text	= strip_markdown(content_to_text(content))
			pieces	= split_text(text, SEPARATOR) if config.split.enable else [text.strip()]
			pieces	= [piece for piece in pieces if piece]
			
			if not pieces:
				return None
			
			if not is_reply_allowed(mode, text, config.submit.max_reply_chars):
				LOGGER.warning(f"群 {chat_id} 回复超限（{len(text)} > {config.submit.max_reply_chars}），整条不发送")
				return None
			
			sent = await self.send_pieces(mode, chat_id, pieces, config, thread_id)
		
		finally:
			self.finish_reply(thread_id, sent, seq_end, config)
		
		return None
	
	async def send_pieces(
		self,
		mode		: Literal["group", "private"],
		chat_id		: Union[str, int],
		pieces		: List[str],
		config		: PluginConfig,
		thread_id	: str,
	) -> bool:
		
		"""逐条发送 受发送频率与分条停顿约束 有一条发出去就算 sent"""
		
		sent = False
		gate = self.gate_of(thread_id, config)
		
		# w 与爱心只有字形没有读音 语音送过滤后的 文字路径仍发原文
		# 长度门槛算的是说出来的字数 空行空白与尾巴符号都不算
		speaking	= strip_tail_symbols(pieces[0] if len(pieces) == 1 else "\n\n".join(pieces))
		spoken		= "".join(speaking.split())
		
		# 一次回复只掷一次骰子 命中就是整条语音 每条按空行切开各发一段
		use_voice = (
			config.voice.enable
			and config.voice.min_chars <= len(spoken) <= config.voice.max_chars
			and random.random() < config.voice.probability
		)
		
		for index, piece in enumerate(pieces):
			if index:
				await asyncio.sleep(burst_gap(config))
			
			# 发太多就停手 剩下的直接丢 记账留给日志
			if not gate.acquire():
				LOGGER.warning(f"{thread_id} 达到发送频率上限 本轮剩余 {len(pieces) - index} 条不发")
				break
			
			if use_voice and await self.send_voice(mode, chat_id, piece, config):
				sent = True
				continue
			
			sent = await self.send_text(mode, chat_id, piece, config) or sent
		
		return sent
	
	def finish_reply(self, thread_id: str, sent: bool, seq_end: int, config: PluginConfig) -> None:
		
		"""一轮跑图结束 状态机与水位都在这里收尾"""
		
		now			= time.monotonic()
		social		= store_recall(SOCIAL_STORE, default=None)
		if isinstance(social, SocialStore):
			social.on_reply_finished(thread_id, sent, now, config)
		
		if not sent or not seq_end:
			return None
		
		buffers = store_recall(MESSAGE_BUFFER, default=None)
		if buffers is not None:
			buffers.mark_delivered(thread_id, seq_end)
		
		return None
	
	def gate_of(self, thread_id: str, config: PluginConfig) -> SendGate:
		
		"""每个会话一个发送账本 首次用到时建"""
		
		gate = self.gates.get(thread_id)
		if gate is None:
			gate = self.gates[thread_id] = SendGate(
				per_minute	= config.delivery.max_send_per_minute,
				per_hour	= config.delivery.max_send_per_hour,
			)
		return gate
	
	async def send_voice(
		self,
		mode		: Literal["group", "private"],
		chat_id		: Union[str, int],
		piece		: str,
		config		: PluginConfig,
	) -> bool:
		
		"""把一条正文合成成语音发出去 没成功返回 False"""
		
		audio = await synthesize(
			text	= strip_tail_symbols(piece),
			url		= config.voice.mimo_url,
			key		= config.voice.mimo_key,
			model	= config.voice.model,
			voice	= config.voice.voice,
			style	= config.voice.style,
		)
		
		if audio is None:
			return False
		
		# 合成花了时间 不再补打字延迟
		try:
			await easier_send(
				mode		= mode,
				chat_id		= chat_id,
				ob11_message	= [{
					"type": "record",
					"data": {"file": f"base64://{base64.b64encode(audio).decode()}"},
				}],
			)
		
		except Exception:
			LOGGER.warning("语音发送失败 回退到文字", exc_info=True)
			return False
		
		return True
	
	async def send_text(
		self,
		mode		: Literal["group", "private"],
		chat_id		: Union[str, int],
		piece		: str,
		config		: PluginConfig,
	) -> bool:
		
		"""发一条文字 句尾的句号去掉 按字数模拟打字耗时 返回是否发送"""
		
		if piece.endswith(FULL_STOP):
			piece = piece[:-len(FULL_STOP)]
		
		if not piece:
			return False
		
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
		
		return True
