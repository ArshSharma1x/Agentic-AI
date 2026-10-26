from dataclasses import dataclass


@dataclass
class Payment:
    id: str
    owner_id: str
    amount_cents: int
    refunded_cents: int = 0


@dataclass
class Refund:
    id: str
    payment_id: str
    amount_cents: int
    idempotency_key: str


class PaymentStore:
    """In-memory store standing in for the payments database."""

    def __init__(self) -> None:
        self._payments: dict[str, Payment] = {}
        self._refunds_by_key: dict[str, Refund] = {}

    def add_payment(self, payment: Payment) -> None:
        self._payments[payment.id] = payment

    def get_payment(self, payment_id: str) -> Payment:
        return self._payments[payment_id]

    def find_refund(self, idempotency_key: str) -> Refund | None:
        return self._refunds_by_key.get(idempotency_key)

    def save_refund(self, refund: Refund) -> None:
        self._refunds_by_key[refund.idempotency_key] = refund
