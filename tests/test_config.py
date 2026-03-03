import pytest
import sys, os

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from sbft.main import get_providers_from_config


def test_providers_config_default():
    """Test that default providers are loaded correctly"""
    providers = get_providers_from_config()
    names = [p.name for p in providers]
    # Should have at least blockcypher and blockstream by default
    assert len(names) >= 2
    assert "blockcypher" in names or "blockstream" in names


def test_providers_config_custom(tmp_path, monkeypatch):
    """Test custom provider configuration"""
    import configparser

    config_path = tmp_path / "config.ini"
    with open(config_path, "w") as f:
        f.write("""[DEFAULT]
PROVIDERS = dummy
DESTINATION_ADDRESS = bc1qtestxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
""")

    monkeypatch.chdir(tmp_path)

    # Import after changing directory
    import sbft.main as main_module

    main_module.CONFIG_FILE = str(config_path)
    main_module.config.read(main_module.CONFIG_FILE)
    main_module.cfg = main_module.config["DEFAULT"]

    providers = get_providers_from_config()
    names = [p.name for p in providers]
    assert "dummy" in names
    assert len(names) == 1  # Should only have dummy provider
