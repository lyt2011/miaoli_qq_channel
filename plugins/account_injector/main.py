from miaoli_bot.core	import PluginProtocol
from miaoli_bot.api		import get_handler_registry
from miaoli_bot.consts	import NORMAL, ON_AGENT_START

from .nodes	import inject_account


class AccountInjector(PluginProtocol):
	
	"""把通道持有的账号配置注入提示词"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list = []
	
	async def on_load(self) -> None:
		
		# 账号配置由 miaoli_qq_channel 校验并写进共享容器 本插件只挂节点
		registry	= get_handler_registry()
		
		self.undo_list.append(registry.on(ON_AGENT_START, inject_account, priority=NORMAL))
	
	async def on_close(self) -> None:
		
		for undo in self.undo_list:
			undo()
