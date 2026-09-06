"""Plaid integration.

A thin first-party client over stdlib HTTP — see ADR 0006 for why we do not
vendor `plaid-python`.
"""

from ledgerly.plaid.client import PlaidClient, PlaidError

__all__ = ["PlaidClient", "PlaidError"]
