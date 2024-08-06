# IAM-Docker-Run

Run Docker containers within the context of an AWS IAM Role, and other development workflow helpers.

## Motivation

The goal is to run our application on our laptops in development in as similar environment as possible to the production environment when the application runs in ECS or EKS, which would run under the task IAM role with permissions specific to that task.

A shortcut sometimes taken by developers is to execute code locally with their personal IAM user which often has very high and broad privileges.  Worse, those long lived credentials sometimes find themselves checked into source control as part of a docker-compose.yml file, etc.  IAM-Docker-Run allows you to run your containers locally within the context of the IAM role you've created for your application.  The credentials themselves are temporary, they are stored in a file in your system's temp path, and never wind up in source control.

IAM-Docker-Run generates AWS temporary credentials and builds a lengthly `docker run` command line statement, echoing it as it executes it so you have transparency into the command it is running.

**This is a development workflow tool, not designed to run production containers.**

A related effort is [IAM-Starter](https://github.com/billtrust/iam-starter) which starts a local process (outside of Docker) in the context of an AWS IAM role.

## Installation

```shell
pip install iam-docker-run
```

## Basic Example Usage

Say you are developing a console application using AWS resources and are in your project's root directory and want to execute your application using your latest source code and the IAM role created for your project.

```shell
iam-docker-run \
    --image mycompany/myservice:latest \
    --role role-myservice-task
```

You can alternatively specify a local AWS profile, then the container will run with the credentials given by that role.  This profile would have to exist locally in your `~/.aws/config` file, which can be created with `aws configure --profile myprofile`.

```shell
iam-docker-run \
    --image mycompany/myservice:latest \
    --profile myprofile
```

Or you can specify a role and a profile.  In this case the profile provides the credentials necessary to assume the role.

```shell
iam-docker-run \
    --image mycompany/myservice:latest \
    --role role-myservice-task \
    --profile myprofile
```

## Arguments and More Examples

### Full argument list

For a full list of arguments, run `iam-docker-run -h`.

### Full Entrypoint

The Docker syntax for overriding an entrypoint with anything more than one word can seem couterintuitive.  With the Docker syntax, the entrypoint can only be the first command and all arguments to that are separated out on the cmd, so if you want to run `python myapp.py --myarg test123`, then `python` is your entrypoint and the rest go on your cmd, to produce a docker run statement like:

```shell
docker run --entrypoint python mycompany/myimage myapp.py --myarg test123
```

To make things easier, iam-docker-run provides the `--full-entrypoint` argument, so you can use it like this:

```shell
iam-docker-run \
    --image mycompany/myimage \
    --full-entrypoint "python myapp.py --myarg test123"
```

### Shell

If you want to debug something in the container, just add a `--shell` argument and it will override the entrypoint with `/bin/bash`.  If you wish to use an alternate shell, you can override this with the following enrivonment variable:

```shell
export IAM_DOCKER_RUN_SHELL_COMMAND="/bin/sh"
```

It is especially convenient to use this command to add to the end of any existing set of arguments.  It will override both the default ENTRYPOINT defined in the Dockerfile as well as the `--full-entrypoint` argument.

```shell
# for example, --shell will take precedence over --full-entrypoint
iam-docker-run \
    --image mycompany/myimage \
    --full-entrypoint "python myapp.py --myarg test123" \
    --shell # let me jump in real quick without modifying the rest of my args
```

### Custom environment variables file

If you have environment variables you want passed to Docker via `docker run --env-file`, with iam-docker-run you would use `--custom-env-file`.  The reason for this is that iam-docker-run is already using a file to pass into Docker with the environment variables for the AWS temporary credentials, so if you have environment variables to add to that, specify a `--custom-env-file` and that will be concatenated to the env file created by iam-docker-run.

Default behavior is to look for a file called `iam-docker-run.env`.  If this file is not found it is silently ignored.  This is helpful if you have an environment variable such as `AWS_ENV=dev` which you want loaded each time without specifying this argument.  Hopefully the rest of your variables are loaded into the environment from a remote configuration store such as AWS SSM Parameter Store.  If you need help with this see [ssm-starter](https://github.com/billtrust/ssm-starter).

### Custom environment arguments

Additionally you can pass environment variables by `-e` or `--envvar`, which is passthrough to the `docker -e` argument.  These are additive with the custom environment variables file.

### Foreground / background

As the main use case is a development workflow, by default the container runs in the foreground.  To run in the background, specify `--detached`, which maps to the `docker run -d` command.  To interact with the terminal, specify `--interactive`, which maps to `docker run -it`.

### Source code volume mount by arguments (developer workflow)

The `--host-source-path` and `--container-source-path` arguments are designed to make it easy to mount your source code into the container when using Docker in a developer workflow where you make changes in your IDE on your host computer and want that source code immediately inserted into the container.  The `--host-source-path` argument can be relative.  In prior versions of IAM-Docker-Run the source code mount was automatic and required the `--no-volume` argument to prevent mounting it.  This automatic mount behavior has been removed however these arguments will remain for backward compatibility.

```shell
iam-docker-run \
    --image mycompany/myservice \
    --role role-myservice-task \
    --host-source-path ./mysource \
    --container-source-path /myapp
```

### Additional volume mounts

You can mount additional volumes by `-v` or `--volume`, which is passthrough to the `docker -v` argument.  These are additive with the source code volume mount (if specified) and the docker in docker mount.

### Assigning additional capabilities

You can assign additional capabilities to a container by using `--cap-add`, which is passed through to the `docker --cap-add` argument.

### Overcoming SELinux with volume mounts

If you are running SELinux and experience permission denied issues when mounting volumes, specify the `--selinux` argument, which will alter the dockr run volume mount argument so that the volume is readable.

### Enable Docker in Docker

If you want to enable Docker in Docker, you can mount the Docker socket by adding the `--mount-docker` argument.  If you then install Docker in the container with the below script and use the Docker CLI from within the container.

```shell
# install the docker client
curl -fsSL get.docker.com -o get-docker.sh
sh get-docker.sh
```

### Adding a portmap

You can use `--portmap` or `-p`, which is a direct match to the `docker run -p` argument, for example:

```shell
iam-docker-run \
    --image mycompany/myservice \
    --role role-myservice-task \
    --portmap 30000:3000
```

The `--portmap 30000:3000` argument in this example would take a HTTP server listening in the container on port 3000 and maps it to port 30000 on your laptop.

Note that you can use multiple portmaps as follows:

```shell
iam-docker-run \
    --image mycompany/myservice \
    --role role-myservice-task \
    -p 4430:443 \
    -p 8080:80
```

### Region

If `--region` is provided that will take precidence, otherwise iam-docker-run will look for your region in AWS_REGION or AWS_DEFAULT_REGION environment variables.  If none are provided it will default to us-east-1.

## Container Name Tempfile

IAM-Docker-Run generates a random container name if the --name arg is not supplied.  If this container name is needed for anything downstream such as the code debugging inside the container feature of VSCode, the container name needs to be discoverable.  IAM-Docker-Run enables this by generating a file which contains the name of the container and writes it in a pre-determined location.

The location of this file follows the:
`/temp/<last directory name of pwd>/_container_name.txt`

You can override the first part of the prefix with the following environment variable:

```shell
export IAM_DOCKER_RUN_CONTAINER_NAME_PATH_PREFIX=/tmp/somewhere/else
```

Or you can disable this entirely by setting:

```shell
export IAM_DOCKER_RUN_DISABLE_CONTAINER_NAME_TEMPFILE=true
```

## Shortcut

An alternate way to invoke iam-docker-run on the command line is to use the alias `idr`.  Just less typing.

```shell
idr --image busybox --role myrole
```

## Example CI workflow

The second use case for iam-docker-run is for running tests from continuous integration.  

```shell
iam-docker-run \
    --image mycompany/myimage \
    --role role-myservice-task \
    --full-entrypoint "/bin/bash /tests/run-integration-test.sh" \
    --profile jenkins
```

## Verbose debugging

To turn on verbose output for debugging, set the `--verbose` argument.

## Temporary Credentials Expire Within 1 Hour

A goal of this project was to be as easy as possible for developers to use and to allow the greatest portability.  To that end, the temporary AWS credentials are generated just once before the container starts, rather than requiring a more complex setup where an additional container would run all the time and regenerate credentials.  When the temp credentials expire (the STS max of 1 hour), the application will start experiencing expired credential exceptions.  For this among other reasons is why you would not use this tool in any environment other than local development or in your build/CI/CD workflow where usage periods are short and the container can be restarted easily and often.

Note: While the STS temporary credentials maximum was recently raised to 12 hours, if you are already in the context of an IAM role which is then assuming another role, the limit in this case remains to be 1 hour.

## Testing

Run the automated script cli tests:

```shell
pip install --user nose scripttest
python setup.py install --user
export AWS_REGION=us-east-1
# set AWS_PROFILE to a valid profile name which can assume roles
export AWS_PROFILE=dev
nosetests -v --exe -w ./test
```

Testing the use case of a role being supplied without a profile, using the credentials in the environment, is difficult to test an a generic automated way.  For now, the following manual steps can test this condition.

```shell
# set ROLE_ARN_FOR_LOCAL_CREDS to a role which can list s3 buckets
export ROLE_ARN_FOR_LOCAL_CREDS=arn:aws:iam::123456789012:role/my-role
# set AWS_PROFILE to a valid profile name which can assume the ROLE_ARN
export AWS_PROFILE=dev
export ROLE_NAME_FOR_CONTAINER=role-ops-developers

aws sts assume-role \
    --role-arn $ROLE_ARN_FOR_LOCAL_CREDS \
    --role-session-name testing \
    --profile $AWS_PROFILE

# put credentials in the environment
export AWS_ACCESS_KEY_ID=fromabove
export AWS_SECRET_ACCESS_KEY=fromabove
export AWS_SESSION_TOKEN=fromabove

iam-docker-run \
    --role $ROLE_NAME_FOR_CONTAINER \
    --image mesosphere/aws-cli:latest --full-entrypoint "aws s3 ls"

# command should succeed with a listing of s3 buckets
```

## Publishing Updates to PyPi

For the maintainer - to publish an updated version of Iam-Docker-Run, increment the version number in iam_docker_run.py and run the following:

```shell
docker build -f ./Dockerfile.buildenv -t billtrust/iam-docker-run:build .
docker run --rm -it --entrypoint make billtrust/iam-docker-run:build publish
```

At the prompts, enter the username and password to the Billtrust pypi.org repo.

## License

MIT License

Copyright (c) 2018 Factor Systems Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
