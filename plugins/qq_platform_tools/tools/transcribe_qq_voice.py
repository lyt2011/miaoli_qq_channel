from langchain_core.tools	import tool

from pydantic	import BaseModel, Field

from miaoli_bot.api	import get_ncatbot_api


class ToolSchema(BaseModel):
	message_id: str = Field(..., description="目标语音消息的 message_id")


@tool(args_schema=ToolSchema)
async def transcribe_qq_voice(message_id: str) -> str:

	"""
	把一条 QQ 语音消息转成文字
	用的是 QQ 自带的转文字能力 不需要额外接口
	只能转语音消息 别的类型会报错 消息被撤回或 QQ 转不出来也会失败
	"""

	ncatbot_api = get_ncatbot_api()
	
	try:
		result = await ncatbot_api.qq.query.fetch_ptt_text(message_id)
	
	except Exception as e:
		return f"[转文字失败: {type(e).__name__}: {e}]"

	if not result.text:
		return "[转文字失败: 这条语音没有转出文字]"

	return result.text
