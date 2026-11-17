from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from testcontainers.community.postgres import PostgresContainer


@dataclass(frozen=True, slots=True)
class SyntheticIds:
    user_a: UUID
    user_b: UUID
    organization_a: UUID
    organization_b: UUID


@pytest.fixture
def synthetic_ids() -> SyntheticIds:
    return SyntheticIds(
        user_a=uuid4(),
        user_b=uuid4(),
        organization_a=uuid4(),
        organization_b=uuid4(),
    )


@pytest.fixture
def postgis_container_factory() -> Callable[[], PostgresContainer]:
    def factory() -> PostgresContainer:
        return PostgresContainer(
            image="postgis/postgis:18-3.7",
            username="openvietgis",
            password="openvietgis",
            dbname="openvietgis_test",
            driver="psycopg",
        )

    return factory