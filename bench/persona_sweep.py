"""上下文长度扫描：同一个探针在短 / 中 / 长上下文里各跑两臂

用法：
$ python3 bench/persona_sweep.py \
    --config /path/to/miaoli_bot/config.yaml --provider codeseed --samples 5

只看两件事：默认人格随上下文变长的漂移，以及追加一条可选提示后的偏移。
"""

import argparse
import importlib.util
import os
import pathlib
import re

import yaml


REPO = pathlib.Path(__file__).parents[1]
TURNS = [20, 400, 1500]
PROBE = ("tease", "喵璃你是不是又变笨了，杂鱼？")


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

	if not base_url or not api_key or not model:
		raise SystemExit("凭据或模型名没取到：检查 --config / --provider，或改用环境变量")

	return base_url, api_key, model


def kaomoji(text: str) -> int:
	return len(re.findall(r"[（(][^()（）]{1,10}[)）]", text))


def mean_of(outputs: list[str]) -> dict:
	samples = [bench.metrics(item) for item in outputs]
	mean = {key: sum(item[key] for item in samples) / len(samples) for key in samples[0]}
	mean["颜文字"] = sum(kaomoji(item) for item in outputs) / len(outputs)
	return mean


def run(args) -> None:
	base_url, api_key, model = credentials(args)
	system = bench.system_prompt()
	kind, message = PROBE
	keys = ("chars", "杂鱼", "颜文字", "问句", "语气词")

	print(f"provider={args.provider} model={model} samples={args.samples} probe={kind}")
	print(f"{'轮数':>5} {'字符':>6} | {'臂':<10} " + " ".join(f"{key:>5}" for key in keys))

	table = {}

	for turns in TURNS:
		base = bench.build_history(turns, seed=args.seed)
		arms = {
			"baseline": [{"role": "system", "content": system}, *bench.render(base, message, None)],
			"intervened": [{"role": "system", "content": system}, *bench.render(base, message, bench.hints.HINTS[kind])],
		}

		for name in ("baseline", "intervened"):
			outputs = [
				bench.chat(arms[name], model, base_url, api_key, args.temperature)
				for _ in range(args.samples)
			]
			mean = mean_of(outputs)
			table[(turns, name)] = mean
			print(f"{turns:>5} {bench.chars(base):>6} | {name:<10} " + " ".join(f"{mean[key]:>5.1f}" for key in keys))
		print()

	print("== 默认人格随上下文长度的漂移（baseline）==")
	for turns in TURNS:
		mean = table[(turns, "baseline")]
		print(f"{turns:>5} 轮: " + " ".join(f"{key} {mean[key]:.1f}" for key in keys))

	print()
	print("== 追加一条提示后的偏移（intervened - baseline）==")
	for turns in TURNS:
		left = table[(turns, "intervened")]
		right = table[(turns, "baseline")]
		print(f"{turns:>5} 轮: " + " ".join(f"{key} {left[key] - right[key]:+.2f}" for key in keys))


def main() -> None:
	parser = argparse.ArgumentParser(description="上下文长度扫描：默认人格漂移 vs 提示偏移")
	parser.add_argument("--config", default=None, help="主包 config.yaml")
	parser.add_argument("--provider", default="codeseed")
	parser.add_argument("--model", default=None)
	parser.add_argument("--samples", type=int, default=5)
	parser.add_argument("--seed", type=int, default=0)
	parser.add_argument("--temperature", type=float, default=0.9)
	args = parser.parse_args()

	if not args.config:
		raise SystemExit("需要 --config 指向主包 config.yaml（或用环境变量给凭据）")

	run(args)


if __name__ == "__main__":
	main()
