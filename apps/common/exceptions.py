# apps/common/exceptions.py

class LedgerError(Exception):
    """Custom exception for ledger-related errors"""
    pass

class InsufficientFundsError(LedgerError):
    """Raised when wallet balance is lower than debit amount."""
    pass

class CurrencyMismatchError(LedgerError):
    """Raised when a transaction involves mismatched currencies."""
    pass

class TransactionReversalError(LedgerError):
    """Raised for errors specific to transaction reversal logic."""
    pass

class TransactionRefundError(LedgerError):
    """Raised for errors specific to transaction refund logic."""
    pass

class AuthenticationError(Exception):
    """Custom exception for authentication and token errors"""
    pass
