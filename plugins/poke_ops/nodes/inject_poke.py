from human_injector.api	import inject_human

from langgraph.runtime	import Runtime

from miaoli_bot.api		import get_thread_id, store_recall
from miaoli_bot.models	import GraphRuntimeContext, GraphState

from ..consts	import HINT_NAME, HINTS, PLUGIN_CONFIG, STATE
from ..utils	import input_text, is_due, is_qq

from typing	import Any, Dict, Optional

import random
import time


async def inject_poke(state: GraphState, runtime: Runtime[GraphRuntimeContext]) -> Optional[Dict[str, Any]]:
	
	"""隔一阵给模型一条「可以戳一戳对方」的可选提示 同一会话有最短间隔"""
	
	config = store_recall(PLUGIN_CONFIG)
	
	# 只管 QQ 平台
	if not config.enable or not is_qq(state.get("platform")):
		return None
	
	# 没有新的输入就没有具体对象可戳
	if not input_text(state.get("input")):
		return None
	
	thread_id = get_thread_id()
	if thread_id is None:
		return None
	
	table	= store_recall(STATE)
	entry	= table.setdefault(thread_id, {"at": 0.0, "undo": None})
	
	# 上一轮的提示先撤掉 不撤会一直挂在上下文里
	if entry["undo"] is not None:
		entry["undo"]()
		entry["undo"] = None
	
	now = time.monotonic()
	if not is_due(entry["at"], now, config.interval_minutes):
		return None
	
	entry["at"]		= now
	entry["undo"]	= inject_human(HINT_NAME, random.choice(HINTS), thread_id)
	
	return None


async def clear_poke(state: GraphState, runtime: Runtime[GraphRuntimeContext]) -> None:
	
	"""回合结束就撤掉这条提示 它只该影响当轮"""
	
	thread_id = get_thread_id()
	if thread_id is None:
		return None
	
	entry = store_recall(STATE).get(thread_id)
	if entry is not None and entry["undo"] is not None:
		entry["undo"]()
		entry["undo"] = None
	
	return None
