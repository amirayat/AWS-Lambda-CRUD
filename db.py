"""
This module contains RDS queries
"""

from psycopg2 import sql, connect
from psycopg2.extras import RealDictCursor

from aws_secretsmanager_caching import SecretCache, InjectKeywordedSecretString

from exceptions import InternalServerError, NotFoundError


def get_secret_cache():
    global cache
    if not cache:
        cache = SecretCache()
    return cache


def get_rds_credentials(secret_cache):
    @InjectKeywordedSecretString(
        secret_id="development/rds/postgresql",
        cache=secret_cache,
        db_name="dbname",
        db_pass="password",
        db_user="username",
        endpoint="host",
        port="port",
    )
    def get_credentials(db_name, db_pass, db_user, endpoint, port):
        return db_name, db_pass, db_user, endpoint, port

    return get_credentials()


class RDB:
    def __init__(self):
        rds_creds = get_rds_credentials(
            secret_cache=get_secret_cache())
        self.connection = connect(
            database=rds_creds[0],
            password=rds_creds[1],
            user=rds_creds[2],
            host=rds_creds[3],
            port=rds_creds[4],
        )
        self.cursor = self.connection.cursor(
            cursor_factory=RealDictCursor)
        self.and_filters = list()
        self.or_filters = list()
        self.filters = list()
        self.comparison_operators = {
            '__eq': ' = ',
            '__ne': ' != ',
            '__gt': ' > ',
            '__gte': ' >= ',
            '__lt': ' < ',
            '__lte': ' <= ',
            '__in': ' IN ',
            '__nin': ' NOT IN ',
            '__like': ' LIKE ',
        }

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        print("Query", "*"*5, self.cursor.query)
        if not self.connection.closed:
            self.connection.commit()
            self.connection.close()

    def do_roll_back(self):
        self.connection.rollback()
        self.connection.close()

    def operator(self, attribute: str) -> list:
        """
        generate condition based on attribute operator
        """
        opr = '__'+attribute.split('__')[-1]
        sql_comparison_operator = self.comparison_operators[opr]
        if 'tier__' in attribute:
            field = attribute.replace(
                "and__", "").replace(
                "or__", "").replace(
                "tier__", "").replace(
                opr, "")
            alias = 'related'
        else:
            field = attribute.replace(
                "and__", "").replace(
                "or__", "").replace(
                opr, "")
            alias = 'product'
        condition = sql.Composed([
            sql.Identifier(alias),
            sql.SQL('.'),
            sql.Identifier(field),
            sql.SQL(sql_comparison_operator),
            sql.Placeholder(attribute)
        ])
        return condition

    def filter_query(self, query_params: dict) -> list:
        """
        to fill and/or filters 
        """
        for k, v in query_params.items():
            if v:
                if k.startswith('and__'):
                    condition = self.operator(k)
                    self.and_filters.append(condition)
                elif k.startswith('or__'):
                    condition = self.operator(k)
                    self.or_filters.append(condition)

    def check_category_id_exists(self, products: list):
        """
        to check entered category ids in request body exists
        """
        category_ids = [product['category_id'] for product in products]
        sql_statement = sql.SQL(
            """
            SELECT {_id}
            FROM {categories}
            WHERE {_id} in %(category_ids)s;
            """
        ).format(
            _id=sql.Identifier('id'),
            categories=sql.Identifier('categories'),
        )
        sql_kwargs = {
            "category_ids": tuple(category_ids),
        }
        self.cursor.execute(sql_statement, sql_kwargs)
        result = self.cursor.fetchall()
        retrieved_group_ids = [dict(record)['id'] for record in result]
        diff = set(category_ids)-set(retrieved_group_ids)
        if diff:
            print("Error-Check Category ID Exists", "*"*5, diff)
            raise NotFoundError()

    def select(self, query_params: dict):
        """
        select query
        """
        self.filter_query(query_params)
        query = sql.SQL("""
        SELECT 
            {products}.{_id},
            {products}.{name},
            {products}.{category_id},
            {products}.{price},
            {categories}.{name} AS {category_name},
            {categories}.{description}
        FROM {products}
        LEFT JOIN {categories}
        ON 
        {products}.{category_id} = {categories}.{_id}""")

        if self.and_filters and self.or_filters:
            self.and_filters = sql.SQL(' AND ').join(self.and_filters)
            self.or_filters = sql.SQL(' OR ').join(self.or_filters)
            self.filters = sql.SQL(' OR ').join(
                [self.and_filters, self.or_filters])
        elif self.and_filters:
            self.filters = sql.SQL(' AND ').join(self.and_filters)
        elif self.or_filters:
            self.filters = sql.SQL(' OR ').join(self.or_filters)

        if self.filters:
            query = sql.Composed([query, sql.SQL(" WHERE {filters}")])

        query = sql.Composed([query, sql.SQL(" GROUP BY {products}.{_id}")])

        if query_params['asc']:
            query = sql.Composed(
                [query, sql.SQL(" ORDER BY {products}.{orderby} ASC")])
        else:
            query = sql.Composed(
                [query, sql.SQL(" ORDER BY {products}.{orderby} DESC")])

        query = sql.Composed(
            [query, sql.SQL(" LIMIT %(limit)s OFFSET %(offset)s;")])

        sql_statement = sql.SQL(
            query.as_string(self.cursor)
        ).format(
            _id=sql.Identifier('id'),
            name=sql.Identifier('name'),
            price=sql.Identifier('price'),
            products=sql.Identifier('products'),
            categories=sql.Identifier('categories'),
            description=sql.Identifier('description'),
            category_id=sql.Identifier('category_id'),
            category_name=sql.Identifier('category_name'),
            orderby=sql.Identifier(query_params['orderby']),
            filters=self.filters
        )
        try:
            self.cursor.execute(sql_statement, query_params)
            result = [dict(record) for record in self.cursor.fetchall()]
            return result
        except Exception as e:
            self.do_roll_back()
            print("Error-Select", "*"*5, str(e))
            raise InternalServerError()

    def insert(self, body: dict):
        """
        insert query
        """
        try:
            ids_map = dict()
            if body['categories']:
                category_table_data = [
                    (
                        data['name'],
                        data['description'],
                    )
                    for data in body['categories']
                ]
                args_str = ','.join(
                    self.cursor.mogrify(
                        "(%s,%s)",
                        data
                    ).decode("utf-8") for data in category_table_data
                )
                category_table_sql_statement = sql.SQL(
                    "INSERT INTO {categories} "
                    "({name},{description}) "
                    f"VALUES {args_str} "
                    "RETURNING {_id};"
                ).format(
                    products=sql.Identifier("categories"),
                    _id=sql.Identifier('id'),
                    name=sql.Identifier('name'),
                    category_id=sql.Identifier('description'),
                )
                self.cursor.execute(category_table_sql_statement)
                res = self.cursor.fetchall()
                inserted_ids = [rec['id'] for rec in res]
                body_ids = [pp['id']for pp in
                                   body['categories']]
                # this dictionary links inserted id to body id
                ids_map = {bi: ii for bi, ii in zip(
                    body_ids, inserted_ids)}
            if body['products']:
                if ids_map:
                    product_table_data = [
                        (
                            data['name'],
                            ids_map[data['category_id']],
                            data['price'],
                        )
                        for data in body['products']
                    ]
                else:
                    self.check_category_id_exists(
                        body['products']
                    )
                    product_table_data = [
                        (
                            data['name'],
                            data['category_id'],
                            data['price'],
                        )
                        for data in body['products']
                    ]
                args_str = ','.join(
                    self.cursor.mogrify(
                        "(%s,%s::INTEGER,%s::DOUBLE PRECISION)",
                        data
                    ).decode("utf-8") for data in product_table_data
                )
                product_table_sql_statement = sql.SQL(
                    "INSERT INTO {products} "
                    "({name},{category_id},{price}) "
                    f"VALUES {args_str};"
                ).format(
                    products=sql.Identifier('products'),
                    name=sql.Identifier('name'),
                    category_id=sql.Identifier('category_id'),
                    price=sql.Identifier('price'),
                )
                self.cursor.execute(product_table_sql_statement)
        except Exception as e:
            self.do_roll_back()
            print("Error-Insert", "*"*5, str(e))
            raise InternalServerError()

    def update(self, body: dict):
        """
        update query
        """
        # all ids are needed, check they are exists
        if body['products']:
            self.check_category_id_exists(body['products'])
            product_table_data = [
                (
                    data['id'],
                    data['name'],
                    data['category_id'],
                    data['price'],
                )
                for data in body['products']
            ]
            args_str = ','.join(
                self.cursor.mogrify(
                    "(%s::INTEGER,%s,%s::INTEGER,%s::DOUBLE PRECISION)",
                    data
                ).decode("utf-8") for data in product_table_data
            )
            product_table_sql_statement = sql.SQL(
                "WITH updated({_id},{name},{category_id},{price}) "
                f"AS (VALUES {args_str}) "
                "UPDATE {products} "
                "SET "
                "{name}=updated.{name}, "
                "{category_id}=updated.{category_id}, "
                "{price}=updated.{price} "
                "FROM updated "
                "WHERE ({products}.{_id} = updated.{_id});"
            ).format(
                _id=sql.Identifier('id'),
                name=sql.Identifier('name'),
                category_id=sql.Identifier('category_id'),
                price=sql.Identifier('price'),
                products=sql.Identifier('products'),
            )
        if body['categories']:
            category_table_data = [
                (
                    data['id'],
                    data['name'],
                    data['description'],
                )
                for data in body['categories']
            ]
            args_str = ','.join(
                self.cursor.mogrify(
                    "(%s::INTEGER,%s,%s)",
                    data
                ).decode("utf-8") for data in category_table_data
            )
            category_table_sql_statement = sql.SQL(
                "WITH updated({_id},{name},{description}) "
                f"AS (VALUES {args_str}) "
                "UPDATE {categories} "
                "SET "
                "{name}=updated.{name}, "
                "{description}=updated.{description} "
                "FROM updated "
                "WHERE ({categories}.{_id} = updated.{_id});"
            ).format(
                _id=sql.Identifier('id'),
                categories=sql.Identifier("categories"),
                name=sql.Identifier('name'),
                description=sql.Identifier('description'),
            )
        try:
            if body['products']:
                self.cursor.execute(product_table_sql_statement)
            if body['categories']:
                self.cursor.execute(category_table_sql_statement)
        except Exception as e:
            self.do_roll_back()
            print("Error-Update", "*"*5, str(e))
            raise InternalServerError()

    def delete(self, body: dict):
        """
        delete query
        """
        # all ids are needed, check they are exists
        product_ids = [product['id'] for product in body['products']]
        category_ids = [category['id'] for category in body['categories']]
        # product table sql query
        product_table_sql_statement = sql.SQL(
            """
            DELETE FROM {table_name} WHERE {_id} in %(ids)s;
            """
        ).format(
            table_name=sql.Identifier("products"),
            _id=sql.Identifier('id')
        )
        product_table_sql_kwargs = {
            'ids': tuple(product_ids)
        }
        # category table sql query
        category_table_sql_statement = sql.SQL(
            """
            DELETE FROM {table_name} WHERE {_id} in %(ids)s;
            """
        ).format(
            table_name=sql.Identifier("categories"),
            _id=sql.Identifier('id')
        )
        category_table_sql_kwargs = {
            'ids': tuple(category_ids)
        }
        try:
            if category_ids:
                self.cursor.execute(
                    category_table_sql_statement,
                    category_table_sql_kwargs)
            if product_ids:
                self.cursor.execute(
                    product_table_sql_statement,
                    product_table_sql_kwargs)
        except Exception as e:
            self.do_roll_back()
            print("Error-Delete", "*"*5, str(e))
            raise InternalServerError()
