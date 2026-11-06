from miaoli_bot.core	import PluginProtocol
from miaoli_bot.api		import store_set, get_handler_registry
from miaoli_bot.consts	import NORMAL, ON_AGENT_START

from .models	import PluginConfig
from .nodes		import inject_account
from .consts	import PLUGIN_CONFIG, RAW_CONFIG


class AccountInjector(PluginProtocol):
	
	"""持有账号配置 并把它注入提示词"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list = []
	
	async def on_load(self) -> None:
		
		config		= PluginConfig.model_validate(self.config)
		registry	= get_handler_registry()
		
		self.undo_list.append(store_set(PLUGIN_CONFIG, config))
		self.undo_list.append(store_set(RAW_CONFIG, self.config))
		self.undo_list.append(registry.on(ON_AGENT_START, inject_account, priority=NORMAL))
	
	async def on_close(self) -> None:
		
		for undo in self.undo_list:
			undo()
