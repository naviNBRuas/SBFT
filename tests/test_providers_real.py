import pytest
import sys, os

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from sbft.sbft_providers import BlockcypherProvider, DummyProvider


def test_blockcypher_provider_interface():
    provider = BlockcypherProvider()
    # Should not raise, but may return empty dict if no network
    result = provider.get_balances(["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"])
    assert isinstance(result, dict)


def test_dummy_provider_always_zero():
    provider = DummyProvider()
    addresses = ["addr1", "addr2"]
    balances = provider.get_balances(addresses)
    assert all(balances[addr] == 0 for addr in addresses)
