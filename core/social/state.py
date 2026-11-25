from collections	import deque
from dataclasses	import dataclass, field
from enum			import StrEnum
from typing			import Any, Deque, Dict, Optional

import time
import random
import logging

from .policy	import PRIORITY, WakeReason, classify, roll_chance


LOGGER = logging.getLogger("miaoli_qq_channel/social_state")

# 提交次数与发言次数的滑动窗口 只保留最近一小时
HOUR_SECONDS = 3600.0
MINUTE_SECONDS = 60.0


class ChatState(StrEnum):
	
	"""会话社交状态"""
	
	DIVING	= "diving"
	ACTIVE	= "active"


@dataclass
class WakeDecision:
	
	"""一次「该说话了」的判定结果"""
	
	reason		: WakeReason
	priority	: int
	at			: float


@dataclass
class SessionSocial:
	
	"""一个会话的社交状态 只在进程内 重启清空"""
	
	state				: ChatState			= ChatState.DIVING
	state_since			: float				= 0.0
	active_until		: float				= 0.0
	follow_until		: float				= 0.0
	pending				: Optional[WakeDecision]	= None
	chance_rolled_at	: float				= float("-inf")
	submitted			: Deque[float]		= field(default_factory=deque)
	replied				: Deque[float]		= field(default_factory=deque)
	in_flight			: bool				= False
	in_flight_since		: float				= 0.0
	last_message_at		: float				= 0.0
	last_reply_at		: float				= 0.0


def is_private_thread(thread_id: str) -> bool:
	
	"""私聊不设限 消息一到就算被叫"""
	
	return thread_id.startswith("private-")


