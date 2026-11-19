# R004 data model

All durable tables carry organization_id/project_id with composite Project FK and transaction-bound RLS. Runtime is non-owner/NOBYPASSRLS. Map identity is UUID5(project UUID, "openvietgis:map"), unique per Project. Reads of unsaved maps return virtual revision0 without writing.

## ProjectMap
Fields: id UUID; organization_id UUID; project_id UUID; configuration_revision BIGINT0..2^53-1; configuration canonical validated JSON; updated_at UTC. Durable first row starts revision1. Unique(project_id,organization_id), composite identity FK. Current revision is CAS-updated under Project→map lock order.

## Configuration
Fields: layers ordered array0..32 of MapLayerReference; basemap literal grid; default_viewpoint null or Viewpoint.
Layer reference: layer_id UUID unique within map, visible boolean; style {color:#RRGGBB,opacity:0..1,width:1..12,radius:2..20}. Style applies only to supported family; no renderer/physical source handles.
Validate each reference's current same-Project ownership/lifecycle and applicable technical support under fresh authority on a new save. Removing retired/unavailable references remains possible. Historical evidence stores only safe configuration values/identities, never source features or credentials.

## Viewpoint
Fields: longitude[-180,180],latitude[-85.05112878,85.05112878],zoom[0,22],bearing[-180,180],pitch[0,60],crs literal4326. All numeric values finite and reject booleans/noncanonical data.
Save separate default_viewpoint intent: {mode:preserve}|{mode:clear}|{mode:set,value:Viewpoint}. preserve uses authoritative prior designated view even after incidental pan/zoom.

## SaveOperation
Fields: operation_id UUID scoped to Project; actor_type human/service_principal; actor_id UUID; request_hash SHA256 canonical expected_revision+configuration intent; committed_revision≥1; map_id; created_at UTC. Receipt: map_id,operation_id,configuration_revision.
Unique(Project,operation_id). Reuse by another actor returns generic conflict/notfound and no receipt. Same actor+same hash returns original receipt before CAS/no-op check; changed intent conflicts. Recheck current project.edit and credential ceiling for save and own-operation lookup. Archive/deletion/revocation can deny reconciliation. Session identity is not actor identity.

## MapRevision
Fields: map_id; revision≥1; prior_revision=revision-1; operation_id; actor_type/id/display snapshot; UTC created_at; before_configuration (null for first),after_configuration; audit_event_id. Unique(Project,map_id,revision) and operation. Append-only runtime grants/policies. Material save commits ProjectMap+revision+operation+success audit in one transaction. Same persisted config yields NO_CHANGES except first explicit default save. Failure rolls all back.

## ViewportSnapshot
Transient request: Org/Project/Layer; source content/schema pins; bbox4326 XY [west,south,east,north], ordered,nonwrap; feature limit1..1000. Response: existing R003 feature context with response_crs4326; items stable IDs+geometry (no attribute payload), complete boolean, limitation null|feature_limit|position_limit|byte_limit. Stable-ID order and lookahead. Bound20000positions,2MiB;2s SQL timeout and finite trusted fixture≤10000. Source/catalog/Layer metadata revisions are independent.
DisplayExtent response uses same context and actual approved transformed vertices: available+bounds4326,empty,unavailable. Never report a partial extent as full.

## WorkspaceSession / Selection
Transient per current actor/Org/Project: local configuration preview, camera,active Layer,selected stable feature IDs,focus,table page,request generation,save status. Selection key also includes Layer/source/content/schema. Selection max100 IDs; fit-selected uses max100 details/concurrency4/20000positions/2MiB aggregate, exceeding budget yields explicit unavailable. No durable selection or incidental camera. Clear old render/table/inspector/pending content on authoritative denial/context change; generation guard ignores delayed mismatched responses. Pages do not substitute IDs. Save state idle/dirty/saving/unresolved/committed/conflict/denied; ambiguous transport retains exact pending operation+intent until authoritative reconciliation.
