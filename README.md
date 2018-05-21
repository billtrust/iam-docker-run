# IAM-Docker-Run

Run Docker containers within the context of an AWS IAM Role, and other development workflow helpers.

## Motivation

The goal is to run our application on our laptops in development in as similar environment as possible to the production environment when the application runs in ECS or EKS, which would run under the task IAM role with permissions specific to that task.

A shortcut sometimes taken by developers is to execute code locally with their personal IAM user which often has very high and broad privileges.  Worse, those long lived credentials sometimes find themselves checked into source control as part of a docker-compose.yml file, etc.  IAM-Docker-Run allows you to run your containers locally within the context of the IAM role you've created for your application.  The credentials themselves are temporary, they are stored in a file in your system's temp path, and never wind up in source control.

IAM-Docker-Run generates AWS temporary credentials and builds a lengthly `docker run` command line statement, echoing it as it executes it so you have transparency into the command it is running.

**This is a development workflow tool, not designed to run production containers.**

## Installation

```shell
$ pip install iam-docker-run
```

## Basic Example Usage

Say you are developing a console application using AWS resources and are in your project's root directory and want to execute your application using your latest source code and the IAM role created for your project.

```shell
$ iam_docker_run \
    --image mycompany/myservice:latest \
    --aws-role-name role-myservice-task
```

There are lots of defaults at play here to keep command line usage succinct to support a convenient development workflow, which is the primary use case.  It is helpful to understand these defaults.  Most notably, it mounts a volume to insert the source code on your laptop into the container.  It assumes a project directory structure where your source code is located relative as `./src`, and that you want it mounted into the container to `/app`.  To disable this automatic volume mount, you must specify `--no-volume`.

## Specifying a local AWS profile

You will likely need to add a `--profile myprofile` argument to each of these examples.  This is the AWS profile used to assume the role, so it needs to have access to assume the role.  If absent, by default it will use the default AWS profile.  This profile would have been created with `aws configure`.  More likely you would have a named role which you would configure with `aws configure --profile myuser` and then add the `--profile myser` argument to each of your calls.

## Arguments and More Examples

### Full argument list

For a full list of arguments, run `iam-docker-run -h`.

### Overriding the volume mount

If your local source code path, or the path to mount it inside the container differs from the `./src` and `/app` defaults, you can override this in two different ways.

#### Overriding volume mount by environment variables

You can use system environment variables to override this which shortens your command and is convenient if you have the same directory structure throughout your projects.  You can override one or both of these.

Relative paths are okay.

```shell
$ export IAM_DOCKER_RUN_HOST_SOURCE_PATH="./mysource"
$ export IAM_DOCKER_RUN_CONTAINER_SOURCE_PATH="/myapp"
$ iam_docker_run \
    --image mycompany/myservice \
    --aws-role-name role-myservice-task
```

#### Overriding volume mount by arguments

An equivalent way using arguments is:

```shell
$ iam_docker_run \
    --image mycompany/myservice \
    --aws-role-name role-myservice-task \
    --host-source-path ./mysource \
    --container-source-path /myapp
```

#### Preventing any volume mount

If you want to prevent it from mounting a volume (if say you are using this from Jenkins, etc.) then you can add `--no-volume`.

### Adding a portmap

This is a direct match to the `docker run -p` argument, for example:

```shell
$ iam_docker_run \
    --image mycompany/myservice \
    --aws-role-name role-myservice-task \
    --portmap 30000:3000
```

The `--portmap 30000:3000` argument in this example would take a HTTP server listening in the container on port 3000 and maps it to port 30000 on your laptop.

### Shell

If you want to debug something in the container, just add a `--shell` argument and it will override the entrypoing with `/bin/bash`.  If you wish to use an alternate shell, you can override this with the following enrivonment variable:

```shell
$ export IAM_DOCKER_RUN_SHELL_COMMAND="/bin/sh"
```

### Full Entrypoint

The Docker syntax for overriding an entrypoint with anything more than one word can seem couterintuitive.  With the Docker syntax, the entrypoint can only be the first command and all arguments to that are separated out on the cmd, so if you want to run `python myapp.py --myarg test123`, then `python` is your entrypoint and the rest go on your cmd, to produce a docker run statement like:

```shell
$ docker run --entrypoint python mycompany/myimage myapp.py --myarg test123
```

To make things easier, iam-docker-run provides the `--full-entrypoint` argument, so you can use it like this:

```shell
$ iam-docker-run \
    --image mycompany/myimage \
    --full-entrypoint "python myapp.py --myarg test123"
```

### Custom environment variables file

If you have environment variables you want passed to Docker via `docker run --env-file`, with iam-docker-run you would use `--custom-env-file`.  The reason for this is that iam-docker-run is already using a file to pass into Docker with the environment variables for the AWS temporary credentials, so if you have environment variables to add to that, specify a `--custom-env-file` and that will be concatenated to the env file created by iam-docker-run.

Default behavior is to look for a file called `iam-docker-run.env`.  If this file is not found it is silently ignored.  This is helpful if you have an environment variable such as `AWS_ENV=dev` which you want loaded each time without specifying this argument.  Hopefully the rest of your variables are loaded into the environment from a remote configuration store such as AWS SSM Parameter Store.  If you need help with this see [ssm-starter](https://github.com/billtrust/ssm-starter).

### Foreground / background

As the main use case is a development workflow, by default the container runs in the foreground.  To run in the background, specify `--detached`, which maps to the `docker run -d` command.

### Region

If `--region` is provided that will take precidence, otherwise iam-docker-run will look for your region in AWS_REGION or AWS_DEFAULT_REGION environment variables.  If none are provided it will default to us-east-1.

### Container Name Tempfile

IAM-Docker-Run generates a random container name.  If this container name is needed for anything downstream such as the code debugging inside the container feature of VSCode, the container name needs to be discoverable.  IAM-Docker-Run enables this by generating a file which contains the name of the container and writes it in a pre-determined location.

The location of this file follows the:
`/temp/<last directory name of pwd>/_container_name.txt`

You can override the first part of the prefix with the following environment variable:

```shell
$ export IAM_DOCKER_RUN_CONTAINER_NAME_PATH_PREFIX=/tmp/somewhere/else
```

Or you can disable this entirely by setting:
```shell
$ export IAM_DOCKER_RUN_DISABLE_CONTAINER_NAME_TEMPFILE=true
```

### Shortcut

An alternate way to invoke iam-docker-run on the command line is to use the alias `idr`.  Just less typing.

```shell
$ idr --image busybox --aws-role-name myrole
```

## Example CI workflow

The second use case for iam-docker-run is for running tests from continuous integration.  

```shell
$ iam-docker-run \
    --image mycompany/myimage \
    --aws-role-name role-myservice-task \
    --full-entrypoint "/bin/bash /tests/run-integration-test.sh" \
    --no-volume \
    --profile jenkins
```

## Verbose debugging

To turn on verbose output for debugging, set the `--verbose` argument.

## Temporary Credentials Expire Within 1 Hour

A goal of this project was to be as easy as possible for developers to use and to allow the greatest portability.  To that end, the temporary AWS credentials are generated just once before the container starts, rather than requiring a more complex setup where an additional container would run all the time and regenerate credentials.  When the temp credentials expire (the STS max of 1 hour), the application will start experiencing expired credential exceptions.  For this among other reasons is why you would not use this tool in any environment other than local development or in your build/CI/CD workflow where usage periods are short and the container can be restarted easily and often.

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

