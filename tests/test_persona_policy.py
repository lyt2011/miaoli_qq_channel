from pathlib	import Path

import importlib.util
import sys


ROOT = Path(__file__).parents[1] / "plugins/persona_ops"

# 让 models 里的相对导入能解析
sys.path.insert(0, str(ROOT.parent))


def load_module(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


text_utils = load_module("persona_text_under_test", ROOT / "utils/text.py")
matching = load_module("persona_matching_under_test", ROOT / "utils/matching.py")
decision = load_module("persona_decision_under_test", ROOT / "utils/decision.py")
hints = load_module("persona_hints_under_test", ROOT / "consts/hints.py")
import persona_ops.models.plugin_config	as config_mod


def test_restraint_covers_serious_scenarios():
	assert matching.is_serious("帮我看看这个报错")
	assert matching.is_serious("今天面试没过，有点难过")
	assert not matching.is_serious("抱抱")
	assert matching.match_kind("帮我看看这个报错", matching.KIND_ORDER) == "restraint"
	assert matching.match_kind("谢谢你，抱抱", matching.KIND_ORDER) == "restraint"
	assert matching.match_kind("帮我看看这个报错", ["tease"]) is None


def test_kind_matching_priority_and_filter():
	assert matching.match_kind("抱抱", matching.KIND_ORDER) == "affection"
	assert matching.match_kind("抱抱，杂鱼", matching.KIND_ORDER) == "affection"
	assert matching.match_kind("杂鱼，就这？", ["tease"]) == "tease"
	assert matching.match_kind("我好菜啊", matching.KIND_ORDER) == "self_deprecate"
	assert matching.match_kind("今天天气不错", matching.KIND_ORDER) is None
	assert matching.match_kind("杂鱼", ["affection"]) is None


def test_cooldown_blocks_repeated_injection():
	entry = {"at": 5}
	assert decision.in_cooldown(entry, 6, 3)
	assert decision.in_cooldown(entry, 8, 3)
	assert not decision.in_cooldown(entry, 9, 3)
	assert not decision.in_cooldown({"at": 0}, 1, 3)
	assert not decision.should_emit(None, entry, 6, 3, 1.0, 0.0)


def test_probability_gate():
	entry = {"at": 0}
	assert decision.should_emit("tease", entry, 1, 3, 0.5, 0.49)
	assert not decision.should_emit("tease", entry, 1, 3, 0.5, 0.5)
	assert decision.should_emit("tease", entry, 1, 3, 1.0, 0.999)
	assert not decision.should_emit("tease", entry, 1, 3, 0.0, 0.0)


def test_input_text_and_platform():
	assert text_utils.input_text("  抱抱  ").strip() == "抱抱"
	blocks = [{"type": "text", "text": "杂鱼"}, {"type": "image_url"}, {"type": "text", "text": "就这"}]
	assert text_utils.input_text(blocks) == "杂鱼\n就这"
	assert text_utils.input_text(None) == ""
	assert text_utils.is_qq("qq") and text_utils.is_qq("QQ")
	assert not text_utils.is_qq("telegram")


def test_hint_texts_stay_optional():
	for kind, hint in hints.HINTS.items():
		assert "如果气氛合适" in hint, kind
		assert any(word in hint for word in ("不必", "不用", "别")), kind
		assert "必须" not in hint and "一定要" not in hint, kind


def test_config_defaults_to_disabled():
	config = config_mod.PluginConfig()
	assert config.enable is False
	assert config.cooldown_turns == 3
	assert config.kinds == ["tease", "self_deprecate"]
	assert config_mod.PluginConfig.model_validate({"kinds": ["tease"]}).kinds == ["tease"]
	try:
		config_mod.PluginConfig.model_validate({"kinds": ["nope"]})
	except ValueError:
		pass
	else:
		raise AssertionError("未知类别应当报错")
	assert config_mod.PluginConfig.model_validate({}).enable is False
