"""Metadata is not an executable module registration or an effective grant."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from openvietgis_api.adapters.http.extensions import (
    CreateExtensionRecordRequest,
    RegisterManifestRequest,
    router,
)
from openvietgis_api.adapters.persistence import extensions_repository as repository
from openvietgis_api.domains.authorization.context import Actor, AuthorizationContext
from openvietgis_api.domains.authorization.permissions import Permission
from openvietgis_api.domains.extensions.domain import ExtensionManifestRecord
from openvietgis_api.domains.platform_errors import PlatformConflictError


def _context() -> AuthorizationContext:
    return AuthorizationContext(
        actor=Actor("human", uuid4(), "Test actor"),
        organization_id=uuid4(),
        project_id=uuid4(),
    )


def _manifest(context: AuthorizationContext) -> ExtensionManifestRecord:
    return ExtensionManifestRecord(
        id=uuid4(),
        organization_id=context.organization_id,
        extension_key="fixture_ext",
        version="1.0.0",
        api_compatibility="1.x",
        display_name="Fixture",
        description="",
        permissions=["ext.fixture_ext.read"],
        commands=[{"id": "read", "label": "Read"}],  # legacy missing permission
        capabilities=[],
        entity_schemas={"entry": {"fields": {"title": {"type": "text"}}}},
        enabled=True,
        registered_by_actor_id=uuid4(),
        created_at=datetime.now(UTC),
    )


def test_legacy_metadata_cannot_be_activated(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _context()
    manifest = _manifest(ctx)
    session = MagicMock()
    session.execute.return_value.mappings.return_value.first.return_value = {
        "id": manifest.id,
        "extension_key": manifest.extension_key,
    }
    repo = repository.SqlExtensionsRepository(session)
    scope = MagicMock()
    monkeypatch.setattr(repository, "prepare_project_scope", scope)
    monkeypatch.setattr(repo, "_manifest", lambda *_: manifest)

    with pytest.raises(PlatformConflictError) as error:
        repo.activate_for_project(context=ctx, manifest_id=manifest.id)

    assert error.value.code == "EXTENSION_MANIFEST_REVALIDATION_REQUIRED"
    scope.assert_called_once_with(session, ctx, permission=Permission.PROJECT_MANAGE)
    assert session.execute.call_count == 1
    session.commit.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update", "import"])
def test_invalid_active_manifest_blocks_new_data_mutations(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ctx = _context()
    manifest = _manifest(ctx)
    session = MagicMock()
    repo = repository.SqlExtensionsRepository(session)
    scope = MagicMock()
    monkeypatch.setattr(repository, "prepare_project_scope", scope)
    monkeypatch.setattr(
        repo, "_activation_row", lambda *_: {"manifest_id": manifest.id, "status": "active"}
    )
    monkeypatch.setattr(repo, "_manifest", lambda *_: manifest)

    with pytest.raises(PlatformConflictError) as error:
        if operation == "create":
            repo.create_record(
                context=ctx, extension_key=manifest.extension_key, entity_name="entry", payload={}
            )
        elif operation == "update":
            repo.update_record(
                context=ctx,
                extension_key=manifest.extension_key,
                record_id=uuid4(),
                expected_revision=1,
                expected_manifest_id=manifest.id,
                payload={},
                expected_link_context=None,
            )
        else:
            repo.import_bundle(
                context=ctx,
                extension_key=manifest.extension_key,
                expected_manifest_id=manifest.id,
                bundle={},
                sha256="0" * 64,
            )

    assert error.value.code == "EXTENSION_MANIFEST_REVALIDATION_REQUIRED"
    scope.assert_called_once_with(session, ctx, permission=Permission.PROJECT_EDIT)
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_legacy_metadata_cannot_transition_to_new_version(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _context()
    current = _manifest(ctx)
    target = replace(current, id=uuid4(), version="1.1.0")
    session = MagicMock()
    session.execute.return_value.mappings.return_value.one_or_none.return_value = {
        "manifest_id": current.id,
    }
    repo = repository.SqlExtensionsRepository(session)
    monkeypatch.setattr(repository, "prepare_project_scope", MagicMock())
    monkeypatch.setattr(
        repo,
        "_manifest",
        lambda _, mid: {
            current.id: current,
            target.id: target,
        }[mid],
    )

    with pytest.raises(PlatformConflictError) as error:
        repo.transition_version(
            context=ctx,
            activation_id=uuid4(),
            expected_manifest_id=current.id,
            target_manifest_id=target.id,
        )

    assert error.value.code == "EXTENSION_MANIFEST_REVALIDATION_REQUIRED"
    assert session.execute.call_count == 1
    session.commit.assert_not_called()


def test_extension_router_has_only_metadata_and_retained_record_endpoints() -> None:
    # Deliberate allowlist: adding an execution/contribution/installation route
    # requires revisiting this trust-boundary test rather than accepting it silently.
    expected = {
        ("POST", "/organizations/{organization_id}/extensions/manifests"),
        ("GET", "/organizations/{organization_id}/extensions/manifests"),
    }
    base = "/organizations/{organization_id}/projects/{project_id}/extensions"
    expected.update(
        (method, base + path)
        for method, path in (
            ("POST", "/activations"),
            ("GET", "/activations"),
            ("POST", "/activations/{activation_id}/deactivate"),
            ("POST", "/activations/{activation_id}/transition"),
            ("GET", "/activations/{activation_id}/history"),
            ("POST", "/{extension_key}/records"),
            ("GET", "/{extension_key}/records"),
            ("PUT", "/{extension_key}/records/{record_id}"),
            ("GET", "/{extension_key}/records/{record_id}/history"),
            ("GET", "/{extension_key}/portable-export"),
            ("POST", "/{extension_key}/portable-import"),
        )
    )
    routes = {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or ()
    }
    assert routes == expected
    with pytest.raises(ValueError):
        Permission("ext.fixture_ext.read")


def test_request_bodies_reject_executable_or_installation_approval_fields() -> None:
    fields = {
        "extension_key": "fixture_ext",
        "version": "1.0.0",
        "display_name": "Fixture",
        "entity_schemas": {},
    }
    for forbidden in ("installation_approved", "executable", "dependencies", "handler"):
        with pytest.raises(ValidationError):
            RegisterManifestRequest.model_validate({**fields, forbidden: True})
    with pytest.raises(ValidationError):
        CreateExtensionRecordRequest.model_validate(
            {"entity_name": "entry", "payload": {}, "command_id": "read"}
        )
