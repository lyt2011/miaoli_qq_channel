from miaoli_bot.api		import register_tool
from miaoli_bot.core	import PluginProtocol

from .tools	import (
	download_qq_file,
	send_message_to_qq,
	delete_qq_message,
	query_qq_message,
	send_poke,
)


class QQPlatformTools(PluginProtocol):
	
	"""QQ 平台工具"""
	
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)
		
		self.undo_list = []
	
	async def on_load(self) -> None:
		
		self.undo_list.append(register_tool(download_qq_file))
		self.undo_list.append(register_tool(send_message_to_qq))
		self.undo_list.append(register_tool(delete_qq_message))
		self.undo_list.append(register_tool(query_qq_message))
		self.undo_list.append(register_tool(send_poke))
	
	async def on_close(self) -> None:
		
		for undo in self.undo_list:
			undo()
