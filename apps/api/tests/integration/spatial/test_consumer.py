"""Run the same API-only consumer against real restricted fixture storage."""

from tests.contract.test_spatial_consumer import exercise_consumer
from tests.fixtures.identity_tenancy import seed_access_world
from tests.integration.spatial.test_sources import _client


def test_independent_consumer_restricted_postgis(migrated_database: None) -> None:
    world = seed_access_world()
    with _client(world.owner_user_id) as client:
        exercise_consumer(client, world.organization_id, world.project_id)
