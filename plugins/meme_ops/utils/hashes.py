HEX_CHARS = frozenset("0123456789abcdef")


def normalize_meme_hash(value: str) -> str:
	
	"""模型偶尔会漏掉前导 0 或者写成大写 统一成 32 位小写 hex"""
	
	cleaned = "".join(char for char in (value or "").strip().lower() if char in HEX_CHARS)
	if len(cleaned) > 32:
		cleaned = cleaned[-32:]
	
	return cleaned.rjust(32, "0")
