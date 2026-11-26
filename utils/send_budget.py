from typing	import Dict, Optional


# thread_id -> {kind: 已用次数} 一轮跑图开始时重置
_COUNTS: Dict[str, Dict[str, int]] = {}


def reset(thread_id: str) -> None:
	
	"""新一轮开始 清空这个会话的发送计数"""
	
	_COUNTS[thread_id] = {}


def clear(thread_id: str) -> None:
	
	"""回合结束 把这个会话的计数删掉"""
	
	_COUNTS.pop(thread_id, None)


def allow(thread_id: Optional[str], kind: str, limit: int) -> bool:
	
	"""这次发送还能不能放行 拿不到 thread_id 或 limit 为 0 时一律放行"""
	
	if not thread_id or limit <= 0:
		return True
	
	counts = _COUNTS.setdefault(thread_id, {})
	used = counts.get(kind, 0)
	if used >= limit:
		return False
	
	counts[kind] = used + 1
	
	return True


def used(thread_id: str, kind: str) -> int:
	
	"""已经用了多少次 测试与调试用"""
	
	return _COUNTS.get(thread_id, {}).get(kind, 0)
