from pydantic	import BaseModel, Field

from typing		import Optional


class CorpusConfig(BaseModel):
	
	enable		: bool			= Field(default=False, description="是否把每条消息解析后追加进语料文件")
	path		: Optional[str]	= Field(default=None, description="语料文件路径 留空则写到插件目录下的 data/corpus.jsonl")
	encoding	: str			= Field(default="utf-8", description="写文件时使用的编码")
	flush		: bool			= Field(default=True, description="每条消息写完是否立刻刷盘 不刷最多丢最后一条")
