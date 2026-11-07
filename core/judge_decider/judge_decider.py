from .actions	import MustReply, AddScore

from dataclasses	import dataclass
from asyncio		import wait_for as await_for
from typing			import Any, Awaitable, Callable, Sequence, Union

import logging


LOGGER		= logging.getLogger("JudgeDecider")

JudgeNode	= Callable[[Sequence[Any]], Awaitable[Union[MustReply, AddScore, None]]]


@dataclass
class NodeWrapper:
	
	func	: JudgeNode
	priority: int


class JudgeDecider:
	
	def __init__(self, atimeout: float) -> None:
		self.judge_nodes, self.atimeout = [], atimeout
	
	def register_node(self, func: JudgeNode, priority: int) -> NodeWrapper:
		
		"""注册节点并返回节点包装器 不去重"""
	
		node_wrapper = NodeWrapper(func=func, priority=priority)
		self.judge_nodes.append(node_wrapper)
		
		return node_wrapper
	
	def unregister_node(self, node_wrapper: NodeWrapper) -> None:
		"""幂等注销节点"""
		if node_wrapper in self.judge_nodes:
			self.judge_nodes.remove(node_wrapper)
		
	async def decide(self, data: Sequence[Any]) -> Union[float, MustReply]:
		
		score = 0.0
		
		frozen_data		= tuple(data)
		sorted_wrappers	= sorted(self.judge_nodes, key=lambda n: n.priority, reverse=True) # 优先级越大越先跑
		
		for wrapper in sorted_wrappers:
			
			try:
				result = await await_for(
					wrapper.func(frozen_data), timeout=self.atimeout)
			
			except Exception as exception:
				
				LOGGER.error(f"条件节点 {wrapper.func.__name__} 运行出错: "
					f"{type(exception).__name__}: {exception}", exc_info=exception)
			
				continue
			
			if not result:
				LOGGER.info(f"条件节点 {wrapper.func.__name__} 对本次没有意见")
			
			elif isinstance(result, AddScore):
				score = score + result.score
				LOGGER.info(f"条件节点 {wrapper.func.__name__} 因为 {result.reason} 加了 {result.score} 分")
			
			elif isinstance(result, MustReply):
				LOGGER.info(f"条件节点 {wrapper.func.__name__} 因为 {result.reason} 认为必须回复")
				return result
			
			else:
				LOGGER.warning(f"条件节点 {wrapper.func.__name__} 返回了未知动作: {type(result).__name__}")
		
		# 兜底返回分数让调用方决策
		return score
