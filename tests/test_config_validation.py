import configparser
import pytest
import sys, os

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from sbft.main import validate_config, get_providers_from_config
import sbft.main as main_module


def test_config_validation_good(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    with open(config_path, "w") as f:
        f.write("""[DEFAULT]
DESTINATION_ADDRESS = bc1qvalidaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
PROVIDERS = blockcypher
""")
    monkeypatch.chdir(tmp_path)
    # Patch config file location in sbft
    main_module.CONFIG_FILE = str(config_path)
    main_module.config.read(main_module.CONFIG_FILE)
    main_module.cfg = main_module.config["DEFAULT"]
    main_module.DESTINATION_ADDRESS = main_module.cfg.get("DESTINATION_ADDRESS", "")
    main_module.PROVIDERS = get_providers_from_config()
    validate_config()


def test_config_validation_bad(tmp_path, monkeypatch):
    config_path = tmp_path / "config.ini"
    with open(config_path, "w") as f:
        f.write("""[DEFAULT]
DESTINATION_ADDRESS = notvalid
PROVIDERS = blockcypher
""")
    monkeypatch.chdir(tmp_path)
    main_module.CONFIG_FILE = str(config_path)
    main_module.config.read(main_module.CONFIG_FILE)
    main_module.cfg = main_module.config["DEFAULT"]
    main_module.DESTINATION_ADDRESS = main_module.cfg.get("DESTINATION_ADDRESS", "")
    main_module.PROVIDERS = get_providers_from_config()
    with pytest.raises(SystemExit):
        validate_config()
