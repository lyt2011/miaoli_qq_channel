from typing	import Any, List, Optional, Union


def is_qq(platform: Any) -> bool:
	
	"""只处理 QQ 平台的消息"""
	
	return str(platform).lower() == "qq"


def input_text(content: Union[str, List[dict], None]) -> str:
	
	"""把 state["input"] 归一成文本：字符串原样保留，内容块列表只取 text 段"""
	
	if isinstance(content, str):
		return content.strip()
	
	if isinstance(content, list):
		parts = [
			part["text"] for part in content
			if isinstance(part, dict) and isinstance(part.get("text"), str)
		]
		return "\n".join(part for part in parts if part).strip()
	
	return ""
