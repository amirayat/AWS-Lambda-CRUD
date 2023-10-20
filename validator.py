"""
This module contains validators for: 
    query parameters 
    and request body 
using pydantic
"""


import re
import ast

from typing import List, Tuple, Optional, Literal

from pydantic import (BaseModel as BM, constr,
                      ValidationError, PositiveInt,
                      NonNegativeInt, NonNegativeFloat,
                      model_validator, field_validator)

from .exceptions import BadRequestError


or_filter_regex = r'\|(.*?)\*'
and_filter_regex = r'&(.*?)\*'


def list_to_dict(lst: list) -> dict:
    """
    convert list filters to dict
    """
    dct = dict()
    try:
        for item in lst:
            key_value = item.split('=')
            _filter: str = key_value[0]
            _val: str = key_value[1]
            if _filter.endswith('__in') or \
                    _filter.endswith('__nin'):
                dct[_filter] = ast.literal_eval(_val)
            else:
                dct[_filter] = _val
        return dct
    except Exception as e:
        raise BadRequestError(error_message=e)


class BaseModel(BM, extra='forbid'):
    """
    pydantic base model
    """

    def __init__(self, *args, **kwargs):
        try:
            super().__init__(**kwargs)
        except ValidationError as err:
            error_message = list()
            for error in err.errors():
                msg = error['msg']
                loc = error.get('loc', [])
                error_message.append(
                    f"{','.join([str(i) for i in loc])} {msg}")
            error_message_str = ', '.join(error_message)
            print("Bad Request Error", "*"*5, error_message_str)
            raise BadRequestError(error_message=error_message_str)


class Product(BaseModel):
    """
    model for product
    """
    id: PositiveInt
    name: constr(strip_whitespace=True,
                 min_length=1,
                 regex=r"[a-zA-Z]")
    category_id: PositiveInt
    price: NonNegativeFloat


class Category(BaseModel):
    """
    model for category
    """
    id: PositiveInt
    name: constr(strip_whitespace=True,
                 min_length=1,
                 regex=r"[a-zA-Z]")
    description: constr(strip_whitespace=True,
                        min_length=1,
                        max_length=255,
                        regex=r"[a-zA-Z]",)


class Body(BaseModel):
    """
    model for request body
    """
    products: Optional[List[Product]] = list()
    categories: Optional[List[Category]] = list()

    @model_validator(mode='after')
    def check(self):
        if not self.products and not self.categories:
            raise ValueError(
                "At least one of 'products' or 'categories' is needed.")
        return self


class QueryParam(BaseModel):
    """
    model for request query params
    """
    filters: Optional[str] = None
    limit: Optional[PositiveInt] = 10
    offset: Optional[NonNegativeInt] = 0
    orderby: Optional[Literal[
        'id',
        'name',
        'category_id',
        'price',
    ]] = 'price'
    asc: Optional[bool] = False


class Filter(BaseModel):
    """
    model for query parameters filters
    """
    id__eq: Optional[PositiveInt] = None
    id__gt: Optional[PositiveInt] = None
    id__gte: Optional[PositiveInt] = None
    id__in: Optional[Tuple[PositiveInt, ...]] = None
    id__lt: Optional[PositiveInt] = None
    id__lte: Optional[PositiveInt] = None
    id__ne: Optional[PositiveInt] = None
    id__nin: Optional[Tuple[PositiveInt, ...]] = None

    name__eq: Optional[str] = None
    name__in: Optional[Tuple[str, ...]] = None
    name__like: Optional[str] = None
    name__ne: Optional[str] = None
    name__nin: Optional[Tuple[str, ...]] = None

    category_id__eq: Optional[PositiveInt] = None
    category_id__gt: Optional[PositiveInt] = None
    category_id__gte: Optional[PositiveInt] = None
    category_id__in: Optional[Tuple[PositiveInt, ...]] = None
    category_id__lt: Optional[PositiveInt] = None
    category_id__lte: Optional[PositiveInt] = None
    category_id__ne: Optional[PositiveInt] = None
    category_id__nin: Optional[Tuple[PositiveInt, ...]] = None

    category_name__eq: Optional[str] = None
    category_name__in: Optional[Tuple[str, ...]] = None
    category_name__like: Optional[str] = None
    category_name__ne: Optional[str] = None
    category_name__nin: Optional[Tuple[str, ...]] = None

    price__eq: Optional[NonNegativeFloat] = None
    price__gt: Optional[NonNegativeFloat] = None
    price__gte: Optional[NonNegativeFloat] = None
    price__in: Optional[Tuple[NonNegativeFloat, ...]] = None
    price__lt: Optional[NonNegativeFloat] = None
    price__lte: Optional[NonNegativeFloat] = None
    price__ne: Optional[NonNegativeFloat] = None
    price__nin: Optional[Tuple[NonNegativeFloat, ...]] = None

    description__eq: Optional[str] = None
    description__in: Optional[Tuple[str, ...]] = None
    description__like: Optional[str] = None
    description__ne: Optional[str] = None
    description__nin: Optional[Tuple[str, ...]] = None

    @field_validator('name__like', 'category_name__like', 'description__like')
    @classmethod
    def change_like(cls, v: str) -> str:
        return f'%{v}%'


def validate_query_params(query_params: dict) -> dict:
    """
    to validate query params
    """
    query_params: dict = QueryParam(
        **query_params).model_dump(exclude_none=True)
    filters = query_params.get('filters', None)
    if filters:
        try:
            _and_filters = re.findall(and_filter_regex, filters)
            _or_filters = re.findall(or_filter_regex, filters)
            and_filters: dict = Filter(
                **list_to_dict(_and_filters)).model_dump(exclude_none=True)
            and_filters = {
                'and__'+k: v for k, v in and_filters.items()
            }
            or_filters: dict = Filter(
                **list_to_dict(_or_filters)).model_dump(exclude_none=True)
            or_filters = {
                'or__'+k: v for k, v in or_filters.items()
            }
            query_params.pop('filters')
            query_params.update(and_filters)
            query_params.update(or_filters)
        except Exception as e:
            raise BadRequestError(
                error_message="Invalid Query Parameters!")
    return query_params
