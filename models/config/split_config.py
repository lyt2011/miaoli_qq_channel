from pydantic	import BaseModel, Field, model_validator

from typing	import Self


class SplitConfig(BaseModel):
	
	"""输出分割配置"""
	
	enable		: bool	= Field(default=True, description="是否启用分割")
	delimiter	: str	= Field(default="\n\n", description="分隔符 切成几段就发几条消息")
	
	
	@model_validator(mode="after")
	def ensure_delimiter(self) -> Self:
		
		"""启用分割时分隔符不能为空"""
		
		if self.enable and not self.delimiter:
			raise ValueError("启用分割时分隔符必须要有内容")
		
		return self
