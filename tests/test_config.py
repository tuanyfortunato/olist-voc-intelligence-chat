from src.config import Settings, get_settings


def test_defaults(monkeypatch):
    monkeypatch.delenv("TOP_K", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL_ID", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.aws_region == "us-east-1"
    assert settings.embedding_model_id == "cohere.embed-multilingual-v3"
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_batch_size == 96
    assert settings.index_workers == 2
    assert settings.top_k == 15
    assert settings.max_question_chars == 500
    assert settings.daily_question_limit == 300
    assert settings.db_port == 5432
    assert settings.db_sslmode == "require"


def test_env_overrides_and_types(monkeypatch):
    monkeypatch.setenv("TOP_K", "10")
    monkeypatch.setenv("MIN_SIMILARITY", "0.42")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.top_k == 10
    assert settings.min_similarity == 0.42
    assert isinstance(settings, Settings)


def test_settings_are_cached(monkeypatch):
    get_settings.cache_clear()
    assert get_settings() is get_settings()


def test_calibrated_defaults(monkeypatch):
    for name in ["MIN_SIMILARITY", "TOP_K", "USE_REWRITE", "MIN_COMMENT_CHARS"]:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.min_similarity == 0.58
    assert settings.top_k == 15
    assert settings.use_rewrite is True
    assert settings.min_comment_chars == 0


def test_boolean_from_environment(monkeypatch):
    for raw, expected in [("false", False), ("0", False), ("true", True), ("1", True)]:
        monkeypatch.setenv("USE_REWRITE", raw)
        get_settings.cache_clear()
        assert get_settings().use_rewrite is expected
