from nixsearch.log import get_logger, setup_logging


def test_get_logger():
    logger = get_logger("test")
    assert logger.name == "nixsearch.test"


def test_setup_logging():
    # Just verify it doesn't raise; it writes to the real log location
    setup_logging()
