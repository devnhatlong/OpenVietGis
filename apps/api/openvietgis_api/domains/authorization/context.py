from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Self
from uuid import UUID

ActorTypeLiteral = Literal["human", "service_principal", "system"]


@dataclass(frozen=True, slots=True)
class Actor:
    actor_type: ActorTypeLiteral
    actor_id: UUID | None
    display_name: str

    def __post_init__(self) -> None:
        if self.actor_type != "system" and self.actor_id is None:
            raise ValueError("non-system actor requires actor_id")


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    actor: Actor
    organization_id: UUID
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    credential_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RequestedActorContext:
    actor_type: ActorTypeLiteral
    actor_id: UUID | None
    organization_id: UUID
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    credential_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.actor_type != "system" and self.actor_id is None:
            raise ValueError("non-system requested actor requires actor_id")
        if (self.actor_type == "service_principal") != (self.credential_id is not None):
            raise ValueError("only service actors must include credential_id")

    def to_payload(self) -> dict[str, str | None]:
        return {
            "actor_type": self.actor_type,
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "organization_id": str(self.organization_id),
            "workspace_id": str(self.workspace_id) if self.workspace_id else None,
            "project_id": str(self.project_id) if self.project_id else None,
            "credential_id": str(self.credential_id) if self.credential_id else None,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Self:
        actor_type = payload.get("actor_type")
        if actor_type not in {"human", "service_principal", "system"}:
            raise ValueError("invalid actor_type")
        return cls(
            actor_type=actor_type,
            actor_id=UUID(payload["actor_id"]) if payload.get("actor_id") else None,
            organization_id=UUID(payload["organization_id"]),
            workspace_id=UUID(payload["workspace_id"]) if payload.get("workspace_id") else None,
            project_id=UUID(payload["project_id"]) if payload.get("project_id") else None,
            credential_id=UUID(payload["credential_id"]) if payload.get("credential_id") else None,
        )
