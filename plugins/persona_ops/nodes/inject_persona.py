from human_injector.api	import inject_human

from langgraph.runtime	import Runtime

from miaoli_bot.api		import get_thread_id, store_recall
from miaoli_bot.models	import GraphRuntimeContext, GraphState

from ..consts	import HINTS, HINT_NAME, PLUGIN_CONFIG, STATE
from ..utils	import input_text, is_qq, match_kind, should_emit

from typing	import Any, Dict, Optional

import random


async def inject_persona(state: GraphState, runtime: Runtime[GraphRuntimeContext]) -> Optional[Dict[str, Any]]:
	
	"""按当前这轮的消息场景 给模型一条可选的拟人表达提示 每轮最多一条"""
	
	config = store_recall(PLUGIN_CONFIG)
	
	# 只管 QQ 平台
	if not config.enable or not is_qq(state.get("platform")):
		return None
	
	text = input_text(state.get("input"))
	
	# 太短没有语境
	if len(text) < 2:
		return None
	
	thread_id = get_thread_id()
	if thread_id is None:
		return None
	
	table	= store_recall(STATE)
	entry	= table.setdefault(thread_id, {"turn": 0, "kind": None, "at": 0, "undo": None})
	entry["turn"] += 1
	
	# 上一轮的提示先撤掉 不撤会一直挂在上下文里
	if entry["undo"] is not None:
		entry["undo"]()
		entry["undo"] = None
	
	kind = match_kind(text, config.kinds)
	
	if not should_emit(kind, entry, entry["turn"], config.cooldown_turns, config.probability, random.random()):
		return None
	
	entry["kind"]	= kind
	entry["at"]		= entry["turn"]
	entry["undo"]	= inject_human(HINT_NAME, HINTS[kind], thread_id)
	
	return None
