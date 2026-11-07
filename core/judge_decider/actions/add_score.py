class AddScore:
	
	def __init__(self, score: float, reason: str = "") -> None:
		
		if score > 1 or score < 0:
			raise ValueError(f"分数只能为 0-1，接收到 {score}")
		
		self.score	= score
		self.reason	= reason