class SocialStore:
	
	"""所有会话的社交状态 按会话号分桶"""
	
	def __init__(self) -> None:
		self.sessions	: Dict[str, SessionSocial]	= {}
	
	def session(self, thread_id: str) -> SessionSocial:
		session = self.sessions.get(thread_id)
		if session is None:
			session = self.sessions[thread_id] = SessionSocial()
		return session
	
	def on_message(
		self,
		thread_id	: str,
		entry		: Any,
		config		: Any,
		now			: Optional[float] = None,
	) -> Optional[WakeReason]:
		
		"""记一条消息 顺手判定它值不值得开窗 返回命中的理由"""
		
		now		= time.monotonic() if now is None else now
		session	= self.session(thread_id)
		social	= config.social
		
		session.last_message_at = now
		
		reason = classify(entry.event, entry.addressed, social.wake, config.account.bot_id)
		if reason is not None:
			session.pending = WakeDecision(reason, PRIORITY[reason], now)
			self._enter_active(session, config, now)
			return reason
		
		# 潜水时才摇随机 私聊不摇
		if session.state is ChatState.DIVING and not is_private_thread(thread_id):
			cooldown = social.chance_cooldown_seconds
			if now - session.chance_rolled_at >= cooldown and roll_chance(social.chance):
				session.pending = WakeDecision(WakeReason.CHANCE, PRIORITY[WakeReason.CHANCE], now)
				return WakeReason.CHANCE
		
		return None
	
	def decide(self, thread_id: str, now: float, config: Any) -> Optional[WakeDecision]:
		
		"""攒够了没有 该不该提交"""
		
		session = self.session(thread_id)
		
		if session.pending is not None:
			return session.pending
		
		if not self.is_following(thread_id, config, now):
			return None
		
		# 跟随里的消息不走缓冲区默认静默/随机策略 下个 tick 就交 由跟随自己的限流兜底
		return WakeDecision(WakeReason.FOLLOW, PRIORITY[WakeReason.FOLLOW], now)
	
	def can_submit(self, thread_id: str, now: float, config: Any) -> bool:
		
		"""每个会话的提交频率上限 私聊无限 跟随时用跟随自己的限流"""
		
		if is_private_thread(thread_id):
			return True
		
		session	= self.session(thread_id)
		self._prune_stamps(session.submitted, now)
		
		if self.is_following(thread_id, config, now):
			follow = config.follow
			if session.submitted and now - session.submitted[-1] < follow.min_interval_seconds:
				return False
			recent_minute = sum(1 for stamp in session.submitted if now - stamp < MINUTE_SECONDS)
			if recent_minute >= follow.max_submit_per_minute:
				return False
			recent_hour = sum(1 for stamp in session.submitted if now - stamp < HOUR_SECONDS)
			return recent_hour < follow.max_submit_per_hour
		
		social	= config.social
		
		if len(session.submitted) >= social.max_submit_per_minute:
			recent = sum(1 for stamp in session.submitted if now - stamp < MINUTE_SECONDS)
			if recent >= social.max_submit_per_minute:
				return False
		
		recent_hour = sum(1 for stamp in session.submitted if now - stamp < HOUR_SECONDS)
		
		return recent_hour < social.max_submit_per_hour
	
	def on_submit(self, thread_id: str, now: float, decision: WakeDecision, config: Any) -> None:
		
		"""提交成功后记账：清 pending、置在途、记一次提交、续跟随计时"""
		
		session = self.session(thread_id)
		session.pending = None
		session.in_flight = True
		session.in_flight_since = now
		session.submitted.append(now)
		
		if decision.reason is WakeReason.CHANCE:
			session.chance_rolled_at = now
		
		self._enter_active(session, config, now)
		if decision.reason is WakeReason.FOLLOW:
			session.follow_until = now + config.follow.duration_minutes * 60.0
	
	def on_reply_finished(self, thread_id: str, ok: bool, now: float, config: Any) -> None:
		
		"""一轮跑图结束 成功了记发言时间并续上聊天状态"""
		
		session = self.session(thread_id)
		session.in_flight = False
		
		if not ok:
			return None
		
		session.last_reply_at = now
		session.replied.append(now)
		self._enter_active(session, config, now)
		if config.follow.enable:
			session.follow_until = now + config.follow.duration_minutes * 60.0
		
		return None
	
	def expire(self, thread_id: str, now: float, config: Any) -> None:
		
		"""状态超时与在途超时 每个 tick 调一次"""
		
		session = self.session(thread_id)
		social	= config.social
		
		if session.in_flight and now - session.in_flight_since > social.in_flight_timeout_seconds:
			LOGGER.warning(f"{thread_id} 在途窗口超时（{social.in_flight_timeout_seconds}s）放行下一轮")
			session.in_flight = False
		
		# 聊天状态到期或冷场就回潜水
		if session.state is ChatState.ACTIVE:
			idle = now - session.last_message_at > social.idle_minutes * 60
			if now >= session.active_until or idle:
				session.state		= ChatState.DIVING
				session.state_since	= now
				session.active_until	= 0.0
				session.follow_until	= 0.0
				session.pending		= None
				LOGGER.info(f"{thread_id} 回到潜水（{'冷场' if idle else '活跃到期'}）")
		
		self._prune_stamps(session.submitted, now)
		self._prune_stamps(session.replied, now)
	
	def prune(self, now: float, idle_seconds: float = HOUR_SECONDS) -> None:
		
		"""清掉完全空闲的会话状态"""
		
		for thread_id in list(self.sessions):
			session = self.sessions[thread_id]
			if session.in_flight or session.pending is not None:
				continue
			last = max(session.last_message_at, session.last_reply_at, session.state_since)
			if now - last >= idle_seconds:
				self.sessions.pop(thread_id, None)
	
	def is_following(self, thread_id: str, config: Any, now: float) -> bool:
		
		"""该会话是否处于跟随中 跟随里的消息跳过缓冲默认策略
		
		跟随由「回复完成」或「跟随中的一次提交」开启 被叫进入 active 本身还不算
		"""
		
		session = self.session(thread_id)
		return config.follow.enable and session.state is ChatState.ACTIVE and now < session.follow_until
	
	def _enter_active(self, session: SessionSocial, config: Any, now: float) -> None:
		
		"""被叫到或刚发完言都算进入跟随 时长由 follow.duration_minutes 决定 每次提交后重算"""
		
		session.state		= ChatState.ACTIVE
		session.state_since	= now
		session.active_until = now + config.follow.duration_minutes * 60.0
	
	def _prune_stamps(self, stamps: Deque[float], now: float) -> None:
		while stamps and now - stamps[0] > HOUR_SECONDS:
			stamps.popleft()
