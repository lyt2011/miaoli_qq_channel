from pydantic	import BaseModel, Field


class PluginConfig(BaseModel):
	
	enable				: bool	= Field(default=False, description="是否启用定期戳一戳提示")
	interval_minutes	: int	= Field(default=10, ge=1, le=1440, description="同一会话两次提示之间的最短间隔（分钟）")
