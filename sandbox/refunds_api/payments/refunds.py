from .store import PaymentStore, Refund


def refund(
    store: PaymentStore,
    user_id: str,
    payment_id: str,
    amount_cents: int,
    idempotency_key: str,
) -> Refund:
    """Refund part or all of a payment. See the refund policy (DOC-REFUND-POLICY)."""
    raise NotImplementedError
