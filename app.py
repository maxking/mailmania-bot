import os
import gitlab
import logging
from chalice import Chalice, ForbiddenError, BadRequestError

app = Chalice(app_name='mailmania')
app.debug = True
app.log.setLevel(logging.DEBUG)
BACKPORT_DESTINATION = 'release-3.1'


@app.route('/project/{project}', methods=['POST'])
def index(project):
    request = app.current_request
    token = os.getenv('{}_GL_TOKEN'.format(project.upper()))
    if request.headers.get('X-GL-Token') != token:
        raise ForbiddenError('Gl Token does not match')
    request_body = request.json_body
    if request_body['object_kind'] != 'merge_request':
        raise BadRequestError(
            'This bot only listens for Merge Request hooks',
            ' you provided {}'.format(request_body['object_kind']))
    if request_body['project']['name'].lower() != project.lower():
        raise BadRequestError(
            'Bad project name, url is for {0} and data is {1}'.format(
                project, request_body['project']['name']))

    target_branch = request_body['object_attributes']['target_branch']
    labels = request_body['labels']
    state = request_body['object_attributes']['state']

    if (target_branch.lower() == 'master' and
        ('backport-candidate' in labels) and
        state.lower() == 'merged'):
            print("This is a backport candidate, performing requested action.")
            do_backport(request_body['project']['path_with_namespace'],
                        request_body['object_attributes']['iid'])
    else:
        return "Not creating merge request."


def do_backport(project, mr_id):
    gl = gitlab.Gitlab('https://gitlab.com', os.getenv('GL_TOKEN'),
                       api_version=4)
    project = gl.projects.get(project)
    backport_br = project.branches.get(BACKPORT_DESTINATION)
    if backport_br is None:
        raise BadRequestError("Backport branch doesn't exist!")
    new_backport_branch = 'backport-mr-{}'.format(mr_id)
    # TODO: handle branch exists error.
    new_branch = project.branches.create({'branch': new_backport_branch,
                                          'ref': BACKPORT_DESTINATION, })
    mr = project.mergerequests.get(mr_id)
    for commit in mr.commits():
        try:
            commit.cherry_pick(new_backport_branch)
        except gitlab.exceptions.GitlabCherryPickError:
            pass

    new_mr_title = "Backport MR !{0}: {1}".format(mr_id, mr.title)
    return project.mergerequests.create({'source_branch': new_backport_branch,
                                         'target_branch': BACKPORT_DESTINATION,
                                         'title': new_mr_title,
                                         'description': mr.description})
