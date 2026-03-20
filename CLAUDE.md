# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Setup and Database
```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py makemigrations
python manage.py migrate

# Create a superuser
python manage.py createsuperuser
```

### Running the Application
```bash
# Start development server
python manage.py runserver
# API will be available at http://localhost:8000/api/
```

### Running Tests
```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test apps.wallets
python manage.py test apps.users
python manage.py test apps.ledger

# Run a specific test module
python manage.py test apps.wallets.tests.test_wallet_service

# Run a specific test case
python manage.py test apps.wallets.tests.test_wallet_service.WalletServiceTests

# Run a specific test method
python manage.py test apps.wallets.tests.test_wallet_service.WalletServiceTests.test_create_wallet_success

# Test options
python manage.py test --failfast    # Stop on first failure
python manage.py test -v 2         # Verbose output
python manage.py test --keepdb     # Reuse test database
```

### API Documentation
Once the server is running, interactive API documentation is available at:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Architecture Overview

### Technology Stack
- **Django 6.0.1** with **Django Ninja** (REST API framework)
- **SQLite** (development), likely PostgreSQL for production
- **JWT authentication** with access/refresh tokens
- **Pydantic** for request/response validation
- Django test framework

### Project Structure

```
digital_wallet/
├── manage.py              # Django CLI entrypoint (uses config.settings.dev)
├── config/
│   ├── settings/
│   │   ├── base.py       # Base settings (DATABASES, INSTALLED_APPS, AUTH_USER_MODEL)
│   │   ├── dev.py       # Development overrides (DEBUG=True)
│   │   └── prod.py      # Production settings (if exists)
│   ├── urls.py          # Main URL routing - aggregates app routers under /api/
│   └── wsgi.py
├── apps/
│   ├── common/          # Shared utilities
│   │   ├── auth/
│   │   │   ├── bearer.py   # JWT token authentication for Django Ninja
│   │   │   └── jwt.py      # Token creation/validation utilities
│   │   ├── exceptions.py  # Custom exception hierarchy (LedgerError, InsufficientFundsError, etc.)
│   │   └── domain/        # Common domain models
│   ├── users/           # User management
│   │   ├── models.py       # Custom User model (extends AbstractUser, adds email, is_system)
│   │   ├── repository.py   # UserRepository (CRUD operations)
│   │   ├── services.py     # UserService (registration, auth, token refresh)
│   │   ├── domain/
│   │   │   └── user.py     # DomainUser dataclass for auth context
│   │   └── api/
│   │       ├── router.py   # Routes: /auth/register, /auth/login, /auth/refresh, /auth/me
│   │       └── schemas.py  # Pydantic schemas (RegisterIn, LoginIn, TokenOut, UserOut)
│   ├── wallets/         # Wallet management
│   │   ├── models.py       # Wallet model (UUID PK, user FK, currency, status)
│   │   ├── repository.py   # WalletRepository (wallet_exists, create_wallet, get_wallets_for_update)
│   │   ├── services/
│   │   │   └── wallet_service.py  # Business logic: create_wallet, get_wallet_balance, get_user_wallets
│   │   └── api/
│   │       ├── router.py   # Routes: /wallets/, /wallets/{id}/balance
│   │       └── schemas.py  # WalletCreateIn, WalletOut, BalanceOut
│   └── ledger/          # Transaction and balance tracking
│       ├── models.py       # Transaction and LedgerPosting models
│       │                       - Transaction: type (normal/reversal/refund), user, reversal_of FK
│       │                       - LedgerPosting: transaction FK, wallet FK, amount, direction (debit/credit), currency
│       ├── repository.py   # LedgerRepository (get_wallet_balance, create_transaction, create_postings)
│       ├── services/
│       │   ├── transaction_service.py    # core create_transaction with validation
│       │   └── compensation_service.py  # reverse_transaction, refund_transaction
│       ├── selectors.py   # (if exists) Query objects for complex lookups
│       └── api/
│           ├── router.py   # Routes: /transactions/transfer, /transactions/{id}/reverse, /transactions/{id}/refund
│           └── schemas.py  # TransferRequest, RefundRequest
```

### Layered Architecture

The codebase follows a strict layering pattern:

1. **API Layer** (`apps/*/api/`)
   - Django Ninja routers with endpoint functions
   - Pydantic schemas for request/response validation
   - JWT authentication via `JWTAuth` bearer class
   - Translates HTTP requests into service layer calls

2. **Service Layer** (`apps/*/services/`)
   - Contains business logic and invariants
   - Validates operations before delegating to repositories
   - Example: `create_transaction` validates debits=credits, currency consistency, sufficient funds

3. **Repository Layer** (`apps/*/repository.py`)
   - Pure data access operations (CRUD)
   - No business logic
   - Returns Django models or aggregates
   - Example: `WalletRepository.create_wallet()`, `LedgerRepository.get_wallet_balance()`

