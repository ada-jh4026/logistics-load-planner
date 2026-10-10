import pytest

from agent.schemas import IntentOp


def test_vehicle_ops_infer_target():
    assert IntentOp(action="remove_vehicle", id="V02").target == "vehicle"
    assert IntentOp(action="add_vehicle", value={"id": "V9"}).target == "vehicle"


def test_set_requires_target():
    with pytest.raises(ValueError):
        IntentOp(action="set", id="S01", field="service_min", value=5)


def test_unknown_store_reason_mentions_entity():
    from agent.interpret import apply_ops
    from agent.schemas import SolveRequest
    from agent.tests.checks import load_request

    r = SolveRequest(**load_request("partial"))
    _, _, rejected, _ = apply_ops(r, [IntentOp(action="set", target="store", id="S07", field="window_start_min", value=None)])
    assert rejected and "门店 S07 不存在" in rejected[0].reason
