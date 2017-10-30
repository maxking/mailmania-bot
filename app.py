import os
import boto3
import gitlab
import logging
import traceback

from botocore.client import BaseClient
from typing import Any, Dict, Iterable, Text, Tuple
from chalice import Chalice, ForbiddenError, BadRequestError
from gitlab.v4.objects import (
    Project, ProjectBranch, ProjectMergeRequest, ProjectLabel)


app = Chalice(app_name='mailmania')
app.log.setLevel(logging.DEBUG)

BACKPORT_DESTINATION = os.getenv('BACKPORT_BRANCH', 'release-3.1')

gl = gitlab.Gitlab('https://gitlab.com',
                   os.getenv('GITLAB_TOKEN'), api_version=4)

ses = None


class BackportFailedError(Exception):
    pass


def prepare_email(subject: Text, body: Text) -> Dict['str', object]:
    email = {
        'Subject': {
            'Data': subject,
            'Charset': 'utf-8',
        },
        'Body': {
            'Text': {
                'Data': body,
                'Charset': 'utf-8'
            }
        }
    }
    return email


def prepare_destination(recipients: Iterable[Text]) -> Dict[Text, Iterable[Text]]:
    return {'ToAddresses': recipients}


def send_email_ses(
        ses_client: BaseClient, recipient: Text, subject: Text, body: Text) -> Dict[Text, Text]:
    """
    Send email to the recipient using Amazon SES service.
    """
    sender = os.getenv('DEFAULT_FROM_EMAIL')
    if sender is None:
        print("ERROR!!! DEFAULT_FROM_EMAIL is not configured")
        return None
    message = prepare_email(subject, body)
    return ses_client.send_email(Source=sender,
                                 Destination=prepare_destination([recipient, ]),
                                 Message=message)


def get_ses_client():
    """Initialize the gloabl ses client and return.

    This is used to lazily initialize the ses client only when it is needed.
    """
    global ses
    if ses is None:
        ses = boto3.client('ses', region_name='us-west-2')
    return ses


def send_email(*args, **kwargs):
    # Dynamic code due to *args, **kwargs, mypy can't really check types here.
    try:
        client = get_ses_client()
        send_email_ses(ses_client=client, *args, **kwargs)
        return True
    except Exception as e:
        print(e)
        return False


def notify_admin(error_trace: Text) -> None:
    recipient = os.getenv('ADMIN_EMAIL')
    if recipient is None:
        print("ERROR!!!!!!!! ADMIN_EMAIL is not configured")
        print(error_trace)
        return
    subject = "There has been a error backporting a merge request"
    send_email(recipient=recipient, subject=subject, body=error_trace)


def create_new_branch(project: Project, mr_id: Text) -> ProjectBranch:
    """
    Create a new branch in the project mentioned above.
    """
    # Breaking the recursive calls.
    if len(mr_id) > 10:
        raise BadRequestError(
            "Merge request {} doesn't look right.".format(mr_id))
    new_backport_branch = 'backport-mr-{}'.format(mr_id)
    try:
        new_branch = project.branches.create({'branch': new_backport_branch,
                                              'ref': BACKPORT_DESTINATION, })
    except gitlab.exceptions.GitlabCreateError as e:
        if "already exists" in str(e):
            return create_new_branch(project, '0' + mr_id)
        else:
            print(e)
            print("Could not fork {0} from {1} for project {2}.".format(
                new_backport_branch, BACKPORT_DESTINATION, project.name))
            traceback.print_exc()
            raise BackportFailedError("Could not fork a new branch.")
    return new_branch


def do_backport(project: Project, mr_id: Text) -> ProjectMergeRequest:
    project = gl.projects.get(project)
    backport_br = project.branches.get(BACKPORT_DESTINATION)
    if backport_br is None:
        raise BackportFailedError(
            "Backport Failed: backport branch '{}' doesn'texist.".format(BACKPORT_DESTINATION)) # noqa
    new_branch = create_new_branch(project, str(mr_id))
    mr = project.mergerequests.get(mr_id)
    for commit in mr.commits():
        try:
            commit.cherry_pick(new_branch.name)
        except gitlab.exceptions.GitlabCherryPickError as e:
            raise BackportFailedError(
                "CherryPick failed with error {}".format(str(e)))
        new_mr_title = "Backport MR !{0}: {1}".format(mr_id, mr.title)
    return project.mergerequests.create({'source_branch': new_branch.name,
                                         'target_branch': BACKPORT_DESTINATION,
                                         'title': new_mr_title,
                                         'description': mr.description})


def has_label(labels: Iterable[ProjectLabel], label_name: Text = 'backport-candidate') -> bool:
    """
    Check if the label mentioned is in the list.
    """
    return label_name in [x['title'] for x in labels]


def is_backport_required(request_body: Dict[Any, Any]) -> Tuple[bool, Text]:
    if request_body['object_kind'] != 'merge_request':
        raise BadRequestError(
            'This bot only listens for Merge Request hooks',
            ' you provided {}'.format(request_body['object_kind']))

    target_branch = request_body['object_attributes']['target_branch']
    labels = request_body['labels']
    state = request_body['object_attributes']['state']

    if (target_branch.lower() == 'master' and has_label(labels) and state.lower() == 'merged'):  # noqa
            return True, None
    reason = "target_branch = {0}, labels = {1}, state = {2}".format(   # noqa
        target_branch, [x['title'] for x in labels], state)
    return False, reason


@app.route('/', methods=['POST'])
def index() -> Text:
    request_body = app.current_request.json_body
    project_with_ns = request_body['project']['path_with_namespace']
    project = project_with_ns.split('/')[1]
    token = os.getenv('{}_GL_TOKEN'.format(project.upper()))
    if token is None:
        return "Bad configuration, Gitlab Token not set."
    if app.current_request.headers.get('X-Gitlab-Token') != token:
        raise ForbiddenError('X-GL-TOKEN Token does not match')

    backport_req, reason = is_backport_required(request_body)
    if backport_req:
            print("This is a backport candidate, performing requested action.")
            try:
                do_backport(project_with_ns,
                            request_body['object_attributes']['iid'])
            except BackportFailedError as e:
                notify_admin(str(e))
            except Exception as e:
                print(e)
                traceback.print_exc()
    else:
        print("Not creating merge request because: " + reason)

    return "Request recieved for backport! Processing ..."
