from pathlib	import Path
from types		import ModuleType

import importlib.util
import sys


ROOT = Path(__file__).parents[1]


def load_module(name: str, path: Path) -> ModuleType:
	
	"""把一个不依赖同包相对导入的文件按独立模块加载（纯逻辑模块测试用）"""
	
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	
	return module


def load_package(name: str, files: dict) -> dict:
	
	"""按合成包加载一组互相有相对导入的模块
	
	files 的键是模块名 值相对插件根目录 按插入顺序加载（被依赖的先写）
	"""
	
	pkg = ModuleType(name)
	pkg.__path__ = [str(ROOT)]
	sys.modules[name] = pkg
	
	modules = {}
	for module_name, relative in files.items():
		path = ROOT / relative
		spec = importlib.util.spec_from_file_location(f"{name}.{module_name}", path)
		module = importlib.util.module_from_spec(spec)
		sys.modules[spec.name] = module
		spec.loader.exec_module(module)
		modules[module_name] = module
	
	return modules
