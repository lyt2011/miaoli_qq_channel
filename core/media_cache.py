from pathlib	import Path
from typing		import Dict, Optional

import asyncio
import hashlib
import urllib.request


# url -> 本地路径 渲染消息时直接查这里
_CACHE: Dict[str, str] = {}

# 常见图片类型后缀 Content-Type 可能带参数 用前缀匹配
_CONTENT_TYPES = (
	("image/jpeg", ".jpg"),
	("image/jpg", ".jpg"),
	("image/png", ".png"),
	("image/gif", ".gif"),
	("image/webp", ".webp"),
	("image/bmp", ".bmp"),
)

_IMAGE_SUFFIXES = frozenset((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))


def cached_path(url: str) -> Optional[str]:
	
	"""这个 URL 有没有已经缓存到本地 没有返回 None"""
	
	return _CACHE.get(url) if url else None


def register(url: str, path: str) -> None:
	
	"""登记 URL 与本地文件的对应关系"""
	
	if url and path:
		_CACHE[url] = path


def clear_registry() -> None:
	
	"""清空登记表 测试用"""
	
	_CACHE.clear()


class MediaCache:
	
	"""入站媒体缓存 消息一到就把图片拉下来 免得模型拿到手时链接已经过期"""
	
	def __init__(
		self,
		root			: Path,
		max_megabytes	: int = 20,
		max_files		: int = 500,
		timeout_seconds	: float = 10.0,
		fetcher			= None,
	) -> None:
		self.root			= Path(root)
		self.max_bytes		= max_megabytes * 1024 * 1024
		self.max_files		= max_files
		self.timeout		= timeout_seconds
		self.fetcher		= fetcher or self._fetch
		self.pending		: Dict[str, "asyncio.Task"] = {}
	
	def path_for(self, url: str) -> Optional[str]:
		
		"""已缓存且文件还在就返回路径"""
		
		path = cached_path(url)
		if path and Path(path).is_file():
			return path
		
		return None
	
	async def cache(self, url: str, name: str = "") -> Optional[str]:
		
		"""下载并登记 同一个 URL 并发只下一次 失败返回 None"""
		
		if not url:
			return None
		
		if (path := self.path_for(url)) is not None:
			return path
		
		task = self.pending.get(url)
		if task is None:
			task = asyncio.create_task(self._download(url, name))
			self.pending[url] = task
			task.add_done_callback(lambda _: self.pending.pop(url, None))
		
		return await task
	
	async def _download(self, url: str, name: str) -> Optional[str]:
		
		try:
			data, content_type = await self.fetcher(url)
		except Exception:
			return None
		
		if not data or len(data) > self.max_bytes:
			return None
		
		self.root.mkdir(parents=True, exist_ok=True)
		digest	= hashlib.sha1(url.encode("utf-8")).hexdigest()
		path	= self.root / f"{digest}{self._suffix(name, content_type)}"
	
		await asyncio.to_thread(path.write_bytes, data)
		register(url, str(path))
		self.prune()
		
		return str(path)
	
	def _suffix(self, name: str, content_type: str) -> str:
		
		"""后缀优先看 Content-Type 其次看原文件名 都不认识就 .img"""
		
		content_type = (content_type or "").lower()
		for prefix, suffix in _CONTENT_TYPES:
			if content_type.startswith(prefix):
				return suffix
		
		if name:
			suffix = Path(name).suffix.lower()
			if suffix in _IMAGE_SUFFIXES:
				return suffix
		
		return ".img"
	
	async def _fetch(self, url: str) -> tuple:
		
		"""默认的下载实现 用标准库在线程里跑 不引额外依赖"""
		
		def get() -> tuple:
			request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
			with urllib.request.urlopen(request, timeout=self.timeout) as response:
				return response.read(), response.headers.get("Content-Type", "")
		
		return await asyncio.to_thread(get)
	
	def prune(self) -> None:
		
		"""缓存目录只保留最近的 max_files 个文件"""
		
		if self.max_files <= 0:
			return
		
		files = sorted(self.root.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True)
		for path in files[self.max_files:]:
			try:
				path.unlink()
			except OSError:
				continue
			for url, cached in list(_CACHE.items()):
				if cached == str(path):
					_CACHE.pop(url, None)
