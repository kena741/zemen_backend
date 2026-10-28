from app.core.services.config_service import redact_secrets


def test_payment_settings_drop_secret_keys_but_keep_public_ones():
    data = {
        "chapa": {"enable": True, "publicKey": "pub", "secretKey": "s", "isSandbox": False},
        "stripe": {"secret_key": "s", "clientSecret": "s", "publishableKey": "pub"},
        "list": [{"privateKey": "s", "name": "x"}],
    }
    out = redact_secrets(data)
    assert out == {
        "chapa": {"enable": True, "publicKey": "pub", "isSandbox": False},
        "stripe": {"publishableKey": "pub"},
        "list": [{"name": "x"}],
    }
    assert data["chapa"]["secretKey"] == "s"
