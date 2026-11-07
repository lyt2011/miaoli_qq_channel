from miaoli_qq_channel.api	import register_judge_node

from miaoli_bot.core	import PluginProtocol
from miaoli_bot.consts	import HIGH, MEDIUM

from .judges	import at_me, name_mentioned


class BaseJudges(PluginProtocol):
	
	"""把内置的条件节点注册进通道的决定器"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list = []
	
	async def on_load(self) -> None:
		
		# 被@ 先于 被点名 命名也先于它命中
		self.undo_list.append(register_judge_node(at_me, priority=HIGH))
		self.undo_list.append(register_judge_node(name_mentioned, priority=MEDIUM))
	
	async def on_close(self) -> None:
		
		for undo in self.undo_list:
			undo()
