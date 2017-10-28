from app import prepare_email


def test_prepare_email():
    """
    Test prepare email returns correct dictionary.
    """
    subject = "Send this subject value"
    body = "This is my email value."

    email = prepare_email(subject, body)

    assert email['Subject']['Data'] == subject
    assert email['Body']['Text']['Data'] == body
