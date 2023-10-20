"""
This module contains lambda function
"""

from actions import ActionMLSRF
import sys

sys.tracebacklimit = 0


def lambda_handler(event, context):
    query_params = event.get('queryParams', dict())
    body = event.get('body', dict())
    method = event.get('method')

    response = dict()

    if method == 'GET':
        result = ActionMLSRF.get(query_params)
        response['result'] = result
    elif method == 'POST':
        ActionMLSRF.post(body)
        response['result'] = "Data has been inserted successfully."
    elif method == 'PUT':
        ActionMLSRF.put(body)
        response['result'] = "Data has been updated successfully."
    elif method == 'DELETE':
        ActionMLSRF.delete(body)
        response['result'] = "Data has been removed successfully."

    response['is_success'] = True
    return response
