import pytest
from pydantic import ValidationError

from nixsearch.config import Config


def test_default_config():
    cfg = Config()
    assert cfg.half_page == 15
    assert cfg.max_description_length == 60


def test_positive_validation_half_page():
    with pytest.raises(ValidationError, match="positive integer"):
        Config(half_page=0)


def test_positive_validation_max_description_length():
    with pytest.raises(ValidationError, match="positive integer"):
        Config(max_description_length=-1)
