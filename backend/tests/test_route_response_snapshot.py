"""RouteResponseSnapshot 测试辅助模型回归。"""

from test_support.route_response_snapshot import RouteResponseSnapshot


def test_route_response_snapshot_records_nested_shape():
    body = {
        "items": [
            {
                "title": "流浪地球",
                "rating": 8.1,
                "local_status": None,
                "flags": {"local": True},
            }
        ],
        "total": 1,
    }

    snapshot = RouteResponseSnapshot.from_body(200, body)

    assert snapshot.status_code == 200
    assert snapshot.body_type == "dict"
    assert snapshot.list_lengths == {"items": 1}
    assert snapshot.field_types["items[].title"] == "str"
    assert snapshot.field_types["items[].rating"] == "float"
    assert snapshot.field_types["items[].local_status"] == "none"
    assert snapshot.field_types["items[].flags.local"] == "bool"
    assert snapshot.field_paths == tuple(sorted(snapshot.field_paths))


def test_route_response_snapshot_keeps_empty_list_shape():
    snapshot = RouteResponseSnapshot.from_body(200, {"items": [], "total": 0})

    assert snapshot.field_types["items"] == "list"
    assert snapshot.field_types["total"] == "int"
    assert snapshot.list_lengths == {"items": 0}
    assert "items[]" not in snapshot.field_paths


def test_route_response_snapshot_supports_top_level_list():
    snapshot = RouteResponseSnapshot.from_body(200, [{"id": "a"}, {"id": "b"}])

    assert snapshot.body_type == "list"
    assert snapshot.list_lengths == {}
    assert snapshot.field_types["[]"] == "dict"
    assert snapshot.field_types["[].id"] == "str"
