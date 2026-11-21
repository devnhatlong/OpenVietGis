"""Strict processing parameter contract without database or network dependencies."""

import pytest

from openvietgis_api.domains.platform_errors import PlatformValidationError
from openvietgis_api.domains.processing.domain import AlgorithmId, validate_algorithm_parameters


@pytest.mark.parametrize("value", [0.1, 12.5, 250, 1000, 500000])
def test_buffer_valid_distance(value):
    assert validate_algorithm_parameters(AlgorithmId.BUFFER, {"distance_meters": value}) == {
        "distance_meters": float(value),
        "quad_segs": 8,
    }


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        {"distance_meters": None},
        {"distance_meters": True},
        {"distance_meters": "1000"},
        {"distance_meters": []},
        {"distance_meters": 0},
        {"distance_meters": 0.09},
        {"distance_meters": -1},
        {"distance_meters": 500001},
        {"distance_meters": 10**400},
        {"distance_meters": float("nan")},
        {"distance_meters": float("inf")},
        {"distance_meters": -float("inf")},
        {"distance_meters": 100, "quad_segs": 2.5},
        {"distance_meters": 100, "quad_segs": "8"},
        {"distance_meters": 100, "quad_segs": True},
        {"distance_meters": 100, "quad_segs": 1},
        {"distance_meters": 100, "quad_segs": 17},
        {"distance_meters": 100, "unexpected": 1},
    ],
)
def test_invalid_buffer_parameter_is_domain_error(parameters):
    with pytest.raises(PlatformValidationError) as error:
        validate_algorithm_parameters(AlgorithmId.BUFFER, parameters)
    assert error.value.code == "INVALID_PARAMETERS"


@pytest.mark.parametrize("algorithm", [AlgorithmId.CLIP, AlgorithmId.DISSOLVE])
def test_unknown_parameter_rejected(algorithm):
    with pytest.raises(PlatformValidationError) as error:
        validate_algorithm_parameters(algorithm, {"unexpected": 1})
    assert error.value.code == "INVALID_PARAMETERS"
