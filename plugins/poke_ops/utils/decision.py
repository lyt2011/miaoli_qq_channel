def is_due(last_at: float, now: float, interval_minutes: int) -> bool:
	
	"""距离上次提示是否已经够久"""
	
	return now - last_at >= interval_minutes * 60
