from langchain_core.tools	import tool

from pydantic	import BaseModel, Field, model_validator

from miaoli_qq_channel.utils	import easier_send
from miaoli_bot.api				import get_ncatbot_api

from ..models	import (
	AtMessage,
	FileMessage,
	ImageMessage,
	Messages,
	RecordMessage,
	TextMessage,
	VideoMessage,
	ReplyMessage as Reply,
)

from typing	import Literal, Self


Mode	= Literal["group", "private"]


class ToolSchema(BaseModel):
	
	chat_id	: str		= Field(..., description="接收方ID")
	mode	: Mode		= Field(..., description="group 发往群聊 private 发往私聊")
	messages: Messages	= Field(..., description="要发送到QQ的消息数组", min_length=1)
	
	@model_validator(mode="after")
	def check_message(self) -> Self:
		
		"""检查消息数量与正确性喵"""
		
		# 先给所有消息分类
		text	= [message for message in self.messages if isinstance(message, TextMessage)]
		at		= [message for message in self.messages if isinstance(message, AtMessage)]
		reply	= [message for message in self.messages if isinstance(message, Reply)]
		image	= [message for message in self.messages if isinstance(message, ImageMessage)]
		file	= [message for message in self.messages if isinstance(message, FileMessage)]
		video	= [message for message in self.messages if isinstance(message, VideoMessage)]
		record	= [message for message in self.messages if isinstance(message, RecordMessage)]
		
		# 检查多媒体数量 注意图片是可以发很多张的
		if (media_count := len([*file, *video, *record])) > 1:
			raise ValueError(f"file/video/record 最多只能存在一条，接收到 {media_count} 条")
		
		# 检查图片数量
		if (image_count := len(image)) > 20:
			raise ValueError(f"image 最多 20 张，接收到 {image_count} 张")
		
		# 检查 reply 数量
		if (reply_count := len(reply)) > 1:
			raise ValueError(f"reply 最多 1 条， 接收到 {reply_count} 条")
		
		# 检查冲突消息
		if [*text, *at, *reply, *image] and [*file, *video, *record]:
			raise ValueError("text/at/reply/image 不可跟 file/video/record 同时发送")
		
		return self


@tool(args_schema=ToolSchema)
async def send_message_to_qq(chat_id: str, mode: Mode, messages: Messages) -> str:

	"""
	发送一条信息到 QQ

	messages 字段说明
	reply 最多 1 条
	image 最多 20 条，可以与 text/at/reply 同时存在
	video/file/record 最多 1 条，不能跟 text/at/reply/image 同时存在
	"""
	
	ob11_messages = [message.to_ob11() for message in messages]
	
	try:
	
		send_result = await easier_send(
			mode			= mode,
			chat_id			= chat_id,
			ob11_message	= ob11_messages,
			ncatbot_api		= get_ncatbot_api(),
		)
	
	except Exception as e:
		return f"[发送失败: {type(e).__name__}: {e}]"

	return send_result.model_dump_json()
