class RoleNotFoundError(Exception):
    def __init__(self, credential_method, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        # a string describing the IAM context
        self.credential_method = credential_method


class AwsUtilError(Exception):
    pass
