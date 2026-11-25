"""
主动拟人干涉 vs 模型默认人格 在长上下文下的对比实验

离线模式（默认）：只统计注入行为、上下文占比与提示落点，不需要模型。
在线模式：给出两臂（默认人格 / 追加一条可选提示）的生成结果并对比表达指标。

离线：
$ python3 bench/persona_compare.py

在线（OpenAI 兼容接口，密钥只从环境变量读）：
$ PERSONA_BENCH_BASE_URL=https://api.deepseek.com/v1 \
PERSONA_BENCH_API_KEY=sk-... \
python3 bench/persona_compare.py --live --model deepseek-chat --samples 5
"""

import argparse
import importlib.util
import json
import os
import pathlib
import random
import re
import urllib.request


REPO = pathlib.Path(__file__).parents[1]
PLUGIN = REPO / "plugins/persona_ops"
SOUL = REPO.parents[0] / "miaoli_bot/plugins/miaoli_bot_adapter/data/SOUL.md"


def load(name, path):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


matching = load("bench_matching", PLUGIN / "utils/matching.py")
decision = load("bench_decision", PLUGIN / "utils/decision.py")
text_utils = load("bench_text", PLUGIN / "utils/text.py")
hints = load("bench_hints", PLUGIN / "consts/hints.py")


CASUAL = [
	"今天好热啊，空调开了半天一点都不凉",
	"在干嘛呢，我刚下班回来，路上堵得要死",
	"我回来了，今天公司那边事情特别多",
	"刚吃完饭，准备躺一会儿再收拾",
	"这也太离谱了，我刚看到那个新闻",
	"你们看这个视频了吗，笑死我了真的",
	"等下要出门买点东西，有人要带吗",
	"困死了，昨晚两点多才睡，今天整个人都是飘的",
	"周末有什么安排吗，我想出去玩两天",
	"刚打完一把游戏，队友实在是太坑了",
]
TEASE = [
	"杂鱼，就这？我还以为你多厉害呢",
	"笨蛋，你又把这个搞错了，再试一次吧",
	"敢不敢跟我比一把，输了的人请奶茶",
	"略略略，反正我不信你能做到",
	"哼，不理你了，谁让你刚才那么说",
]
AFFECTION = [
	"抱抱，今天有点累，想找人说说话",
	"想你了，好久没见你冒泡了",
	"宝，在吗，问你个事",
	"贴贴，今天过得好快啊",
]
SELF_DEPRECATE = [
	"我好菜啊，这个弄了一下午都没搞定",
	"我是不是很笨，感觉什么都做不好",
	"又搞砸了，明明准备了那么久",
	"我废了，这两天状态特别差",
]
SERIOUS = [
	"帮我看看这个报错吧，我实在找不到原因",
	"明天面试好紧张，有什么建议吗",
	"谢谢你昨天帮忙，真的帮了大忙",
	"怎么办，作业写不完了，还有两门没动",
]
REPLY = [
	"嗯嗯，我在的，你慢慢说",
	"哈哈哈，这也行，我是没想到",
	"是吧，我也这么觉得",
	"我看看，等我一下",
	"别急，先喝口水缓一缓",
	"在的在的，刚在忙别的",
	"确实，今天这个点人特别多",
]


def build_history(turns: int, seed: int = 0) -> list[dict]:
	
	"""造一段长会话：闲聊里掺少量调侃 / 亲昵 / 自嘲 / 正经求助"""
	
	rng = random.Random(seed)
	messages: list[dict] = []
	
	for index in range(turns):
		roll = rng.random()
		
		if roll < 0.60:
			user = rng.choice(CASUAL)
		elif roll < 0.75:
			user = rng.choice(TEASE)
		elif roll < 0.85:
			user = rng.choice(AFFECTION)
		elif roll < 0.93:
			user = rng.choice(SELF_DEPRECATE)
		else:
			user = rng.choice(SERIOUS)
		
		messages.append({"role": "user", "content": user})
		messages.append({"role": "assistant", "content": rng.choice(REPLY)})
	
	return messages


