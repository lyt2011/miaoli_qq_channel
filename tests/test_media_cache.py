from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module							# noqa: E402


modules = load_module("media_cache_under_test", Path(__file__).parents[1] / "core" / "media_cache.py")

MediaCache	= modules.MediaCache
cached_path	= modules.cached_path
clear_registry	= modules.clear_registry


def make_cache(tmp_path, payload=b"fake-image", content_type="image/png"):
	
	async def fetcher(url):
		return payload, content_type
	
	cache = MediaCache(root=tmp_path / "media", max_megabytes=1, fetcher=fetcher)
	
	return cache


def test_cache_saves_file_and_registers(tmp_path):
	clear_registry()
	cache = make_cache(tmp_path)
	
	path = __import__("asyncio").run(cache.cache("https://example.com/a.jpg", "a.jpg"))
	
	assert path is not None
	assert Path(path).is_file()
	assert Path(path).suffix == ".png"
	assert cached_path("https://example.com/a.jpg") == path


def test_cache_dedupes_same_url(tmp_path):
	clear_registry()
	calls = []
	
	async def fetcher(url):
		calls.append(url)
		return b"data", "image/jpeg"
	
	cache = MediaCache(root=tmp_path / "media", fetcher=fetcher)
	
	async def run():
		first	= await cache.cache("https://example.com/b.jpg")
		second	= await cache.cache("https://example.com/b.jpg")
		return first, second
	
	first, second = __import__("asyncio").run(run())
	
	assert first == second
	assert len(calls) == 1


def test_cache_ignores_oversized_payload(tmp_path):
	clear_registry()
	cache = make_cache(tmp_path, payload=b"x" * (2 * 1024 * 1024))
	cache.max_bytes = 1024
	
	assert __import__("asyncio").run(cache.cache("https://example.com/c.jpg")) is None
	assert cached_path("https://example.com/c.jpg") is None


def test_cache_returns_none_when_fetch_fails(tmp_path):
	clear_registry()
	
	async def fetcher(url):
		raise OSError("boom")
	
	cache = MediaCache(root=tmp_path / "media", fetcher=fetcher)
	
	assert __import__("asyncio").run(cache.cache("https://example.com/d.jpg")) is None


def test_prune_keeps_newest_files(tmp_path):
	clear_registry()
	cache = make_cache(tmp_path)
	cache.max_files = 2
	
	for index in range(4):
		cache.root.mkdir(parents=True, exist_ok=True)
		path = cache.root / f"{index}.png"
		path.write_bytes(b"x")
		path.touch()
	
	cache.prune()
	
	assert len(list(cache.root.glob("*"))) == 2


def test_suffix_falls_back_when_unknown(tmp_path):
	clear_registry()
	cache = make_cache(tmp_path, content_type="application/octet-stream")
	
	assert __import__("asyncio").run(cache.cache("https://example.com/e.bin", "e.bin")) is not None
