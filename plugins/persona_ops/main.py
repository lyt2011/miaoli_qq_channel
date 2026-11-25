from miaoli_bot.api		import get_handler_registry, store_set
from miaoli_bot.consts	import NORMAL, ON_AGENT_START
from miaoli_bot.core	import PluginProtocol

from .consts	import PLUGIN_CONFIG, RAW_CONFIG, STATE
from .models	import PluginConfig
from .nodes		import inject_persona


class PersonaOps(PluginProtocol):
	
	"""按场景给模型注入可选的拟人表达提示 概率 + 冷却 不强制"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list = []
	
	async def on_load(self) -> None:
		
		config = PluginConfig.model_validate(self.config or {})
		
		self.undo_list.append(store_set(RAW_CONFIG, self.config))
		self.undo_list.append(store_set(PLUGIN_CONFIG, config))
		
		# 关闭时不挂节点
		if not config.enable:
			return
		
		self.undo_list.append(store_set(STATE, {}))
		self.undo_list.append(get_handler_registry().on(ON_AGENT_START, inject_persona, priority=NORMAL))
	
	async def on_close(self) -> None:
		
		for undo in self.undo_list:
			undo()
