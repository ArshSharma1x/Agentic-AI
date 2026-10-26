import pytest

from payments.refunds import refund
from payments.store import Payment, PaymentStore


@pytest.fixture
def store() -> PaymentStore:
    s = PaymentStore()
    s.add_payment(Payment(id="p1", owner_id="alice", amount_cents=5000))
    return s


def test_full_refund(store):
    r = refund(store, "alice", "p1", 5000, "k1")
    assert r.amount_cents == 5000
    assert store.get_payment("p1").refunded_cents == 5000


def test_partial_refunds_accumulate_and_cap(store):
    refund(store, "alice", "p1", 2000, "k1")
    refund(store, "alice", "p1", 3000, "k2")
    with pytest.raises(ValueError):
        refund(store, "alice", "p1", 1, "k3")


def test_cannot_exceed_remaining_amount(store):
    with pytest.raises(ValueError):
        refund(store, "alice", "p1", 5001, "k1")


def test_idempotency_key_is_required(store):
    with pytest.raises(ValueError):
        refund(store, "alice", "p1", 100, "")


def test_same_key_returns_same_refund_without_moving_money_twice(store):
    first = refund(store, "alice", "p1", 1000, "k1")
    second = refund(store, "alice", "p1", 1000, "k1")
    assert second == first
    assert store.get_payment("p1").refunded_cents == 1000


@pytest.mark.parametrize("amount", [0, -5])
def test_amount_must_be_positive(store, amount):
    with pytest.raises(ValueError):
        refund(store, "alice", "p1", amount, "k1")


def test_unknown_payment_is_an_error(store):
    with pytest.raises(LookupError):
        refund(store, "alice", "nope", 100, "k1")