4. **Models** (`apps/*/models.py`)
   - Django ORM models with fields and constraints
   - `CheckConstraint` on LedgerPosting to prevent zero amounts
   - `Index` definitions for query performance
   - Never query models directly from API or service layers—always use repositories

### Key Domain Concepts

#### Wallets
- Each wallet has a currency (ISO-4217, 3 uppercase letters) and status (active/archived)
- Users can have multiple wallets with same currency? No—unique_together=(user, name, currency)
- System wallets exist (user.is_system=True) for fee collection, etc.
- Balance is computed from LedgerPosting records, NOT stored on Wallet model

#### Ledger (Double-Entry)
- All financial operations are transactions with postings
- Each transaction has 2+ postings that must balance (total debits = total credits)
- Posting direction: `debit` or `credit`
- Amount stored as signed Decimal on posting (negative for debits, positive for credits) in `LedgerRepository.create_postings()`
- Wallet balance = sum(posting.amount) across all postings for that wallet
- Atomic transactions enforced with `@transaction.atomic`

#### Transaction Types
- `normal`: Standard wallet-to-wallet transfer or deposit/withdrawal
- `reversal`: Complete cancellation of a normal transaction (mirrors all postings with opposite signs)
- `refund`: Partial refund of a normal transaction (creates new transaction with negative amount postings)

#### Authentication
- Custom User model with `email` (unique) and `is_system` flag
- JWT tokens contain user ID in `sub` claim and `type` (access/refresh)
- `JWTAuth` class populates `request.auth` with DomainUser (dataclass, not Django model)
- API endpoints use `auth=JWTAuth()` decorator

### Important Patterns

#### Repository Methods
- Use `select_for_update()` when acquiring row locks for concurrent operations
- System wallets (username='SYSTEM') are accessible for operations that need to bypass user ownership checks
- `get_wallets_for_update(wallet_ids, user)` returns wallets belonging to user OR system wallets—used in `create_transaction` to lock all involved wallets

#### Error Handling
- Custom exceptions in `apps/common/exceptions.py`:
  - `LedgerError`: Base exception for ledger ops
  - `InsufficientFundsError`: Balance too low for debit
  - `CurrencyMismatchError`: Cross-currency not allowed
  - `AuthenticationError`: JWT/user auth failures
- Services raise these; routers catch and return appropriate HTTP responses
- Never expose internal errors to clients; map to 400/404/401 as appropriate

#### Database Constraints
- LedgerPosting amount cannot be zero (`CheckConstraint`)
- Wallet unique_together prevents duplicate names per user per currency
- Use database transactions (`@transaction.atomic`) for all money-moving operations

#### Testing
- Tests use Django's test framework (unittest-style)
- Test files live alongside code in `tests/` subdirectories
- Set up test fixtures with `setUp()` or factory functions
- Database is automatically rolled back between tests
- Example test patterns: mock time, create users/wallets/transactions, assert balances

### Coding Conventions

#### Naming
- Models: PascalCase (Wallet, Transaction, LedgerPosting)
- Repository methods: snake_case (get_wallet_balance, create_wallet)
- Service functions: snake_case, often with `user` as first parameter after kwargs
- File names: snake_case.py

#### Imports
- Standard library first
- Django imports second
- Local app imports third
- Group by category with blank lines

#### Type Hints
- Use type hints on function signatures (especially service layer)
- Use `Decimal` for monetary amounts, not float
- Use `UUID` for model IDs

#### Django Ninja
- schemas inherit from `pydantic.BaseModel`
- Use `response` parameter to map return types: `@router.post("/", response={201: WalletOut})`
- Can return tuple: `return 201, wallet_instance` (status, data)
- Path params: `{wallet_id: UUID}` automatically converts to UUID

## Important Files to Know

- `config/urls.py`: API router aggregation
- `apps/common/auth/bearer.py`: JWT authentication implementation
- `apps/common/exceptions.py`: All custom exceptions
- `apps/ledger/services/transaction_service.py`: Core transaction logic (invariants, validation)
- `apps/ledger/services/compensation_service.py`: Reversal and refund logic
- `apps/wallets/repository.py`: Wallet data access including system wallet handling

## Known Issues and Gotchas

- SQLite is used for development; test against PostgreSQL compatibility if deploying to Postgres
- Currency codes are uppercase ISO-4217; validate with regex `^[A-Z]{3}$`
- Wallet balance is always computed, never stored—queries aggregate postings
- System wallets are identified by `user.username == 'SYSTEM'` (hardcoded in WalletRepository)
- JWT tokens have limited lifetime; refresh endpoint extends access
- `request.auth.id` in routers is a UUID (from DomainUser), NOT a Django User instance

## Git Workflow

- Main branch: `master`
- Feature branches: use descriptive names
- Commit messages: follow conventional commits if possible (feat:, fix:, refactor:)

## Environment

- Python 3.12+ (check exact version in .venv)
- Use the provided virtual environment at `.venv/`
- No Docker setup currently—local development only
