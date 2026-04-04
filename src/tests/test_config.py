from nixsearch.config import Config


def test_default_config():
    cfg = Config()
    assert cfg.half_page == 15
    assert cfg.log_format == "%(asctime)s %(levelname)s %(name)s: %(message)s"
    assert cfg.log_date_format == "%Y-%m-%d %H:%M:%S"
    assert cfg.max_description_length == 60
    assert cfg.required_commands == ["nix", "git"]
    assert cfg.channel == "nixpkgs"
    assert cfg.max_channels == 5
