"""配置加载测试 —— vega.toml + 环境变量 + per-role 覆盖。"""


from vega.core.config import LlmConfig, VegaConfig, load_config, role_llm_config


def test_load_config_no_file_uses_env():
    """无配置文件 → 从环境变量构造默认。"""
    cfg = load_config("/no/such/vega.toml")
    assert cfg.llm.provider in ("deepseek", "ollama")
    assert cfg.embedding.model == "bge-m3"


def test_load_config_from_toml(tmp_path):
    cfg_file = tmp_path / "vega.toml"
    cfg_file.write_text(
        '[llm]\nprovider = "openai"\nmodel = "gpt-4o"\napi_key = "sk-test"\n'
        'base_url = "https://api.openai.com"\n'
        '[llm.roles]\nquery = { model = "gpt-4o-mini" }\n'
        '[embedding]\nmodel = "text-embedding-3-small"\ndim = 1536\n',
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_file))
    assert cfg.llm.provider == "openai"
    assert cfg.llm.model == "gpt-4o"
    assert cfg.llm.api_key == "sk-test"
    assert cfg.llm.roles["query"]["model"] == "gpt-4o-mini"
    assert cfg.embedding.model == "text-embedding-3-small"
    assert cfg.embedding.dim == 1536


def test_env_var_reference_in_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "sk-from-env")
    cfg_file = tmp_path / "vega.toml"
    cfg_file.write_text('[llm]\napi_key = "${MY_API_KEY}"\n', encoding="utf-8")
    cfg = load_config(str(cfg_file))
    assert cfg.llm.api_key == "sk-from-env"


def test_role_override_inherits_base(tmp_path):
    cfg_file = tmp_path / "vega.toml"
    cfg_file.write_text(
        '[llm]\nprovider = "deepseek"\nmodel = "deepseek-chat"\napi_key = "sk-x"\n'
        'base_url = "https://api.deepseek.com"\n'
        '[llm.roles]\nquery = { model = "qwen2.5:7b", provider = "ollama" }\n',
        encoding="utf-8",
    )
    cfg = load_config(str(cfg_file))
    # extract 继承 base
    p, m, k, b = role_llm_config(cfg, "extract")
    assert p == "deepseek" and m == "deepseek-chat" and k == "sk-x"
    # query 覆盖
    p, m, k, b = role_llm_config(cfg, "query")
    assert p == "ollama" and m == "qwen2.5:7b"
    # api_key 继承(未在 role 里覆盖)
    assert k == "sk-x"


def test_role_no_override_returns_base(tmp_path):
    cfg = VegaConfig(llm=LlmConfig(provider="ollama", model="qwen2.5:7b"))
    p, m, k, b = role_llm_config(cfg, "any_role")
    assert p == "ollama" and m == "qwen2.5:7b"
