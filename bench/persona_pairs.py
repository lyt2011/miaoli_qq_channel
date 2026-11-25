"""成对盲评：默认人格 vs 追加一条提示，哪条更像喵璃

每对把两条回复随机交换顺序再问裁判，避免位置偏好；只统计胜负平。

用法：
$ python3 bench/persona_pairs.py \
    --config /path/to/miaoli_bot/config.yaml --provider codeseed --samples 3
"""

import argparse
import importlib.util
import os
import pathlib
import random
import re

import yaml


REPO = pathlib.Path(__file__).parents[1]
PROBES = [
	("tease", "喵璃你是不是又变笨了，杂鱼？"),
	("affection", "抱抱，今天好累，陪我说会儿话"),
	("self_deprecate", "我好菜啊，一下午都没搞定这个"),
	("restraint", "帮我看看这个报错，我实在找不到原因"),
]


def load_bench():
	spec = importlib.util.spec_from_file_location("persona_bench", REPO / "bench/persona_compare.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


bench = load_bench()


def credentials(args) -> tuple[str, str, str]:
	base_url = os.environ.get("PERSONA_BENCH_BASE_URL", "")
	api_key = os.environ.get("PERSONA_BENCH_API_KEY", "")
	model = args.model

	if not base_url or not api_key:
		data = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8"))
		for provider in (data.get("llm") or {}).get("providers") or []:
			if provider.get("name") != args.provider:
				continue
			base_url = provider.get("base_url", "")
			api_key = provider.get("api_key", "")
			names = [
				item.get("name") if isinstance(item, dict) else item
				for item in (provider.get("models") or [])
			]
			model = model or (names[0] if names else "")
			break

	return base_url, api_key, model


def persona_brief() -> str:
	return bench.system_prompt()[:900]


def ask_judge(a: str, b: str, model: str, base_url: str, api_key: str) -> str:
	prompt = (
		"你在给一个 QQ 群角色做盲评。人设：\n"
		f"{persona_brief()}\n\n"
		"同一个人设，对同一句话的两种回复：\n"
		f"A: {a}\nB: {b}\n\n"
		"哪一条更像这个角色（语气、分寸、自称、称呼都要像）？"
		"只回答 A 或 B 或 平局，不要解释。"
	)
	answer = bench.chat([{"role": "user", "content": prompt}], model, base_url, api_key, 0.0)
	match = re.search(r"A|B|平局", answer, re.IGNORECASE)
	return match.group(0).upper() if match else "平局"


def run(args) -> None:
	base_url, api_key, model = credentials(args)
	system = bench.system_prompt()
	base = bench.build_history(args.turns, seed=args.seed)
	rng = random.Random(args.seed)

	print(f"provider={args.provider} model={model} samples={args.samples} 历史 {len(base)} 条")
	print()

	wins = {"intervened": 0, "baseline": 0, "平局": 0}

	for kind, message in PROBES:
		baseline = [{"role": "system", "content": system}, *bench.render(base, message, None)]
		intervened = [{"role": "system", "content": system}, *bench.render(base, message, bench.hints.HINTS[kind])]
		left = right = tie = 0

		for _ in range(args.samples):
			a = bench.chat(baseline, model, base_url, api_key, args.temperature)
			b = bench.chat(intervened, model, base_url, api_key, args.temperature)

			swapped = rng.random() < 0.5
			verdict = ask_judge(b if swapped else a, a if swapped else b, model, base_url, api_key)

			if verdict == "平局":
				tie += 1
			elif (verdict == "A") != swapped:
				left += 1
			else:
				right += 1

		wins["baseline"] += left
		wins["intervened"] += right
		wins["平局"] += tie
		print(f"{kind:14s} 默认胜 {left} / 干涉胜 {right} / 平 {tie}")

	print()
	print(f"总计：默认胜 {wins['baseline']} / 干涉胜 {wins['intervened']} / 平 {wins['平局']}")


def main() -> None:
	parser = argparse.ArgumentParser(description="成对盲评：默认人格 vs 追加一条提示")
	parser.add_argument("--config", default=None)
	parser.add_argument("--provider", default="codeseed")
	parser.add_argument("--model", default=None)
	parser.add_argument("--samples", type=int, default=3)
	parser.add_argument("--turns", type=int, default=400)
	parser.add_argument("--seed", type=int, default=0)
	parser.add_argument("--temperature", type=float, default=0.9)
	args = parser.parse_args()

	if not args.config:
		raise SystemExit("需要 --config 指向主包 config.yaml")

	run(args)


if __name__ == "__main__":
	main()
