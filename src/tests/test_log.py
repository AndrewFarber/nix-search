from nixsearch.log import get_logger, setup_logging


def test_get_logger():
    logger = get_logger("test")
    assert logger.name == "nixsearch.test"


def test_setup_logging(tmp_path, monkeypatch):
    monkeypatch.setattr("nixsearch.log.config.data_dir", tmp_path)
    setup_logging()
    assert (tmp_path / "nix-search.log").exists()
