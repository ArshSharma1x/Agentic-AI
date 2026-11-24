from primes import is_prime

def test_standard_definition():
    assert not is_prime(1) and not is_prime(0) and is_prime(97) and not is_prime(91)
