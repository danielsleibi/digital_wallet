# Digital Wallet API

A double-entry ledger digital wallet service built with Django and Django Ninja.

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ installed
- PowerShell (Windows) or Bash (macOS/Linux)

### 2. Set Up Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install "pydantic[email]"
```

---

### 4. Run Database Migrations
Initialize your database schema:
```bash
python manage.py migrate
```

---

### 5. Create an Admin Account (Optional)
```bash
python manage.py createsuperuser
```

---

### 6. Run the Development Server
```bash
python manage.py runserver
```

The server will start at `http://127.0.0.1:8000/`.

---

## API Documentation & Endpoints

Once the server is running, you can explore and test the endpoints via interactive API documentation:

- **Swagger UI:** [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **Django Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

### Main Route Prefixes
- `/api/auth` – User registration, authentication, JWT token refresh
- `/api/wallets` – Wallet creation, balances, and queries
- `/api/transactions` – Ledger transactions, transfers, deposits, withdrawals

---

## Running Tests

Execute the test suite using Django's test runner:

```bash
# Run all tests
python manage.py test

# Run tests for a specific app
python manage.py test apps.wallets
python manage.py test apps.users
python manage.py test apps.ledger
```

---

## Project Structure

    | Layer            | Responsibility                |
    | ---------------- | ----------------------------- |
    | API Layer        | Receives requests             |
    | Service Layer    | Business rules (ledger logic) |
    | Repository Layer | Database operations           |
    | Models           | Schema definitions            |

## Folder Structure Example

    dwls/
    ├── manage.py
    ├── config/
    │ ├── **init**.py
    │ ├── asgi.py
    │ ├── wsgi.py
    │ ├── urls.py
    │ └── settings/
    │ ├── **init**.py
    │ ├── base.py
    │ ├── dev.py
    │ └── prod.py
    │
    ├── apps/
    │ ├── users/
    │ │ ├── api/
    │ │ │ ├── router.py
    │ │ │ └── schemas.py
    │ │ ├── domain/
    │ │ │ └── user.py
    │ │ ├── models.py
    │ │ └── services.py
    │ │
    │ ├── wallets/
    │ │ ├── api/
    │ │ │ ├── router.py
    │ │ │ └── schemas.py
    │ │ │
    │ │ ├── domain/
    │ │ │ ├── wallet.py
    │ │ │ ├── money.py
    │ │ │ └── currency.py
    │ │ │
    │ │ ├── services/
    │ │ │ ├── wallet_service.py
    │ │ │ └── balance_service.py
    │ │ │
    │ │ ├── models.py
    │ │ ├── repositories.py
    │ │ └── tests/
    │ │
    │ ├── ledger/
    │ │ ├── api/
    │ │ │ ├── router.py
    │ │ │ └── schemas.py
    │ │ │
    │ │ ├── domain/
    │ │ │ ├── transaction.py
    │ │ │ ├── posting.py
    │ │ │ └── invariants.py
    │ │ │
    │ │ ├── services/
    │ │ │ ├── transaction_service.py
    │ │ │ └── transfer_service.py
    │ │ │
    │ │ ├── models.py
    │ │ ├── repositories.py
    │ │ ├── selectors.py
    │ │ └── tests/
    │ │
    │ └── common/
    │ ├── domain/
    │ │ ├── base_entity.py
    │ │ ├── money.py
    │ │ └── exceptions.py
    │ │
    │ ├── db/
    │ │ └── atomic.py
    │ │
    │ ├── auth/
    │ │ └── jwt.py
    │ │
    │ └── utils/
    │ └── time.py
    │
    ├── requirements.txt
    └── README.md
