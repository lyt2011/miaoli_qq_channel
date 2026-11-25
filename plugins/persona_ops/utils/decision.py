from typing	import Any, Dict, Optional


def in_cooldown(entry: Dict[str, Any], turn: int, cooldown_turns: int) -> bool:
	
	"""同一会话里距上次注入不足冷却轮数"""
	
	last = entry.get("at", 0)
	
	return bool(last) and (turn - last) <= cooldown_turns


def should_emit(
	kind: Optional[str],
	entry: Dict[str, Any],
	turn: int,
	cooldown_turns: int,
	probability: float,
	roll: float,
) -> bool:
	
	"""命中类别 + 过冷却 + 过概率 三道闸都过才注入"""
	
	if kind is None:
		return False
	
	if in_cooldown(entry, turn, cooldown_turns):
		return False
	
	return roll < probability