def replay(messages: list[dict], probability: float, cooldown: int, kinds: list[str], seed: int = 0) -> dict:
	
	"""按节点的判定顺序重放：匹配类别 → 冷却 → 概率"""
	
	rng = random.Random(seed)
	entry = {"at": 0}
	turn = 0
	matched = emitted = 0
	kinds_count: dict[str, int] = {}
	
	for message in messages:
		if message["role"] != "user":
			continue
		
		turn += 1
		text = message["content"]
		
		if len(text) < 2:
			continue
		
		kind = matching.match_kind(text, kinds)
		if kind is None:
			continue
		
		matched += 1
		
		if not decision.should_emit(kind, entry, turn, cooldown, probability, rng.random()):
			continue
		
		emitted += 1
		kinds_count[kind] = kinds_count.get(kind, 0) + 1
		entry["at"] = turn
	
	return {
		"turns": turn,
		"matched": matched,
		"emitted": emitted,
		"kinds": kinds_count,
	}


def system_prompt() -> str:
	
	"""优先读主包的人设文件，读不到就用一段占位人设"""
	
	if SOUL.is_file():
		return SOUL.read_text(encoding="utf-8")
	
	return "你是喵璃，一个在 QQ 群里和大家聊天的角色。"


def chars(messages: list[dict]) -> int:
	return sum(len(message["content"]) for message in messages)


def render(base: list[dict], probe: str, hint: str | None) -> list[dict]:
	
	"""默认人格臂 / 追加一条可选提示臂"""
	
	messages = list(base)
	messages.append({"role": "user", "content": probe})
	
	if hint is not None:
		messages.append({"role": "user", "content": f"<persona-hint>\n{hint}\n</persona-hint>"})
	
	return messages


PROBES = [
	("tease", "喵璃你是不是又变笨了，杂鱼？"),
	("affection", "抱抱，今天好累，陪我说会儿话"),
	("self_deprecate", "我好菜啊，一下午都没搞定这个"),
	("restraint", "帮我看看这个报错，我实在找不到原因"),
]


PARTICLES = ["啦", "呀", "嘛", "哼", "诶", "欸", "喔", "哦"]
PET = ["抱抱", "贴贴", "亲亲", "宝", "想你了"]


def metrics(text: str) -> dict:
	
	"""能离线算的表达指标"""
	
	return {
		"chars": len(text),
		"杂鱼": text.count("杂鱼"),
		"亲昵词": sum(text.count(item) for item in PET),
		"问句": text.count("?") + text.count("？"),
		"感叹": text.count("!") + text.count("！"),
		"语气词": sum(text.count(item) for item in PARTICLES),
	}


def chat(messages: list[dict], model: str, base_url: str, api_key: str, temperature: float) -> str:
	
	payload = json.dumps({
		"model": model,
		"messages": messages,
		"temperature": temperature,
	}).encode("utf-8")
	
	request = urllib.request.Request(
		base_url.rstrip("/") + "/chat/completions",
		data=payload,
		headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
	)
	
	with urllib.request.urlopen(request, timeout=120) as response:
		body = json.loads(response.read().decode("utf-8"))
	
	return body["choices"][0]["message"]["content"]


def judge(outputs: list[str], model: str, base_url: str, api_key: str) -> tuple[float, float]:
	
	"""让模型给两臂各打 1-5 分（自然度 / 亲密感），取均值"""
	
	normal = intimate = 0.0
	
	for output in outputs:
		prompt = (
			"给下面这段 QQ 群聊回复打分，只输出两个整数用逗号隔开：自然度,亲密感（各 1-5）。\n\n"
			+ output
		)
		answer = chat([{"role": "user", "content": prompt}], model, base_url, api_key, 0.0)
		numbers = [int(item) for item in re.findall(r"[1-5]", answer)][:2]
		
		if len(numbers) == 2:
			normal += numbers[0]
			intimate += numbers[1]
	
	count = max(len(outputs), 1)
	
	return normal / count, intimate / count


