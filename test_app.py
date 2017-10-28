import pytest                                                 # type: ignore
import botocore.session

from unittest import TestCase
from botocore.stub import ANY, Stubber
from app import prepare_email, send_email_ses


def test_prepare_email():
    """
    Test prepare email returns correct dictionary.
    """
    subject = "Send this subject value"
    body = "This is my email value."

    email = prepare_email(subject, body)

    assert email['Subject']['Data'] == subject
    assert email['Body']['Text']['Data'] == body


class AWSTests(TestCase):

    def setUp(self):
        self.ses_client = botocore.session.get_session().create_client('ses')
        self.stubber = Stubber(self.ses_client)
        self.ses_response = {'MessageId': 'Thisthevalueofmessage@example.com'}
        expected_params = {'Source': ANY,
                           'Destination': ANY,
                           'Message': ANY}
        self.stubber.add_response('send_email', self.ses_response,
                                  expected_params)

    def tearDown(self):
        self.stubber.deactivate()
        pass

    def test_send_email_ses(self):
        """
        Test send email sends out emails.
        """
        with self.stubber:
            response = send_email_ses(self.ses_client, 'test@example.com',
                                      "Please send this to test.",
                                      "This is the sample email body.\n")
        assert response == self.ses_response
