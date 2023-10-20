"""
This module contains error exceptions
to handle the right request status code 
in AWS API gateway template
"""

class InternalServerError(Exception):
    message = """
    We apologize for the inconvenience, 
    but it seems that our server encountered 
    an unexpected issue while processing your request. 
    Our technical team has been alerted 
    to this problem and is actively 
    working to resolve it as quickly as possible.
    """
    def __init__(self, *args, error_message=message, **kwargs):
        self.error_message = "Internal Server Error [500]: "+error_message
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.error_message
    

class BadRequestError(Exception):
    message = """
    We're sorry, but the request you submitted 
    to our server appears to be invalid or improperly 
    formatted. This could be due to a variety of 
    reasons, such as missing or incorrect parameters, 
    incompatible data formats, or other 
    issues with the request itself.
    """
    def __init__(self, *args, error_message=message, **kwargs):
        self.error_message = "Bad Request [400]: "+error_message
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.error_message


class NotAuthorizedError(Exception):
    message="""
    You don't have permission to access this resource.
    """
    def __init__(self, *args, error_message=message, **kwargs):
        self.error_message = "Not authorized [403]: "+error_message
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.error_message


class NotFoundError(Exception):
    message="""
    The resource you are looking for may have been moved, 
    deleted, or never existed in the first place.
    """
    def __init__(self, *args, error_message=message, **kwargs):
        self.error_message = "Not Found [404]: "+error_message
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.error_message
