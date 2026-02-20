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
