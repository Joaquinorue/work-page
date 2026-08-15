import json
import os

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _list_by_type(item_type):
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(item_type),
    )
    return result["Items"]


def _get_one(item_type, item_id):
    result = table.get_item(Key={"PK": f"{item_type}#{item_id}", "SK": "METADATA"})
    return result.get("Item")


def _put_item(item_type, item_id, attributes):
    item = {
        "PK": f"{item_type}#{item_id}",
        "SK": "METADATA",
        "GSI1PK": item_type,
        "GSI1SK": f"{item_type}#{item_id}",
        **attributes,
    }
    table.put_item(Item=item)
    return item


def _delete_item(item_type, item_id):
    table.delete_item(Key={"PK": f"{item_type}#{item_id}", "SK": "METADATA"})


def handler(event, context):
    route_key = event.get("routeKey", "")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    try:
        if route_key == "GET /items":
            item_type = query_params.get("type")
            if not item_type:
                return _response(400, {"error": "falta el query param 'type'"})
            return _response(200, _list_by_type(item_type.upper()))

        if route_key == "GET /items/{type}/{id}":
            item = _get_one(path_params["type"].upper(), path_params["id"])
            if item is None:
                return _response(404, {"error": "no encontrado"})
            return _response(200, item)

        if route_key == "POST /items":
            body = json.loads(event.get("body") or "{}")
            item_type = body.pop("type", None)
            item_id = body.pop("id", None)
            if not item_type or not item_id:
                return _response(400, {"error": "faltan 'type' o 'id' en el body"})
            return _response(201, _put_item(item_type.upper(), item_id, body))

        if route_key == "DELETE /items/{type}/{id}":
            _delete_item(path_params["type"].upper(), path_params["id"])
            return _response(204, {})

        return _response(404, {"error": f"ruta no soportada: {route_key}"})

    except Exception as exc:
        return _response(500, {"error": str(exc)})
