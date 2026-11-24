from primes import is_prime

def test_primes():
    assert is_prime(2) and is_prime(13)
    assert not is_prime(9)
    assert is_prime(1)
