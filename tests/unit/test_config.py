from lexisub import config


def test_app_data_dir_is_absolute():
    assert config.APP_DATA_DIR.is_absolute()


def test_db_path_inside_app_data():
    assert config.DB_PATH.parent == config.APP_DATA_DIR


def test_models_dir_inside_app_data():
    assert config.MODELS_DIR.parent == config.APP_DATA_DIR


def test_model_ids_are_strings():
    assert isinstance(config.STT_MODEL_ID, str) and config.STT_MODEL_ID
    assert isinstance(config.LLM_MODEL_ID, str) and config.LLM_MODEL_ID


def test_chunk_size_reasonable():
    assert 10 <= config.TRANSLATION_CHUNK_LINES <= 50
