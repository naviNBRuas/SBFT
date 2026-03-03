import os
import sys
import pytest

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from sbft.main import validate_config, get_providers_from_config


def make_config(
    tmp_path,
    dest_addr="bc1qtestaddressxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    providers="blockcypher",
):
    config_path = tmp_path / "config.ini"
    with open(config_path, "w") as f:
        f.write(f"""[DEFAULT]
DESTINATION_ADDRESS = {dest_addr}
PROVIDERS = {providers}
""")
    return config_path


def test_validate_config_valid(monkeypatch, tmp_path):
    config_path = make_config(tmp_path)
    monkeypatch.setenv("CONFIG_FILE", str(config_path))
    # Should not raise
    validate_config()


@pytest.mark.parametrize("addr", [None, "", "abc", "12345"])
def test_validate_config_invalid(monkeypatch, tmp_path, addr):
    config_path = make_config(tmp_path, dest_addr=addr or "")
    monkeypatch.setenv("CONFIG_FILE", str(config_path))
    with pytest.raises(SystemExit):
        validate_config()


def test_get_providers_from_config(monkeypatch, tmp_path):
    config_path = make_config(tmp_path, providers="blockcypher,blockstream,dummy")
    monkeypatch.setenv("CONFIG_FILE", str(config_path))
    providers = get_providers_from_config()
    names = [p.name for p in providers]
    assert "blockcypher" in names
    assert "blockstream" in names
    assert "dummy" in names
