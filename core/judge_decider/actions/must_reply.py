class MustReply:
	
	def __init__(self, reason: str) -> None:
		
		if not reason.strip():
			raise ValueError("MustReply 必须有 reason 且不能为空")
		
		self.reason = reason