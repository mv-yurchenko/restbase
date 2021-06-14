import json

import pytest
import requests

from tables import TokenTable
from utils import get_existing_data


@pytest.mark.parametrize(
    "data_dict,expected_status_code",
    [
        ({"token_name": "test_token"}, 200),
        ({"token_name": "test_token1", "description": "test_description"}, 200),
    ],
)
def test_generate_admin_token_correct_header(
    restbase_url,
    test_main_admin_token,
    postgres_session,
    data_dict,
    expected_status_code,
):
    response = requests.post(
        restbase_url + "AdminToken/Generate/",
        headers={"token": test_main_admin_token},
        data=json.dumps(data_dict),
    )
    assert response.status_code == expected_status_code
    new_token = json.loads(response.text)["new_token"]

    tokens = get_existing_data(
        postgres_session,
        TokenTable,
    )

    # Check new token exists in database
    assert new_token in [i.token for i in tokens if i.admin_access]
    if data_dict.get("description"):
        assert data_dict.get("description") in [
            i.description for i in tokens if i.token == new_token
        ]


@pytest.mark.parametrize(
    "data_dict,expected_status_code",
    [
        ({"token_name": "test_token"}, 403),
        ({"token_name": "test_token", "description": "test_description"}, 403),
    ],
)
def test_generate_admin_token_incorrect_header(
    restbase_url,
    data_dict,
    expected_status_code,
):
    response = requests.post(
        restbase_url + "AdminToken/Generate/",
        headers={"token": "123"},
        data=json.dumps(data_dict),
    )
    assert response.status_code == expected_status_code


@pytest.mark.parametrize(
    "data_dict,expected_status_code",
    [
        ({"token_name": "test_user_token"}, 200),
        ({"token_name": "test_user_token1", "description": "test_description"}, 200),
    ],
)
def test_generate_user_token_correct_header(
    restbase_url,
    test_main_admin_token,
    postgres_session,
    data_dict,
    expected_status_code,
):
    response = requests.post(
        restbase_url + "UserToken/Generate/",
        headers={"token": test_main_admin_token},
        data=json.dumps(data_dict),
    )
    assert response.status_code == expected_status_code
    new_token = json.loads(response.text)["new_token"]

    tokens = get_existing_data(
        postgres_session,
        TokenTable,
    )

    # Check new token exists in database
    assert new_token in [i.token for i in tokens if not i.admin_access]
    if data_dict.get("description"):
        assert data_dict.get("description") in [
            i.description for i in tokens if i.token == new_token
        ]


@pytest.mark.parametrize(
    "data_dict,expected_status_code",
    [
        ({"token_name": "test_user_token"}, 403),
        ({"token_name": "test_user_token_1", "description": "test_description"}, 403),
    ],
)
def test_generate_user_token_incorrect_header(
    restbase_url,
    data_dict,
    expected_status_code,
):
    response = requests.post(
        restbase_url + "UserToken/Generate/",
        headers={"token": "123"},
        data=json.dumps(data_dict),
    )
    assert response.status_code == expected_status_code