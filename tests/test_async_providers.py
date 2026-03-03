"""
Async provider functionality tests
"""

import pytest
import sys
import os
import asyncio

# Add src to path for proper imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)


@pytest.mark.asyncio
async def test_dummy_provider_async():
    """Test that dummy provider works asynchronously"""
    from sbft.sbft_providers import DummyProvider

    provider = DummyProvider()
    addresses = ["addr1", "addr2", "addr3"]

    # Test async balance checking
    balances = await provider.get_balances(addresses)

    assert isinstance(balances, dict)
    for addr in addresses:
        assert balances[addr] == 0


@pytest.mark.asyncio
async def test_provider_factory_async():
    """Test that provider factory creates working async providers"""
    from sbft.sbft_providers import create_provider

    # Test creating and using different providers
    providers_to_test = ["dummy"]

    for provider_name in providers_to_test:
        provider = create_provider(provider_name)
        addresses = ["test_addr"]

        # Should not raise exceptions
        balances = await provider.get_balances(addresses)
        assert isinstance(balances, dict)