def offline(args) -> None:
	
	base = build_history(args.turns, seed=args.seed)
	stats = replay(base, args.probability, args.cooldown, args.kinds, seed=args.seed)
	prompt = system_prompt()
	
	context_chars = chars(base)
	probe = "喵璃你是不是又变笨了，杂鱼？"
	baseline = render(base, probe, None)
	intervened = render(base, probe, hints.HINTS["tease"])
	
	delta = chars(intervened) - chars(baseline)
	
	print("== 长上下文规模 ==")
	print(f"人设字符数        : {len(prompt)}")
	print(f"历史消息数        : {len(base)}（{stats['turns']} 轮）")
	print(f"历史字符数        : {context_chars}")
	print(f"粗略 token 估算   : {context_chars // 2}（按 1 token ≈ 2 汉字 粗估，仅看量级）")
	print()
	print("== 注入行为（重放同一段会话）==")
	print(f"命中场景          : {stats['matched']} / {stats['turns']} 轮（{stats['matched'] / max(stats['turns'], 1):.1%}）")
	print(f"实际注入          : {stats['emitted']} / {stats['turns']} 轮（{stats['emitted'] / max(stats['turns'], 1):.1%}）")
	print(f"类别分布          : {stats['kinds']}")
	print()
	print("== 单轮上下文增量 ==")
	print(f"提示字符数        : {len(hints.HINTS['tease'])}")
	print(f"上下文增量        : +{delta} 字符（相对历史 {delta / max(context_chars, 1):.3%}）")
	print("提示位置          : 生成点之前的最后一条 HumanMessage（人设在 messages[0]）")
	print()
	print("== 提示全文 ==")
	print(hints.HINTS["tease"])
	print()
	print("说明：离线部分只能量化「注入频率 / 上下文占比 / 落点」，"
		"人格输出差异要接真模型；加上 --live 即可跑两臂对比。")


def read_provider(config_path: str, provider_name: str, model_name: str) -> tuple[str, str, str]:
	
	"""从主包 config.yaml 里取某个 provider 的 base_url / api_key / 模型名"""
	
	import yaml
	
	data = yaml.safe_load(pathlib.Path(config_path).read_text(encoding="utf-8"))
	providers = (data.get("llm") or {}).get("providers") or []
	
	for provider in providers:
		if provider.get("name") != provider_name:
			continue
		
		models = [
			item.get("name") if isinstance(item, dict) else item
			for item in (provider.get("models") or [])
		]
		chosen = model_name or (models[0] if models else "")
		
		if not chosen:
			raise SystemExit(f"{provider_name} 没有可用模型")
		
		return provider.get("base_url", ""), provider.get("api_key", ""), chosen
	
	raise SystemExit(f"配置里没有 provider: {provider_name}")


def mean_metrics(outputs: list[str]) -> dict:
	
	"""一组输出的指标均值"""
	
	samples = [metrics(item) for item in outputs]
	
	return {key: sum(item[key] for item in samples) / len(samples) for key in samples[0]}


def print_arm(name: str, mean: dict, width: int = 10) -> None:
	
	print(f"{name:10s}: " + ", ".join(f"{key} {value:.2f}" for key, value in mean.items()))


