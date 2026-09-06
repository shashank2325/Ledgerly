"""Normalization and enrichment. Pure functions where possible, so they are
testable without AWS and re-runnable over history (SPEC §15)."""

from ledgerly.pipeline.accounts import normalize_accounts

__all__ = ["normalize_accounts"]
