import os
import pytest                                                 # type: ignore
import botocore.session

from unittest import TestCase, mock
from botocore.stub import ANY, Stubber
from app import prepare_email, send_email_ses, notify_admin, prepare_destination


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
        self.ses_client = botocore.session.get_session().create_client(
            'ses', region_name='us-west-2')
        self.stubber = Stubber(self.ses_client)
        self.ses_response = {'MessageId': 'Thisthevalueofmessage@example.com'}
        expected_params = {'Source': ANY,
                           'Destination': ANY,
                           'Message': ANY}
        self.stubber.add_response('send_email', self.ses_response,
                                  expected_params)
        self.stubber.activate()

    def tearDown(self):
        self.stubber.deactivate()

    def test_send_email_ses(self):
        """
        Test send email sends out emails.
        """
        response = send_email_ses(self.ses_client, 'test@example.com',
                                  "Please send this to test.",
                                  "This is the sample email body.\n")
        assert response == self.ses_response

    @pytest.mark.xfail
    def test_send_email_ses_with_bad_email(self):
        # Test bad email address fails gracefully.
        response = send_email_ses(self.ses_client, 'notanemail',
                                  'Please send this to someone.',
                                  'This is the sample email body.\n')
        assert response != self.ses_response
        assert response is None

    @mock.patch('app.ses')
    def test_send_email_ses_uses_sender_env(self, mock_client):
        # setting DEFAULT_FROM_EMAIL env should use that as sender.
        recipient = 'notanemail'
        subject = 'Please send this to someone.'
        body = 'This is the sample email body.\n'

        response = send_email_ses(mock_client, recipient, subject, body)

        mock_client.send_email.assert_called()
        mock_client.send_email.assert_called_with(
            Source=os.getenv('DEFAULT_FROM_EMAIL'),
            Destination=prepare_destination([recipient]),
            Message=prepare_email(subject, body))

    @mock.patch('app.ses')
    @mock.patch.dict(os.environ, {'DEFAULT_FROM_EMAIL': 'new@example.com'})
    def test_send_email_ses_new_sender(self, mock_client):
        recipient = 'notanemail'
        subject = 'Please send this to someone.'
        body = 'This is the sample email body.\n'

        send_email_ses(mock_client, recipient, subject, body)

        mock_client.send_email.assert_called()
        mock_client.send_email.assert_called_with(
            Source=os.getenv('DEFAULT_FROM_EMAIL'),
            Destination=prepare_destination([recipient]),
            Message=prepare_email(subject, body))

    @mock.patch.dict(os.environ, {"ADMIN_EMAIL": "hey@example.com"})
    @mock.patch('app.ses')
    def test_notify_admin(self, mock_client):
        error_trace = 'Error Traceback for emails.'
        notify_admin(error_trace)
        mock_client.send_email.assert_called()
