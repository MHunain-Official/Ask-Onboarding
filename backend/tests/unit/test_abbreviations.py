from app.services.abbreviations import expand_abbreviations


def test_expands_emp_and_ack() -> None:
    assert "employee" in expand_abbreviations("new EMP handbook")
    assert "acknowledge" in expand_abbreviations("please ACK the policy")


def test_leaves_unknown_tokens() -> None:
    assert expand_abbreviations("xyzzy") == "xyzzy"
