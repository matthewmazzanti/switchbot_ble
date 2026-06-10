"""Tests for Blind Tilt response serialization."""

from switchbot.proto.blind_tilt.responses import (
    ActionModeResponse,
    CalibrationResponse,
    CalibrationStepResponse,
    DelayResponse,
    PositionResponse,
    StatusResponse,
)


class TestPositionResponse:
    def test_roundtrip(self):
        resp = PositionResponse(status=1, run_status=0, position=50)
        assert PositionResponse.from_bytes(resp.to_bytes()) == resp

    def test_moving(self):
        resp = PositionResponse(status=1, run_status=1, position=25)
        assert PositionResponse.from_bytes(resp.to_bytes()) == resp

    def test_wire_format(self):
        resp = PositionResponse(status=1, run_status=2, position=100)
        assert resp.to_bytes() == bytes([0x01, 0x02, 0, 0, 0, 0, 100])


class TestCalibrationResponse:
    def test_roundtrip_calibrated(self):
        resp = CalibrationResponse(
            status=1, calibrated=True, direction_set=True, direction=0
        )
        assert CalibrationResponse.from_bytes(resp.to_bytes()) == resp

    def test_roundtrip_reversed(self):
        resp = CalibrationResponse(
            status=1, calibrated=False, direction_set=True, direction=1
        )
        assert CalibrationResponse.from_bytes(resp.to_bytes()) == resp

    def test_wire_format(self):
        resp = CalibrationResponse(
            status=1, calibrated=True, direction_set=False, direction=0
        )
        assert resp.to_bytes() == bytes([0x01, 0x04])


class TestCalibrationStepResponse:
    def test_roundtrip(self):
        resp = CalibrationStepResponse(
            status=1, step=4, enable_next=True, exit=False, direction_error=False
        )
        assert CalibrationStepResponse.from_bytes(resp.to_bytes()) == resp

    def test_exit(self):
        resp = CalibrationStepResponse(
            status=1, step=4, enable_next=False, exit=True, direction_error=False
        )
        assert CalibrationStepResponse.from_bytes(resp.to_bytes()) == resp

    def test_wire_format(self):
        # step=4, exit=1 -> 0x24
        resp = CalibrationStepResponse(
            status=1, step=4, enable_next=False, exit=True, direction_error=False
        )
        assert resp.to_bytes() == bytes([0x01, 0x24])


class TestActionModeResponse:
    def test_roundtrip_performance(self):
        resp = ActionModeResponse(status=1, silent=False)
        assert ActionModeResponse.from_bytes(resp.to_bytes()) == resp

    def test_roundtrip_silent(self):
        resp = ActionModeResponse(status=1, silent=True)
        assert ActionModeResponse.from_bytes(resp.to_bytes()) == resp


class TestDelayResponse:
    def test_roundtrip(self):
        resp = DelayResponse(status=1, timestamp=1700000000, position=50)
        assert DelayResponse.from_bytes(resp.to_bytes()) == resp

    def test_wire_format(self):
        resp = DelayResponse(status=1, timestamp=0, position=0)
        assert resp.to_bytes() == bytes([0x01, 0, 0, 0, 0, 0])


class TestStatusResponse:
    def test_roundtrip(self):
        resp = StatusResponse(status=1)
        assert StatusResponse.from_bytes(resp.to_bytes()) == resp

    def test_error(self):
        resp = StatusResponse(status=2)
        assert StatusResponse.from_bytes(resp.to_bytes()) == resp
