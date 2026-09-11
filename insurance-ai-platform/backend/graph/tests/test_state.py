from graph.state import make_audit_event


def test_make_audit_event_has_expected_shape():
    event = make_audit_event(node="test_node", event_type="unit_test", description="desc", data={"a": 1})

    assert event["node"] == "test_node"
    assert event["event_type"] == "unit_test"
    assert event["description"] == "desc"
    assert event["data"] == {"a": 1}
    assert isinstance(event["timestamp"], str) and event["timestamp"]


def test_make_audit_event_defaults_empty_data():
    event = make_audit_event(node="n", event_type="e", description="d")
    assert event["data"] == {}
