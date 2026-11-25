from typing	import List, Sequence, Tuple


def format_age(seconds: float) -> str:
	
	"""把「多久以前」写成人话"""
	
	if seconds < 5:
		return "刚刚"
	if seconds < 60:
		return f"{int(seconds)} 秒前"
	if seconds < 3600:
		return f"{int(seconds // 60)} 分钟前"
	
	return f"{int(seconds // 3600)} 小时前"


def time_prefix(wall_time: str, age_seconds: float) -> str:
	return f"[{wall_time} · {format_age(age_seconds)}] "


def build_header(reason: str, unread: int, delivered_seq: int, is_group: bool) -> str:
	
	"""快照头：唤醒理由 + 未读条数 + 已读水位 + 「不是全部」提醒"""
	
	return (
		f"[唤醒理由：{reason}；未读 {unread} 条；已读水位 {delivered_seq}；"
		"你看到的不是全部，回复别复述记录]"
	)


def omitted_note(count: int) -> str:
	
	"""预算不够时省略了多少条"""
	
	if count <= 0:
		return ""
	
	return f"[更早的 {count} 条未唤醒消息已省略]"


def old_warning(age_seconds: float, minutes: int) -> str:
	
	"""最新一条都隔很久了 提醒模型别用秒回语气"""
	
	if age_seconds <= minutes * 60:
		return ""
	
	return "[注意：最新一条消息也已经放了很久，这是旧账，不要用「刚看到」的语气，按现在的时间说话]"


def trim(
	lines: Sequence[str],
	max_chars: int,
	always_keep: int = 1,
) -> Tuple[List[str], int]:
	
	"""从最旧的开始省 直到总字数塞进预算
	
	always_keep 是最少要保留的最近几条（默认最新一条）
	返回（保留的行，被省掉的行数）
	"""
	
	if not lines:
		return [], 0
	
	budget = max(1, max_chars)
	kept: List[str] = []
	used = 0
	
	for index in range(len(lines) - 1, -1, -1):
		line = lines[index]
		cost = len(line) + 1
		need = max(0, always_keep - len(kept))
		
		if kept and used + cost > budget and need <= 0:
			return list(reversed(kept)), index + 1
		
		kept.append(line)
		used += cost
	
	return list(reversed(kept)), 0
