from types	import SimpleNamespace


class FakeMessage:
	
	def __init__(self, text: str = "", at_me: bool = False, segments=None) -> None:
		self.text		= text
		self._at_me		= at_me
		self._segments	= list(segments or [])
	
	def is_at(self, bot_id: str, all_except: bool = False) -> bool:
		return self._at_me
	
	def __iter__(self):
		return iter(self._segments)


class FakeEvent:
	
	def __init__(self, group: bool = True, user_id: str = "u1", text: str = "", at_me: bool = False, segments=None) -> None:
		self.group		= group
		self.user_id	= user_id
		self.message	= FakeMessage(text, at_me, segments)
	
	def is_group_msg(self) -> bool:
		return self.group


class FakeReply:
	pass


def make_entry(event, addressed: bool, seq: int = 1, at: float = 0.0):
	return SimpleNamespace(event=event, addressed=addressed, seq=seq, at=at, wall_time="00:00:00")


def make_config(**social_overrides):
	social = SimpleNamespace(
		enabled				= True,
		tick_seconds		= 1.0,
		quiet				= 8.0,
		follow_up			= False,
		follow_quiet		= 30.0,
		follow_min_unread	= 2,
		chance				= 0.0,
		chance_cooldown_seconds	= 120.0,
		max_submit_per_minute	= 1,
		max_submit_per_hour	= 12,
		speak_cooldown_seconds	= 300.0,
		active_min_minutes	= 15,
		active_max_minutes	= 30,
		idle_minutes		= 6,
		in_flight_timeout_seconds	= 240.0,
		wake				= SimpleNamespace(at=True, name=True, keyword=False, keyword_list=[], question=False, quote=False),
	)
	for key, value in social_overrides.items():
		setattr(social, key, value)
	
	return SimpleNamespace(
		account		= SimpleNamespace(bot_id="bot"),
		channel		= SimpleNamespace(buf_size=2),
		delivery	= SimpleNamespace(
			burst_enable=True,
			burst_interval_min=1.0,
			burst_interval_max=3.0,
			long_gap_probability=0.0,
			long_gap_min=2.5,
			long_gap_max=5.0,
			max_send_per_minute=8,
			max_send_per_hour=60,
		),
		snapshot	= SimpleNamespace(unread_limit=30, max_chars=6000, old_message_minutes=30),
		social		= social,
		submit		= SimpleNamespace(
			group_whitelist=[],
			at_only_in_group=False,
			nickname_variants=[],
			max_reply_chars=500,
		),
	)
