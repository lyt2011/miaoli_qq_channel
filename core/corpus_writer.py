from ncatbot.event.qq	import MessageEvent

from .channel	import render_event, thread_id_of

from pathlib	import Path
from datetime	import datetime
from typing		import Any, Dict, Optional

import json


def to_record(event: MessageEvent) -> Dict[str, Any]:
	
	"""一个消息事件 → 可序列化的一行字典"""
	
	data	= event._data
	sender	= getattr(event, "sender", None)
	group_id = getattr(data, "group_id", None)
	
	return {
		"time"			: datetime.fromtimestamp(event.time).strftime("%Y-%m-%d %H:%M:%S"),
		"timestamp"		: event.time,
		"thread_id"		: thread_id_of(event),
		"type"			: "group" if event.is_group_msg() else "private",
		"group_id"		: str(group_id) if group_id is not None else None,
		"group_name"	: getattr(data, "group_name", None),
		"user_id"		: str(event.user_id),
		"nickname"		: getattr(sender, "nickname", None),
		"card"			: getattr(sender, "card", None),
		"message_id"	: str(event.message_id),
		"text"			: render_event(event),
	}


class CorpusWriter:
	
	"""把每条消息事件解析成一行 JSON 追加进语料文件"""
	
	def __init__(
		self,
		path		: Optional[Path]	= None,
		encoding	: str				= "utf-8",
		flush		: bool				= True,
	) -> None:
		
		self.path		= Path(path) if path else Path("corpus.jsonl")
		self.encoding	= encoding
		self.flush		= flush
		self._file		= None
	
	def open(self) -> None:
		
		"""打开文件 目录不存在就建"""
		
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self._file = self.path.open("a", encoding=self.encoding)
	
	def close(self) -> None:
		
		"""关掉文件 没开过就什么也不做"""
		
		if self._file is None:
			return None
		
		self._file.close()
		self._file = None
	
	def write(self, event: MessageEvent) -> Dict[str, Any]:
		
		"""写完返回落地的那条记录 方便调用方打日志"""
		
		record	= to_record(event)
		line	= json.dumps(record, ensure_ascii=False)
		
		self._file.write(line + "\n")
		
		if self.flush:
			self._file.flush()
		
		return record
