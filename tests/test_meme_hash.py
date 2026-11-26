from pathlib	import Path

import sys


sys.path.insert(0, str(Path(__file__).parent))

from loader	import load_module							# noqa: E402


modules				= load_module("meme_hashes_under_test", Path(__file__).parents[1] / "plugins" / "meme_ops" / "utils" / "hashes.py")
normalize_meme_hash	= modules.normalize_meme_hash


def test_normalize_pads_leading_zero():
	assert normalize_meme_hash("36f06eb157bf2bcaf0fbe9ad8737b55") == "036f06eb157bf2bcaf0fbe9ad8737b55"


def test_normalize_keeps_full_hash():
	assert normalize_meme_hash("036f06eb157bf2bcaf0fbe9ad8737b55") == "036f06eb157bf2bcaf0fbe9ad8737b55"


def test_normalize_lowercases():
	assert normalize_meme_hash("036F06EB157BF2BCAF0FBE9AD8737B55") == "036f06eb157bf2bcaf0fbe9ad8737b55"


def test_normalize_trims_extra_prefix():
	assert normalize_meme_hash("ab036f06eb157bf2bcaf0fbe9ad8737b55") == "036f06eb157bf2bcaf0fbe9ad8737b55"


def test_normalize_empty():
	assert normalize_meme_hash("") == "0" * 32
