from pathlib	import Path

import importlib.util
import sys


ROOT = Path(__file__).parents[1] / "plugins/poke_ops"

# 让 models 里的相对导入能解析
sys.path.insert(0, str(ROOT.parent))


def load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


text_utils = load_module("poke_text_under_test", ROOT / "utils/text.py")
decision = load_module("poke_decision_under_test", ROOT / "utils/decision.py")
hints = load_module("poke_hints_under_test", ROOT / "consts/hints.py")
import poke_ops.models.plugin_config	as config_mod


def test_config_defaults():
	config = config_mod.PluginConfig()
	assert config.enable is False
	assert config.interval_minutes == 10


def test_interval_bounds():
	assert config_mod.PluginConfig(interval_minutes=1).interval_minutes == 1
	for bad in (0, 1441):
		try:
			config_mod.PluginConfig(interval_minutes=bad)
		except ValueError:
			continue
		raise AssertionError(f"interval_minutes={bad} 应该被拒绝")


def test_is_due():
	assert decision.is_due(0.0, 599.9, 10) is False
	assert decision.is_due(0.0, 600.0, 10) is True
	assert decision.is_due(100.0, 160.0, 1) is True
	assert decision.is_due(100.0, 159.9, 1) is False


def test_hints_are_suggestive():
	assert isinstance(hints.HINTS, tuple) and len(hints.HINTS) >= 1
	for hint in hints.HINTS:
		assert "如果气氛合适" in hint
		assert "不想" in hint
		assert "send_poke" in hint


def test_platform_and_text():
	assert text_utils.is_qq("qq")
	assert text_utils.is_qq("QQ")
	assert not text_utils.is_qq("discord")
	assert text_utils.input_text("  你好  ") == "你好"
	assert text_utils.input_text([{"type": "text", "text": "甲"}, {"type": "image_url"}]) == "甲"
	assert text_utils.input_text(None) == ""
	assert text_utils.input_text([{"type": "image_url"}]) == ""
