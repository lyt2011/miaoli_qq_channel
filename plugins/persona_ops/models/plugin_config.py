from pydantic	import BaseModel, Field, model_validator

from ..consts	import HINTS

from typing	import List, Self


class PluginConfig(BaseModel):
	
	enable			: bool		= Field(default=False, description="是否启用拟人提示注入")
	probability		: float		= Field(default=0.6, ge=0, le=1, description="命中场景后仍按这个概率决定是否注入")
	cooldown_turns	: int		= Field(default=3, ge=0, le=100, description="同一会话连续注入之间的冷却轮数")
	kinds			: List[str]	= Field(
		default_factory=lambda: ["tease", "self_deprecate"],
		description="允许的提示类别",
	)
	
	@model_validator(mode="after")
	def check_kinds(self) -> Self:
		
		"""类别写错直接报错 不要静默不生效"""
		
		if unknown := set(self.kinds) - set(HINTS):
			raise ValueError(f"未知的提示类别: {sorted(unknown)}")
		
		return self
