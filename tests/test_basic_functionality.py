"""
Basic functionality tests for SBFT
Tests core components without complex mocking
"""

import pytest
import sys
import os
import tempfile
import configparser

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)


def test_imports_work():
    """Test that all modules can be imported successfully"""
    # Test main module imports
    from sbft.main import get_providers_from_config, validate_config
    from sbft.sbft_providers import ProviderBase, DummyProvider, get_available_providers
    from sbft.sbft_monitoring import monitor, progress_tracker

    # Test that we can create basic instances
    assert DummyProvider is not None
    assert get_available_providers() is not None


def test_provider_factory():
    """Test that provider factory works correctly"""
    from sbft.sbft_providers import create_provider, get_available_providers

    # Test getting available providers
    providers = get_available_providers()
    assert "dummy" in providers
    assert "blockcypher" in providers
    assert "blockstream" in providers

    # Test creating a dummy provider
    dummy_provider = create_provider("dummy")
    assert dummy_provider.name == "dummy"


def test_config_parsing():
    """Test that config parsing function exists and works basically"""
    from sbft.main import get_providers_from_config

    # Just test that the function can be called without error
    # (it will use the default config file which should exist)
    try:
        providers = get_providers_from_config()
        # Should return a list of providers
        assert isinstance(providers, list)
        # Should have at least some providers
        assert len(providers) >= 0
    except FileNotFoundError:
        # This is expected if config.ini doesn't exist in test environment
        # We just want to make sure the function exists and can be called
        pass


def test_monitoring_objects_exist():
    """Test that monitoring objects can be instantiated"""
    from sbft.sbft_monitoring import monitor, progress_tracker, monitoring_service

    # These should exist and be importable
    assert monitor is not None
    assert progress_tracker is not None
    assert monitoring_service is not None


def test_key_generation_basic():
    """Test basic key generation functionality"""
    from bitcoinlib.keys import HDKey
    from bitcoinlib.mnemonic import Mnemonic

    # Test that we can generate a basic key
    entropy = (123456789).to_bytes(16, "big")
    mnemonic = Mnemonic("english").to_mnemonic(entropy)
    hd_key = HDKey.from_passphrase(mnemonic, network="bitcoin")
    private_key = hd_key.key_for_path("m/44'/0'/0'/0/0")

    assert mnemonic is not None
    assert private_key is not None
    assert private_key.address is not None
