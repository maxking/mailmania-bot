import os
import sys
import app
import pytest                                                 # type: ignore
import botocore.session

from io import StringIO
from unittest import TestCase, mock
from contextlib import contextmanager
from botocore.stub import ANY, Stubber
from botocore.client import BaseClient
from app import (prepare_email, send_email_ses, notify_admin,
    prepare_destination, get_ses_client, send_email, prepare_destination)


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def test_prepare_email():
    """
    Test prepare email returns correct dictionary.
    """
    subject = "Send this subject value"
    body = "This is my email value."

    email = prepare_email(subject, body)

    assert email['Subject']['Data'] == subject
    assert email['Body']['Text']['Data'] == body


def test_prepare_destination():
    # Test prepare_destination works as expected.
    destination = 'myself@example.com'
    dest = prepare_destination([destination, ])
    assert dest == {'ToAddresses': [destination, ]}


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

    def test_get_ses_client(self):
        # Test get_ses_client returns the global client object.
        original_client = app.ses
        assert original_client is None
        # Not when get_ses_client is invoked, the global ses client is
        # initialized and is same as the one returned by the method.
        new_client = get_ses_client()
        # The client should be an instance of BaseClient object.
        assert isinstance(new_client, BaseClient)
        # The global app.ses client should be now set to the value returned by
        # get_ses_client.
        assert app.ses is not None
        # The global value should be same as the one returned by get_ses_client.
        assert new_client is app.ses
        # If the global is already initialized, do not create another one.
        another_client = get_ses_client()
        assert another_client is new_client

    @mock.patch('app.ses')
    @mock.patch('app.send_email_ses')
    def test_send_email(self, mock_method, mock_client):
        # Test send_email invokes send_email_ses.
        args = ['value1', 'value2']
        kwargs = dict(key='value')

        val = send_email(*args, **kwargs)
        assert not mock_client.send_email.called
        assert mock_method.called
        mock_method.assert_called_with(*args, **kwargs, ses_client=mock_client)
        assert val is True

        # Test that send_email prints out error when an exception is raised.
        mock_method.reset_mock()
        # Raise an exception when this method is called.
        mock_method.side_effect = Exception('I am a super exception!')

        with captured_output() as (out, err):
            val = send_email(*args, **kwargs)
            assert val is False
            assert 'I am a super exception!' == out.getvalue().strip()
            assert not mock_client.send_email.called

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

        send_email_ses(mock_client, recipient, subject, body)

        mock_client.send_email.assert_called()
        mock_client.send_email.assert_called_with(
            Source=os.getenv('DEFAULT_FROM_EMAIL'),
            Destination=prepare_destination([recipient]),
            Message=prepare_email(subject, body))

    @mock.patch('app.ses')
    @mock.patch.dict(os.environ, {'DEFAULT_FROM_EMAIL': 'new@example.com'})
    def test_send_email_ses_new_sender(self, mock_client):
        # Test send_email_ses changes sender when environment variable
        # 'DEFAULT_FROM_EMAIL' is changed.
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

    @pytest.mark.xfail
    @mock.patch.dict(os.environ, {"ADMIN_EMAIL": 'hey@example.com',
                                  "ALERT_ADMIN": "No"})
    @mock.patch('app.ses')
    def test_notify_admin_silenced(self, mock_client):
        # If alert admin is set to "No", do not send out emails on errors and
        # failures.
        error_trace = 'Error traceback for emails'
        notify_admin(error_trace)
        assert not mock_client.send_email.called



class GitlabTests(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass


    def test_create_new_branch(self):
        # Test that new branch creation succeeds.
        pass

    def test_create_new_branch_when_exists(self):
        # Test graceful logging and exist if the backport branch exists.
        pass

    def test_create_new_branch_gitlab_error(self):
        # Test any other gitlab error when creating new branch.
        pass

    def test_do_backport(self):
        # Test that backport succeeds to a new branch.
        pass

    def test_do_backport_with_errors(self):
        # Test logging and graceful exit if the cherry_pick fails for one or
        # more commits.
        pass

    def test_backport_if_new_branch_creation_fails(self):
        # Test graceful exit if new branch creation fails.
        pass

    def test_has_label(self):
        # Test a simple list of labels.
        pass

    def test_has_label_with_no_matches(self):
        # Test if there are no matches.
        pass

    def test_label_with_multiple_matches(self):
        # Test if there are multiple matches.
        pass

    def test_is_backport_required_simple(self):
        # Test if the backport is required for this current request.
        pass

    def test_is_backport_required_non_master_destination(self):
        # Test if backport is required when the target branch for the merge
        # request is not 'master'.
        pass

    def test_is_backport_required_with_no_labels(self):
        # Test if backport is required when the target branch doesn't have the
        # required labels.
        pass

    def test_is_backport_required_non_merged_request(self):
        # Test if a backport is required when the merge request isn't merged.
        pass

    def test_is_backport_required_returns_correct_reasons(self):
        # If the backport is not going to succeed, test that the correct reasons
        # are returned.
        pass

    def test_index(self):
        # Test index processes request nicely.
        pass

    def test_index_correct_response_for_request(self):
        # Test the correct response is returned for the request.
        pass

    def test_index_backport_not_required(self):
        # Test index response if backport is not reuired.
        pass

    def test_index_backport_required(self):
        # Test index response if the backport is required.
        pass

    def test_index_logs_error_tracebacks(self):
        # Test that errors are logged when they happen for debugging purpose.
        pass

    def test_index_notifies_admin_when_backport_fails(self):
        # Test that admin is notified when the backport fails with a known
        # error.
        pass

    def test_index_with_no_gitlab_token(self):
        # Test error is logged and returned when the gitlab's token is not set.
        pass

    def test_index_when_gitlab_token_match_fails(self):
        # Test if the gitlab's token doesn't match as per the configured token.
        pass

    def test_index_with_get_requests(self):
        # Test a GET request to index.
        pass
