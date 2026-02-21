# apps/common/exceptions.py

class LedgerError(Exception):
    """Custom exception for ledger-related errors"""
    pass

class AuthenticationError(Exception):
    """Custom exception for authentication and token errors"""
    pass
