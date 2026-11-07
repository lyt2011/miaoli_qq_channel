from miaoli_bot.api	import store_recall

from ..core		import JudgeNode
from ..consts	import JUDGE_DECIDER

from typing	import Callable


def register_judge_node(func: JudgeNode, priority: int = 0) -> Callable[[], None]:
	
	"""注册条件节点 返回幂等注销函数"""
	
	judge_decider	= store_recall(JUDGE_DECIDER)
	node_wrapper	= judge_decider.register_node(func, priority=priority)
	
	def undo() -> None:
		judge_decider.unregister_node(node_wrapper)
	
	return undo
