"""插件注册表测试 —— entry points 发现 + 配置覆盖 + 加载。"""

from vega.plugins import discover_plugins, load_plugin, load_plugin_config, reload_plugins


def test_discover_finds_builtin_novel():
    plugins = discover_plugins()
    assert "novel" in plugins


def test_load_plugin_returns_instance():
    p = load_plugin("novel")
    assert p.name == "novel"
    assert "character" in p.entity_types


def test_config_override_adds_plugin(tmp_path):
    # 配置里把 custom 名指向 novel 插件模块(模拟用户自定义插件)
    cfg = tmp_path / "vega.toml"
    cfg.write_text('[plugins]\ncustom = "vega.plugins.novel:NovelPlugin"\n', encoding="utf-8")
    plugins = discover_plugins(str(cfg))
    assert "custom" in plugins
    assert "novel" in plugins  # 内置仍在


def test_config_overrides_builtin(tmp_path):
    # 同名覆盖:config 的 novel 指向别处(此处仍指 novel,验证优先级机制)
    cfg = tmp_path / "vega.toml"
    cfg.write_text('[plugins]\nnovel = "vega.plugins.novel:NovelPlugin"\n', encoding="utf-8")
    plugins = discover_plugins(str(cfg))
    assert plugins["novel"] == "vega.plugins.novel:NovelPlugin"


def test_load_unknown_raises():
    try:
        load_plugin("不存在的领域")
        raise AssertionError("应抛 ValueError")
    except ValueError:
        pass


def test_reload_clears_cache():
    load_plugin("novel")
    reload_plugins()
    # 无异常即过(reload 后可重新 load)
    p = load_plugin("novel")
    assert p.name == "novel"


def test_load_plugin_config_missing_file():
    assert load_plugin_config("/no/such/vega.toml") == {}
