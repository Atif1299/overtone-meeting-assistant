from __future__ import annotations

import boto3

from config import Settings


def _session_kwargs(settings: Settings) -> dict[str, str]:
    kwargs: dict[str, str] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return kwargs


def get_boto3_session(settings: Settings):
    return boto3.session.Session(**_session_kwargs(settings))


def get_sqs_client(settings: Settings):
    return get_boto3_session(settings).client("sqs")


def get_dynamodb_resource(settings: Settings):
    return get_boto3_session(settings).resource("dynamodb")

