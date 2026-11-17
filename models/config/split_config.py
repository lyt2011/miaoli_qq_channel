from pydantic	import BaseModel, Field


class SplitConfig(BaseModel):
	
	"""输出分割配置 分隔符固定是空行 这里只留开关"""
	
	enable	: bool	= Field(default=True, description="是否按空行分条 切成几条就发几条消息")
