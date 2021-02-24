import os

import flask
from flask_restful import Api

from exceptions import AccessAlreadyGrantedError
from exceptions import TableNotFoundError
from fields import ADMIN_TOKEN_FIELD_NAME
from fields import LOCAL_DATABASE_NAME_FIELD_NAME
from fields import QUERY_FIELD_NAME
from fields import USER_TOKEN_FIELD_NAME
from fields import USER_TOKEN_NAME_FIELD_NAME
from localbase import LocalBaseWorker
from request_validator import RequestValidator
from rest import AdminToken
from rest import Database
from rest import ListDatabase
from rest import ListTable
from rest import ListUserToken
from rest import Table
from rest import UserToken
from rest.common_rest import RestCommon
from sql_query_worker import SqlQueryWorker
from token_worker import TokenWorker
from utils import get_bad_request_answer
from utils import get_local_table_name_from_request
from utils import get_worker

app = flask.Flask("RestBase")

local_base_worker = LocalBaseWorker()

token_worker = TokenWorker(local_base_worker)
request_validator = RequestValidator()
rest_helper = RestCommon(local_base_worker, token_worker, request_validator)

app_new = Api(app)
app_new.add_resource(
    AdminToken,
    "/GenerateAdminToken",
    "/GenerateAdminToken/",
    resource_class_kwargs={"rest_helper": rest_helper},
)

app_new.add_resource(
    UserToken,
    "/GenerateUserToken",
    "/GenerateUserToken/",
    methods=["PUT"],
    resource_class_kwargs={"rest_helper": rest_helper},
)


app_new.add_resource(
    ListUserToken,
    "/ListUserTokens",
    "/ListUserTokens/",
    methods=["GET"],
    resource_class_kwargs={"rest_helper": rest_helper},
)

app_new.add_resource(
    Database,
    "/Database",
    "/Database/",
    methods=["PUT", "GET", "POST"],
    resource_class_kwargs={"rest_helper": rest_helper},
)


app_new.add_resource(
    ListDatabase,
    "/Database/list",
    "/Database/list/",
    methods=["GET"],
    resource_class_kwargs={"rest_helper": rest_helper},
)

app_new.add_resource(
    Table,
    "/Table",
    "/Table/",
    methods=["GET", "POST"],
    resource_class_kwargs={"rest_helper": rest_helper},
)

app_new.add_resource(
    ListTable,
    "/Table/list",
    "/Table/list/",
    methods=["GET"],
    resource_class_kwargs={"rest_helper": rest_helper},
)


@app.route("/GrantTableAccess", methods=["POST"])
def grant_table_access():
    if not request_validator.validate_grant_table_access(flask.request):
        return flask.make_response(*get_bad_request_answer())

    token = flask.request.headers.get(ADMIN_TOKEN_FIELD_NAME)

    if not token_worker.is_token_admin(token):
        return flask.make_response("Access denied", 403)

    try:
        local_base_worker.add_table_for_token(
            token=flask.request.args.get(USER_TOKEN_FIELD_NAME),
            token_name=flask.request.args.get(USER_TOKEN_NAME_FIELD_NAME),
            local_table_name=get_local_table_name_from_request(
                flask.request.args, local_base_worker
            ),
        )

        return flask.make_response({"status": "success"}, 200)
    except (TableNotFoundError, AccessAlreadyGrantedError) as e:
        return flask.make_response({"status": "failed", "error": str(e)}, 404)


@app.route("/GetData", methods=["GET"])
def get_data_request():
    if not request_validator.validate_get_data_request(flask.request):
        return flask.make_response(*get_bad_request_answer())

    # Check if token has access to table
    token = flask.request.headers.get(USER_TOKEN_FIELD_NAME)

    if token not in local_base_worker.get_tokens_list():
        return flask.make_response("Token not found.", 404)

    query = flask.request.args.get(QUERY_FIELD_NAME)
    local_database_name = flask.request.args.get(LOCAL_DATABASE_NAME_FIELD_NAME)

    if local_database_name not in local_base_worker.get_db_name_list():
        return flask.make_response(f"Database {local_database_name} not found.", 404)

    worker = get_worker(
        local_base_worker.get_db_type(local_db_name=local_database_name)
    )(local_database_name, local_base_worker)

    sql_worker = SqlQueryWorker(query, local_base_worker, local_database_name)

    for table in sql_worker.get_local_table_names():
        if not token_worker.validate_access(token, table):
            return flask.make_response(f"Access denied for table {table}", 403)

    try:
        return_data = worker.execute_get_data_request(query)
        return flask.make_response({"data": return_data}, 200)

    except Exception as e:

        return flask.make_response(
            {
                "status": "error",
                "server error": str(e),
                "message": "Make sure that request parameters are correct. If all is correct pls report bug on github.",
            },
            500,
        )


if __name__ == "__main__":
    if os.getenv("STAGE") == "test":
        local_base_worker.add_test_token()
    app.run(host="0.0.0.0", port=54541)
