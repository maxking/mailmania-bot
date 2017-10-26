# Mailmania Bot

This bot is meant to help with backporting merge requests to branches other than
'master'. It is built using server application framework [Chalice][3] hosted on
[AWS Lambda][1] and receives notifications using [Gitlab's Webhooks][2].


**Note** : This is a relative Alpha level software and is under active development. 
**Please use it at your own risk.**


## Setup

This bot is not specific to any project and (minus some bugs) can be run for any
project on Gitlab.com. In future, I am planning to add support for
non-Gitlab.com instances of Gitlab and Github too, but there is not ETA. If
you'd like to help, please feel free to send in a pull request.


If you are not familiar with Chalice, I recommend that you look through its
[documentation][4] to make sure you understand what are you doing. You need to
[setup AWS credentials][5] on your local machine to be able to deploy to AWS Lambda
using Chalice. 

Then, go ahead and clone this repo:

```bash
$ git clone https://github.com/maxking/mailmania-bot.git
```

Create a new configuration file at `mailmania-bot/.chalice/config.json`:

```json
{
  "version": "2.0",
		"app_name": "mailmania",
		"environment_variables": {"<project_name>_GL_TOKEN": "<secret-token>",
	                              "GITLAB_TOKEN": "<gitlab-access-token>",
								  "BACKPORT_DESTINATION": "<backport-branch>",
								  "ADMIN_EMAIL": "maxking@asynchronous.in"},
		"stages": {
				"dev": {
						"api_gateway_stage": "api"
				}
		}
}
```

The environment variables in above configuration are meant to pass credentials
to the Lambda Function as environment variables:

- `<project_name>_GL_TOKEN` : This is a secret token you set in Gitlab when
  creating the Webhook to make sure your bot doesn't serve random web requests
  from un-intended users. Please replace `<project_name>` with the name of your
  project without the namespace. So for https://gitlab.com/maxking/mailman you
  will set `MAILMAN_GL_TOKEN`.
  
- `GITLAB_TOKEN`: This is the [personal access token][6] for your Gitlab User
  which has enough permissions to create branches in the project that webhook in
  set for. Merge requests will be created by this user.
  
- `BACKPORT_DESTINATION`: For now, this bot can only backport to a single branch
  whose name is set as the value of this environment variable. Merge Requests
  with label "backport-candidate" only are processed by this bot.
  
- `ADMIN_EMAIL`: In case anything goes wrong, an email will be sent to this
  email address with error trace. Currently, this doesn't work properly.


## Process of creating Merge Request

This is the steps bot does to create a backported merge request:

1. Create a new branch with `BACKPORT_DESTINATION` branch as the reference.
2. Cherry-pick all the commits from the MR being backported.
3. Create a new MR from this new branch to the `BACKPORT_DESTINATION` branch.


## Contributing Guidelines

Contributions and questions are welcome. Please create a issue on the Github
project.


## License

This project is Licensed under Apache License 2.0. Please see the LICENSE file
for full license text.



[1]: https://aws.amazon.com/lambda/
[2]: https://docs.gitlab.com/ee/user/project/integrations/webhooks.html
[3]: https://github.com/aws/chalice
[4]: https://chalice.readthedocs.io/en/latest/index.html
[5]: https://github.com/aws/chalice#credentials
[6]: https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html
