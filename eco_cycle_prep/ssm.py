from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def _client():
    return boto3.client("ssm", region_name="us-east-1")


def get(name: str) -> str:
    return _client().get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
