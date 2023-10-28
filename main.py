"""
This module contains lambda function
"""

from actions import Action
import sys

sys.tracebacklimit = 0


def lambda_handler(event, context):
    query_params = event.get('queryParams', dict())
    body = event.get('body', dict())
    method = event.get('method')

    response = dict()

    if method == 'GET':
        result = Action.get(query_params)
        response['result'] = result
    elif method == 'POST':
        Action.post(body)
        response['result'] = "Data has been inserted successfully."
    elif method == 'PUT':
        Action.put(body)
        response['result'] = "Data has been updated successfully."
    elif method == 'DELETE':
        Action.delete(body)
        response['result'] = "Data has been removed successfully."

    response['is_success'] = True
    return response
