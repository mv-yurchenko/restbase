import os

import flask
from apscheduler.schedulers.background import BackgroundScheduler
from flask_restful import Api

from _logger import Logger
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
from rest import Logs
from rest import Table
from rest import UserToken
from rest.common_rest import RestCommon
from sql_query_worker import SqlQueryWorker
from token_worker import TokenWorker
from utils import get_bad_request_answer
from utils import get_local_table_name_from_request
from utils import get_worker
from utils import update_data_about_db_structure


app = flask.Flask("RestBase")

local_base_worker = LocalBaseWorker()
logger = Logger()

# Schedule database structure update
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    update_data_about_db_structure, "interval", minutes=30, args=[local_base_worker]
)
scheduler.start()

token_worker = TokenWorker(local_base_worker)
request_validator = RequestValidator()
rest_helper = RestCommon(local_base_worker, token_worker, request_validator, logger)

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


app_new.add_resource(
    Logs,
    "/Logs/",
    "/Logs",
    methods=["GET"],
    resource_class_kwargs={"rest_helper": rest_helper},
)


@app.route("/GrantTableAccess", methods=["POST"])
def grant_table_access():
    if not request_validator.validate_grant_table_access(flask.request):
        logger.log_incorrect_request("/GrantTableAccess/", flask.request)
        return flask.make_response(*get_bad_request_answer())

    token = flask.request.headers.get(ADMIN_TOKEN_FIELD_NAME)

    if not token_worker.is_token_admin(token):
        logger.log_access_denied("/GrantTableAccess", token)
        return flask.make_response("Access denied", 403)

    try:
        local_table_name = get_local_table_name_from_request(
            flask.request.args, local_base_worker
        )
        local_base_worker.add_table_for_token(
            token=flask.request.args.get(USER_TOKEN_FIELD_NAME),
            token_name=flask.request.args.get(USER_TOKEN_NAME_FIELD_NAME),
            local_table_name=local_table_name,
        )

        logger.log_status_execution(
            "/GrantTableAccess", token, "success", flask.request
        )

        return flask.make_response({"status": "success"}, 200)
    except (TableNotFoundError, AccessAlreadyGrantedError) as e:
        logger.log_status_execution("/GrantTableAccess", token, "error", flask.request)
        return flask.make_response({"status": "failed", "error": str(e)}, 404)


@app.route("/GetData", methods=["GET"])
def get_data_request():
    if not request_validator.validate_get_data_request(flask.request):
        logger.log_incorrect_request("/GetData", flask.request)
        return flask.make_response(*get_bad_request_answer())

    # Check if token has access to table
    token = flask.request.headers.get(USER_TOKEN_FIELD_NAME)

    if token not in local_base_worker.get_tokens_list():
        logger.log_not_found("/GetData", token, entity="token", entity_name=token)
        return flask.make_response("Access denied.", 404)

    query = flask.request.args.get(QUERY_FIELD_NAME)
    local_database_name = flask.request.args.get(LOCAL_DATABASE_NAME_FIELD_NAME)

    if local_database_name not in local_base_worker.get_db_name_list():
        logger.log_not_found(
            "/GetData", token, entity="database", entity_name=local_database_name
        )
        return flask.make_response(f"Database {local_database_name} not found.", 404)

    worker = get_worker(
        local_base_worker.get_db_type(local_db_name=local_database_name)
    )(local_database_name, local_base_worker)

    sql_worker = SqlQueryWorker(query, local_base_worker, local_database_name)

    for table in sql_worker.get_local_table_names():
        if not token_worker.validate_access(token, table):
            logger.log_access_denied(
                "/GetData", token, entity="table", entity_name=table
            )
            return flask.make_response(f"Access denied for table {table}", 403)

    try:
        return_data = worker.execute_get_data_request(query)
        logger.log_status_execution("/GetData", token, "success", flask.request)
        return flask.make_response({"data": return_data}, 200)

    except Exception as e:
        logger.log_status_execution("/GetData", token, "error", flask.request)
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
