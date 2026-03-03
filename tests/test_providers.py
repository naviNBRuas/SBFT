import pytest
import sys, os

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from sbft.sbft_providers import DummyProvider


def test_dummy_provider_returns_zero():
    provider = DummyProvider()
    addresses = ["addr1", "addr2", "addr3"]
    balances = provider.get_balances(addresses)
    assert isinstance(balances, dict)
    for addr in addresses:
        assert balances[addr] == 0
