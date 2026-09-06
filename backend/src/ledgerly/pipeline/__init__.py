"""Normalization and enrichment. Pure functions where possible, so they are
testable without AWS and re-runnable over history (SPEC §15)."""

from ledgerly.pipeline.accounts import normalize_accounts
from ledgerly.pipeline.transactions import classify, normalize_batch, normalize_transaction
from ledgerly.pipeline.detect import detect_and_persist
from ledgerly.pipeline.transfers import find_transfers, score_pair

__all__ = [
    "classify", "detect_and_persist", "find_transfers", "normalize_accounts", "normalize_batch",
    "normalize_transaction", "score_pair",
]
