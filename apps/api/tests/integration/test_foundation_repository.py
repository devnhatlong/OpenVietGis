from openvietgis_api.adapters.persistence.db import get_session_factory
from openvietgis_api.adapters.persistence.foundation_repository import SqlFoundationRepository
from openvietgis_api.domain.foundation import FoundationSampleRecord


def test_repository_creates_and_reads_record(migrated_database: None) -> None:
    created = FoundationSampleRecord.create("repository-check")

    with get_session_factory()() as session:
        repository = SqlFoundationRepository(session)
        repository.add(created)
        session.commit()

    with get_session_factory()() as session:
        loaded = SqlFoundationRepository(session).get(created.id)

    assert loaded == created
