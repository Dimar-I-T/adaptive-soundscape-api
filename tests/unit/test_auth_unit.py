from services.auth_service import hash_password, verify_password

def test_password_hashing():
    password = "secret_dimar_123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("not_secret_dimar_123", hashed) is False