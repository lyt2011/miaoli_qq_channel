from ncatbot.types.qq.segment		import Face, Forward
from ncatbot.types.common.segment	import (
	At,
	File,
	Image,
	MessageSegment,
	PlainText,
	Record,
	Reply,
	Video,
)

from typing	import Any, Optional

from ..media_cache	import cached_path


# 常见富文本段里可能装正文的字段 取第一个非空的当预览
PREVIEW_FIELDS = ("title", "content", "text", "desc", "summary")


def _media(label: str, segment: Any) -> str:
	"""媒体段统一渲染成 [标签 文件名 大小](URL) 缺什么就省什么
	
	file 有时候装的是文件名 有时候直接就是 URL（Attachment 转出来的那种）
	所以显示名优先取 file_name 并且避免和链接重复
	"""
	
	link = segment.url or (segment.file if segment.file.startswith("http") else "")
	name = segment.file_name or segment.file
	
	pieces = [label]
	
	if name != link:
		pieces.append(name)
	
	if segment.file_size:
		pieces.append(str(segment.file_size))
	
	head = " ".join(pieces)
	
	if not link:
		return f"[{head}]"
	
	return f"[{head}]({link})"


def _preview(segment: MessageSegment) -> Optional[str]:
	"""未知段兜底 从几个常见字段里捞一句能看的 捞不到返回 None"""
	
	for field in PREVIEW_FIELDS:
		value = getattr(segment, field, None)
		if isinstance(value, str) and value.strip():
			return value.strip()[:60]
	
	return None


def render_segment(segment: MessageSegment) -> str:
	
	"""单个消息段 → 一行文本
	
	纯文本直接展开 别的段按类型加标签 认不出的段只留类型名 + 一句预览
	"""
	
	if isinstance(segment, PlainText):
		# 正文里的换行会破坏「一段一行」 换成可见符号
		return f"[文本] {segment.text.replace(chr(10), '⏎')}"
	
	if isinstance(segment, Face):
		return f"[表情 {segment.id}]"
	
	if isinstance(segment, At):
		return f"[@ {segment.user_id}]"
	
	if isinstance(segment, Reply):
		return f"[回复 {segment.id}]"
	
	if isinstance(segment, Image):
		# 入站时就下载好的图片 直接给本地路径 模型用 read_image 看 不用再去拉会过期的 URL
		path = cached_path(segment.url) if segment.url else None
		if path:
			name = segment.file_name or segment.file
			pieces = ["图片"]
			if name and name != path:
				pieces.append(name)
			pieces.append(f"已缓存:{path}")
			return f"[{' '.join(pieces)}]"
		return _media("图片", segment)
	
	if isinstance(segment, Record):
		return _media("语音", segment)
	
	if isinstance(segment, Video):
		return _media("视频", segment)
	
	if isinstance(segment, File):
		return _media("文件", segment)
	
	if isinstance(segment, Forward):
		count = len(segment.content) if segment.content else 0
		if count:
			return f"[转发 {segment.id} {count}条]"
		return f"[转发 {segment.id}]"
	
	preview = _preview(segment)
	if preview:
		return f"[{segment._type} {preview}]"
	
	return f"[{segment._type}]"
