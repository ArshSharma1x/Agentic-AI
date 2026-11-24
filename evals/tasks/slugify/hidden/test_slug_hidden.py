from slug import slugify

def test_accents_and_punctuation():
    assert slugify("Café Déjà Vu") == "cafe-deja-vu"
    assert slugify("  Hello,   World!! ") == "hello-world"
    assert slugify("C++ & Rust") == "c-rust"
