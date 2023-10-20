"""
This module contains action class 
to route each request method to associated db query
"""

from validator import Body, validate_query_params
from db import RDB


class ActionMLSRF:
    """
    action class for request methods
    """
    @staticmethod
    def get(query_params) -> list:
        query_params = validate_query_params(query_params)
        with RDB() as rdb:
            result = rdb.select(query_params)
        return result

    @staticmethod
    def put(body) -> None:
        body = Body(**body).model_dump()
        with RDB() as rdb:
            rdb.update(body)

    @staticmethod
    def post(body) -> None:
        body = Body(**body).model_dump()
        with RDB() as rdb:
            rdb.insert(body)

    @staticmethod
    def delete(body) -> None:
        body = Body(**body).model_dump()
        with RDB() as rdb:
            rdb.delete(body)
