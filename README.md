# Fintech Wallet Backend API

This project implements a secure, auditable wallet system similar to those used by modern fintech platforms (e.g. Opay, PalmPay).

## Features

- JWT authentication with role-based access
- One-wallet-per-user enforcement
- Dollar-based wallet using cent-level precision
- Idempotent deposits, withdrawals, and transfers
- Row-level locking to prevent race conditions
- Double-entry style transfers
- Full transaction ledger
- Admin audit & balance reconciliation

## Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- JWT (HS256)
- Argon2 password hashing

## Currency Handling (NGN)

All monetary values are stored in **kobo (₦ × 100)** to prevent floating-point errors.

Examples:

- ₦1.00 → 100 kobo
- ₦12,500.50 → 1,250,050 kobo

Frontend handles conversion to naira.

Example:

- $10.50 → 1050 cents

## Security Considerations

- Idempotency keys prevent duplicate transactions
- Wallet row locking prevents double-spend
- Auditing endpoints detect ledger mismatches

## Future Improvements

- Payment gateway integration
- KYC & AML
- Alembic migrations
- Webhook handling
