PLUGIN_CONFIG	= "miaoli_qq_channel/models.plugin_config"
RAW_CONFIG	= "miaoli_qq_channel/raw_config"
MESSAGE_BUFFER	= "miaoli_qq_channel/core.thread_backlog"
READY_BUFFER	= "miaoli_qq_channel/core.ready_buffer"

# 子插件 account_injector 的配置键
# 跨包不能在顶层 import，子插件是按包名注册进 sys.modules 的，加载期还没就位
# 值必须与 plugins/account_injector/consts/share_store_keys.py 保持一致
ACCOUNT_CONFIG	= "miaoli_qq_channel/subplugin/account_injector.models.plugin_config"
