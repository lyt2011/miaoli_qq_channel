from human_injector.api	import inject_human

from langgraph.runtime	import Runtime

from miaoli_bot.api		import store_recall
from miaoli_bot.models	import GraphRuntimeContext, GraphState

from ..core		import MemeSqlite
from ..consts	import PLUGIN_CONFIG

from typing	import Any, Dict, Optional


async def inject_memes(state: GraphState, runtime: Runtime[GraphRuntimeContext]) -> Optional[Dict[str, Any]]:
	
	"""把可用表情清单写进注入表 由 human_injector 渲染成一条常驻 HumanMessage"""
	
	async with MemeSqlite(store_recall(PLUGIN_CONFIG).database.path) as meme_sqlite:
		rows		= await meme_sqlite.fetch_memes()
		tags_map	= await meme_sqlite.fetch_tags_by_meme_ids([row[0] for row in rows])
	
	memes = [
		f"{hash}: {description}: {tags_map.get(meme_id, [])}"
		for (meme_id, description, hash, _) in rows
	]
	
	# 同名覆盖旧值 旧 undo 自动失效 所以不用自己收集
	inject_human("available-memes", "\n".join(memes))
	
	return None
