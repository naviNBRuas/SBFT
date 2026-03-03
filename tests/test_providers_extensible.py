import pytest
import sys, os

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from sbft.sbft_providers import ProviderBase


class TestProvider(ProviderBase):
    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "test"

    @property
    def base_url(self) -> str:
        return "http://test.local"

    def get_balances(self, addresses):
        # Simulate a provider that returns 1 for all addresses
        return {addr: 1 for addr in addresses}


def test_testprovider_returns_one():
    provider = TestProvider()
    addresses = ["addr1", "addr2"]
    balances = provider.get_balances(addresses)
    assert all(balances[addr] == 1 for addr in addresses)


def test_providerbase_not_implemented():
    base = ProviderBase()
    with pytest.raises(NotImplementedError):
        base.get_balances(["addr"])