def online(args) -> None:
	
	base_url = os.environ.get("PERSONA_BENCH_BASE_URL", "")
	api_key = os.environ.get("PERSONA_BENCH_API_KEY", "")
	model = args.model
	
	# 没有环境变量就读主包配置
	if (not base_url or not api_key) and args.config:
		base_url, api_key, model = read_provider(args.config, args.provider, args.model)
	
	if not base_url or not api_key:
		raise SystemExit("缺少 PERSONA_BENCH_BASE_URL / PERSONA_BENCH_API_KEY，或用 --config 指定主包 config.yaml")
	
	if not model:
		raise SystemExit("缺少 model：用 --model 指定，或让 provider 的默认模型生效")
	
	base = build_history(args.turns, seed=args.seed)
	system = system_prompt()
	scenarios = [item for item in PROBES if args.probe is None or item[0] == args.probe]
	
	if not scenarios:
		raise SystemExit("没有匹配的场景，--probe 取 tease / affection / self_deprecate / restraint")
	
	print(f"provider={args.provider or 'env'} base_url={base_url} model={model}")
	print(f"历史 {len(base)} 条 / {chars(base)} 字符，每场景采样 {args.samples} 次")
	print()
	
	all_outputs = {"baseline": [], "intervened": []}
	
	for kind, message in scenarios:
		
		arms = {
			"baseline": [{"role": "system", "content": system}, *render(base, message, None)],
			"intervened": [{"role": "system", "content": system}, *render(base, message, hints.HINTS[kind])],
		}
		outputs = {"baseline": [], "intervened": []}
		
		for index in range(args.samples):
			for name in ("baseline", "intervened"):
				outputs[name].append(chat(arms[name], model, base_url, api_key, args.temperature))
			print(f"  [{kind}] 采样 {index + 1}/{args.samples}")
		
		all_outputs["baseline"].extend(outputs["baseline"])
		all_outputs["intervened"].extend(outputs["intervened"])
		
		print(f"== 场景 {kind} ==")
		print_arm("baseline", mean_metrics(outputs["baseline"]))
		print_arm("intervened", mean_metrics(outputs["intervened"]))
		print(f"样例 baseline  : {outputs['baseline'][0]}")
		print(f"样例 intervened: {outputs['intervened'][0]}")
		print()
	
	print("== 全部场景汇总（均值）==")
	mean_baseline = mean_metrics(all_outputs["baseline"])
	mean_intervened = mean_metrics(all_outputs["intervened"])
	print_arm("baseline", mean_baseline)
	print_arm("intervened", mean_intervened)
	print()
	
	print("== 差值（干涉 - 默认）==")
	for key in mean_baseline:
		print(f"  {key:6s}: {mean_intervened[key] - mean_baseline[key]:+.2f}")
	
	if args.judge:
		print()
		print("== 模型打分（1-5 均值）==")
		for name in ("baseline", "intervened"):
			normal, intimate = judge(all_outputs[name], model, base_url, api_key)
			print(f"{name:10s}: 自然度 {normal:.2f} / 亲密感 {intimate:.2f}")


def main() -> None:
	
	parser = argparse.ArgumentParser(description="拟人干涉 vs 默认人格 长上下文对比")
	parser.add_argument("--turns", type=int, default=400, help="合成的历史轮数")
	parser.add_argument("--probability", type=float, default=0.6)
	parser.add_argument("--cooldown", type=int, default=3)
	parser.add_argument("--seed", type=int, default=0)
	parser.add_argument("--kinds", nargs="*", default=["restraint", "affection", "tease", "self_deprecate"])
	parser.add_argument("--probe", default=None, help="只跑某个场景：tease / affection / self_deprecate / restraint")
	parser.add_argument("--live", action="store_true", help="接真模型跑两臂对比")
	parser.add_argument("--config", default=None, help="从主包 config.yaml 读 provider（或改用环境变量）")
	parser.add_argument("--provider", default=None, help="config 里的 provider 名")
	parser.add_argument("--model", default=None)
	parser.add_argument("--samples", type=int, default=3)
	parser.add_argument("--temperature", type=float, default=0.9)
	parser.add_argument("--judge", action="store_true", help="再用模型打分（额外消耗）")
	
	args = parser.parse_args()
	
	if args.live:
		online(args)
	else:
		offline(args)


if __name__ == "__main__":
	main()
