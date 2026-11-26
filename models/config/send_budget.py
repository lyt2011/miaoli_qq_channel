from pydantic	import BaseModel, Field


class SendBudgetConfig(BaseModel):
	
	"""一轮跑图里的发送预算 防止模型一直调发送工具刷屏"""
	
	enable			: bool	= Field(default=True, description="发送预算开关")
	max_messages	: int	= Field(default=3, description="一轮最多用 send_message_to_qq 发几条文字（0 表示不限）", ge=0, le=100)
	max_memes		: int	= Field(default=2, description="一轮最多发表情包（0 表示不限）", ge=0, le=100)
	max_pokes		: int	= Field(default=1, description="一轮最多戳几次（0 表示不限）", ge=0, le=100)
