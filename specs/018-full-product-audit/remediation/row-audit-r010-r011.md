# R010 / R011 row-level reconciliation, 9b12310

**Audit only.** Frozen original source `854fcd0:specs/010-external-sources/spec.md`
(lines 114–197) and `26a170b:specs/011-team-collaboration/spec.md`
(lines 97–158), not the current abbreviated slice specs. Baseline source
`9b12310` in `/opt/openvietgis-remediation-018`. Each of 97 original identifiers
appears once. No release acceptance, production mutation, permission bypass, service
startup or actual remote provider/customer requests.

Legend, mutually exclusive classification of *existing evidence*, not acceptance:

- **E:** Specific exercised assertion supports at least a bounded portion of the
  oracle; the residual column states what is still open.
- **S:** Static implementation/scope mapping only, not a matching executed oracle.
- **G:** Material workflow or acceptance criterion absent/unproved; nearby narrow
  evidence may exist but does not exercise that row's central behavior.

All categories remain open for independent review. Counts:

| Scope | Exercised partial E | Static S | Gap G | Total |
| --- | ---: | ---: | ---: | ---: |
| R010 | 37 | 4 | 9 | 50 |
| R011 | 34 | 5 | 8 | 47 |
| Total | 71 | 9 | 17 | 97 |

## Evidence key (specific tests, provenance and boundaries)

Fresh exact-source unit execution in existing isolated working tree, using cached Python:
`cd apps/api; .venv/bin/python -m pytest -q tests/unit/test_external_provider.py tests/unit/test_external_raster_provider.py tests/unit/test_external_cog_provider.py --disable-warnings`
**42/42 pass**;
`.venv/bin/python -m pytest tests/unit/test_editing_replay_and_rebase.py tests/unit/test_editing_domain.py --disable-warnings`
**21/21 pass (0.13s)**. No DB/browser invocation in this audit.

- **U1**: `apps/api/tests/unit/test_external_provider.py`, particularly
  `test_wms_real_preview_bytes_and_request_parameters`,
  `test_wfs_real_bounded_read_and_query`,
  `test_profile_default_denial_exact_match_rights_and_revocation`,
  `test_dns_rebinding_mixed_public_private_reject` (seven cases),
  `test_actual_peer_mismatch_rejects_before_tls`,
  `test_tls_host_certificate_failure_no_http_request`,
  `test_invalid_operator_policy_fails_closed`,
  `test_redirects_never_followed`,
  `test_media_types_encoding_and_response_size_fail_closed`,
  `test_xml_injection_wrong_layer_bbox_crs_and_image_rejected`,
  `test_geojson_wrong_axis_nonfinite_properties_count_and_crs_rejected`,
  `test_no_raw_query_credentials_displayed`,
  `test_dns_resolution_has_absolute_wait_bound`. Actual stdlib HTTP
  protocol/payload parsing with synthetic socket/DNS/TLS boundaries; no live TLS.
- **U2**: `apps/api/tests/unit/test_external_raster_provider.py`,
  `test_fixed_approved_tile_real_pixel_proof` (XYZ/WMTS),
  `test_tile_policy_valid_and_invalid_coordinates_bounds_origin`,
  `test_xyz_metadata_mismatch_never_requests_tile`,
  `test_wmts_metadata_wrong_matrix_crs_scale_or_limits_denied`,
  `test_tiled_geotiff_real_range_pixels_and_georeference`,
  `test_tiff_wrong_range_response_and_large_source_denied`,
  `test_tiff_bad_crs_georeference_offsets_compression_or_payload_denied`.
- **U3**: `apps/api/tests/unit/test_external_cog_provider.py`,
  `test_actual_cog_overview_and_native_window_pixels`,
  `test_profile_and_viewport_default_deny_no_egress`,
  `test_bad_range_or_version_denied` (seven conditions),
  `test_invalid_cog_directory_georeference_and_decompression_denied` (three),
  `test_bounds_valid_but_excessive_tile_budget_denied`,
  `test_real_gdal_cog_generator_and_independent_pixel_oracle` (two:
  EPSG4326 grayscale; EPSG3857 RGB; exact output pixel arrays).
- D/C/A below are **historical actual DB** testcase results verified individually
  PASS in `dist/remediation-next018/final-integration-2b47cc2.xml` (not a
  new DB run). The full suite had unrelated historical failures; never
  claim the invocation green. Git diff on these specific R010/collaboration/editing
  source and test paths between 2b47cc2 and 9b12310 was empty; that is
  source comparability, not a claim that all shared dependencies or runtime
  are identical.
- **D1**: `apps/api/tests/integration/m3/test_r010_r013_real.py::test_r010_external_sources_ssrf_and_allowlist`.
- **D2**: `apps/api/tests/integration/m3/test_r010_live_provider.py::test_r010_provider_preview_real_auth_live_bytes_and_reopen`. Actual DB/auth but controlled fetch bytes, never a real outside provider.
- **D3**: `apps/api/tests/integration/m3/test_r010_raster_provider.py::test_r010_raster_profiles_protected_api`.
- **D4**: `apps/api/tests/integration/m3/test_r010_cog_viewport.py::test_r010_cog_viewport_authorization_pixels_and_generation`.
- **C1**: `apps/api/tests/integration/m3/test_independent_lifecycle.py::test_review_assignee_current_permission_and_immutable_decision`.
- **C2**: `apps/api/tests/integration/m3/test_collaboration_revision_chain.py::test_replay_actor_and_rebase_exact_history`.
- **C3**: `apps/api/tests/integration/m2/test_r006_r009_real.py::test_r006_editing_changesets_conflicts_validation_and_revert`.
- **C4**: `apps/api/tests/integration/m3/test_r010_r013_real.py::test_r011_r012_r013_collaboration_cad_and_field_offline`.
- **A**: historical exact individual PASS tests also in same JUnit:
  `apps/api/tests/integration/tenancy/test_workspace_grant_inheritance.py::test_workspace_grant_inheritance_is_dynamic_and_project_grant_is_additive`;
  `apps/api/tests/integration/spatial/test_authorization.py::test_change_history_rechecks_current_read_and_scope`
  (human/service); and `apps/api/tests/integration/maps/test_saves.py`
  tests named in rows. Related foundation assertions, not equivalent to direct collaboration route tests.
- **B**: real Chromium `tests/e2e/platform-m2-m3.spec.ts`, “M2+M3 end-to-end:
  R006 Editing, R007 Query, R008 Processing, R009 Cartography, and R010–R015 Hub”
  at historic c7bbe62 verification (same runtime as 2b47cc2).
  See [integrated checkpoint](final-next-integration-evidence.md) and
  `/opt/openvietgis-verify-0019-browser/dist/remediation-0019-browser/focused-c7bbe62.json`.
  Exact assertions lines 136–155: select source and changeset, self-assign,
  comment anchored to feat_new_1 and display, decide and display decision note.
  Single actor, no multi-user reviewer or independent human acceptance.
- [provider slice](G004-external-capability/provider-slice-evidence.md),
  [raster slice](G004-external-capability/raster-slice-evidence.md),
  [COG window slice](G004-external-capability/cog-window-evidence.md),
  [lifecycle checkpoint](r011-r014-lifecycle-checkpoint.md) corroborate constraints;
  historical evidence does not transfer full acceptance.

Static paths inspected: `apps/api/openvietgis_api/domains/external_sources/{domain,provider,cog_provider,geotiff_provider,tile_provider}.py`,
`adapters/http/{external_sources,external_provider_transport,collaboration}.py`,
`adapters/persistence/{external_sources_repository,collaboration_repository,editing_repository}.py`,
migrations 0013, 0014; `apps/web/src/features/platform/{ExternalSourcePreview,CollaborationWorkbenchPanel,PlatformHubPage}.tsx`,
and maplibre-engine.ts. Prefix adapter paths are under apps/api/openvietgis_api.

## R010: fifty row oracles

| ID | Evidence | Required oracle | Actual assertion or static mapping | Residual / next test |
| --- | --- | --- | --- | --- |
| R010/FR-001 | E | Register each of four protocols, obtain real validated payload, prove gate | U1 WMS PNG and WFS exact features; U2 XYZ/WMTS pixel and TIFF quadrants; U3 GDAL overview/crop; D1–D4 201 unverified→fresh proof | No full adapter acceptance, OGC API Features/owned raster missing; validate full profiles and reopen map. |
| R010/FR-002 | G | Distinct stable external DataSource, logical Layer, same project and Map references | external_sources.connections stable UUID/org/project; _conn_wire exposes IDs, but no R003 DataSource/Layer linkage | Implement logical layer and dependency model; ensure map references never directly store endpoint. |
| R010/FR-003 | E | Viewer register/configure/refresh/disable denied; manager permitted | D2 owner register, no-grant member allowlist and preview denied; create_connection/invalidate/revoke require project.edit | Viewer-vs-manager matrix, source-management permission distinct from project.edit, reconfigure/detach not implemented. |
| R010/FR-004 | E | Expose current availability, verified operations/CRS/extent/rights, config revision | D2 unverified metadata-only then scope/bbox/crs and generation, WMS/WFS caps; U1 exact rights | No explicit config revision apart from cache_generation; live sample vs persisted status, unknown fields. |
| R010/FR-005 | E | Unverified/revoked/wrong-rights operations denied, no fictitious flags | D2 wrong rights and revoke 403 zero calls; U1 default policy rejects exact mismatch; edit/offline false | Core command gating beyond Hub, all consumer operations and UI rights not fully tested. |
| R010/FR-006 | G | Save/reopen map with stable external logical Layer plus unchanged native refs | D2 reopened independent connection preview; not a R004 Map reference | No Core external logical layer binding or persistent external map composition. |
| R010/FR-007 | G | Attributable create/change/revoke history with old/new safe config; map detach independent | repository stores creator/time and increments cache_generation; migration 0013 separate records | No config change history, separate logical-layer detach or immutable owned raster asset dependency. |
| R010/FR-008 | E | Only exact operator policy can egress, arbitrary destination denied | U1 default-denial exact profile; D2 wrong endpoint/protocol/rights zero calls; D1 wrong host 403 | Ordinary project edit can create unverified metadata URL on org allowlist; require operator policy at actual registration if contract literal; no egress from unverified. |
| R010/FR-009 | E | Deny unapproved redirects/metadata link/tile template/operation | U1 redirects one call/no follow; U2 mismatch XYZ template/WMTS profile zero tile calls | No pagination links/secondary resource support; explicit multi-provider auth and full matrix. |
| R010/FR-010 | E | Network denials IPv4/IPv6 private, metadata, ambiguous encodings | D1 bad host 403; U1 mixed public+private 7 address cases zero connect/request | Transport IPv4-only accepted profile and static IPv6 refusal; full ambiguous encodings/IPv6 tests needed. |
| R010/FR-011 | E | DNS pin through actual peer and TLS identity; reject redirect/downgrade | U1 peer mismatch before TLS, TLS certificate error before HTTP, redirect refused, bounded DNS | Controlled socket/DNS/TLS seams, not actual independently TLS-served network or rebinding resolver acceptance. |
| R010/FR-012 | E | Nonsecret references shown masked; forbidden credential-bearing requests no forwarding | D1 has_secret_ref true, URL creds 403; D2 query token 403 absent from error; U1 safe endpoint strips query/userinfo, secret ref profile denied | Credentials deliberately unsupported; path-embedded arbitrary strings/diagnostic log and export matrix untested. |
| R010/FR-013 | E | Exact outbound destination/operation and no tenant feature data | U1 fixture request headers+fixed parameters; U3 no user bbox forwarded, Range/If-Match only; U2 fixed tile endpoint | Scope is adapter transport. Separate Core direct basemap path maplibre-engine.ts RASTER_LAYERS may expose tile ranges/referrer; separately approve/test browser provider routes. |
| R010/FR-014 | S | User sees geographic egress disclosure and operator can disable all external | PROFILE_ENV absent denies R010; ExternalSourcePreview scope attribution/rights labels | No explicit geographic disclosure warning or deploy-wide disable of direct HTTPS basemap behavior; human UX required. |
| R010/FR-015 | E | Exceeded bounded I/O/parser/concurrency returns explicit failure | U1 DNS deadline, media/oversize; U2 TIFF range cap; U3 max tile budget, expansion bomb, ETag/time constraints | No load stress proof of concurrency/range total and whole adapter latency/retry; bounded outcomes 502 generic. |
| R010/FR-016 | E | Reject malformed untrusted XML/JSON/PNG/TIFF and subresource/expansion | U1 DTD file entity, wrong metadata/image, duplicate JSON coords/counts; U3 invalid offsets and bomb | Additional malicious corpus, actual secondary subresources and independent fuzzer. |
| R010/FR-017 | E | Current scope rechecked on request/delivery/retry | D2 outsider/current no-grant denied zero calls, reopen fail 502 and no persisted success; D4 revoke zero egress; route rechecks approved_profile after read | Race permission revoke while in-flight response, cache flags at delivery and browser stale result test not executed. |
| R010/FR-018 | E | Unknown/protected results no retained provider cache; scope generation | D2/D4 Cache-Control no-store, repeat egress; list metadata unverified after proof | No retained cache contract (safe default); browser state and service worker exclusion policy/terms tests needed. |
| R010/FR-019 | E | Revocation/policy rights/cache generation invalidate protected results | U1 revoked/rights/disabled profile rejected; D2/D4 generation increments and revoke zero egress | Credential rotation/changed config/detach unsupported, in-flight race and cross-cache substitutions untested. |
| R010/FR-020 | E | Rendering rights not edit/export/offline/analysis, immutable snapshots explicit | U1/U2 caps exact metadata/render or WFS feature_read/query; D2 edit/offline false | No licensed immutable snapshot consumer workflow; all integrated export/analysis routes and rights matrix need proof. |
| R010/FR-021 | S | Provider attribution visible alongside pixels/features | ExternalSourcePreview displays preview.attribution/license_text; U1 returned fields exact | No browser fixture proving each displayed adapter attribution/rights and downstream use. |
| R010/FR-022 | E | WMS capabilities/layer/default style/CRS axis verified before usable | U1 test_wms_real_preview_bytes_and_request_parameters, test_xml_injection_wrong_layer_bbox_crs_and_image_rejected | WMS 1.1.1 fixed x/y sample only; config registration unverified prior validation, no other profile/version/axis or actionable specificity. |
| R010/FR-023 | E | Known control pixels/georeference/alpha and render-only | U1 PNG exact (12,34), (100,100), dimensions/CRS/bbox, transparent request; caps render only | Independent geographical alignment and actual transparent/no-data fixture not proven; Core viewport not available. |
| R010/FR-024 | S | Feature-info only advertised validated and permitted if implemented | Provider preview WMS returns render only, no query endpoints; tested U1 caps | No GetFeatureInfo implementation (optional); explicitly negative operation/API UI test. |
| R010/FR-025 | G | Owned raster immutable R005 asset checksum/source metadata/registration | COG provider.py and geotiff_provider.py only HTTP range of operator-approved remote object | No owned raster R005 lifecycle/checksum/retrieval; do not treat vector import as raster. |
| R010/FR-026 | E | Raster validates bbox/CRS/dimensions/bands/nodata before usable | U2 wrong CRS/georeference/offset refusal; U3 real GDAL grayscale/RGB, strict profile and invalid directory | No nodata/masks/alpha support (reject tags), owned publication absent; supported profiles need complete verification. |
| R010/FR-027 | E | Actual georeferenced display and valid/nodata distinction | U2 independent four colored quadrants; U3 all-pixel overview/native crop independent GDAL 4326/3857 | Nodata and transparency semantics unsupported; no Core display alignment. |
| R010/FR-028 | G | Long raster preparation durable job/progress/cancellation/retry atomic publication | COG bounded synchronous sample, no raster prep jobs | Implement explicit R005 raster artifact/job path and recovery. |
| R010/FR-029 | G | Owned raster original retrieval/export requires current permission and rights | No owned raster assets or export in R010 | Implement owned retrieval via accepted R005 contract or declare unsupported. |
| R010/FR-030 | E | WMTS/XYZ tile matrix extent zoom orientation and attribution verified | U2 fixed tile BBOX mathematical oracle, metadata mismatch test for matrix CRS/scale/limits and XYZ scheme/zoom/attribution | Only fixed z2/x3/y1 fixture and EPSG3857 canonical tile; full zoom-range and provider terms/profile acceptance. |
| R010/FR-031 | E | XYZ template exact operator approved, valid z/x/y substitutions only | U2 invalid_coordinates_bounds_origin; XYZ metadata mismatch refuses alternate template | No arbitrary tile viewport; positive/negative more zoom/origin edges. |
| R010/FR-032 | E | Invalid tile matrix/profile explicitly denied; no fallback | U2 wrong matrix/CRS/scale/limits fails before tile; static one fetch exact target | Missing/failed tile negative and browser no-fallback verification unrun. |
| R010/FR-033 | E | Collection schema/geometry/CRS/advertised operations/limits validated | U1 WFS 1.0.0 GetCapabilities selected type/query/CRS; exact feature response; rejects properties/CRS | No DescribeFeatureType schema/pin, OGC API Features or collection schema change handling. |
| R010/FR-034 | E | Bounded read bbox/max features and coordinate axis; reject arbitrary query | U1 fixture validates fixed BBOX, MAXFEATURES=100; geojson wrong axes/count/CRS denied | Pagination/continuation not supported; only approved sample. |
| R010/FR-035 | E | Preserve types/nulls/IDs/coordinate values and explicit partial | U1 exact fixture feature equality, invalid types/count/axes; _feature_collection returns preserved features | numberMatched/totalFeatures accepted then dropped, no explicit partial/unstable/count continuation. Fixed scope label does not certify completeness. |
| R010/FR-036 | E | Detect changed schema/availability; never claim native pinned snapshot | D2 reopen fresh success then outage 502, availability unverified in list; U1 invalid layer metadata rejects | Schema version changes, stable upstream identifier, unstable result handling not verified. |
| R010/FR-037 | E | Provider read-only, no WFS-T/materialization except immutable authorized import | U1 exact surfaced caps no edit; D2 edit/offline false; provider makes only GetCapabilities/GetFeature | No materialization workflow (safe unavailable), absence of provider write operation and consumer routes broader tests. |
| R010/FR-038 | E | Optional operations not inferred from protocol | D1 metadata-only for unverified; D2/D3/D4 fresh real proof and exact supported flags; U1-U3 tests | No all-optional consumer capability matrix, permanent Core gate not integrated. |
| R010/FR-039 | E | Categorized safe failures and actionable recovery | D2 missing 404, disabled/revoked 403, outage 502, invalid URL 403 without token; U3 wrong CRS/bounds 422/403 | Many parser/timeout/limit causes collapsed to generic 502; refine UI safe recovery reasons without revealing internals. |
| R010/FR-040 | G | Provider outage does not block native navigation/select/save | ExternalSourcePreview isolated in Hub; D2 service failure only that request | No mixed Core external/native map workflow or failure-isolation journey (blocked by missing map linkage). |
| R010/FR-041 | S | Atomic local registration, no partial ready, cleanup/recovery | create_connection DB transaction and unverified defaults; U3 no payload persist | No interruption/cancellation artifact lifecycle, repeated registration semantics or immutable raster assets. |
| R010/FR-042 | E | Declared protocol/version/CRS/rights matrix and independently verified benchmark fixtures | Provider/raster/COG slice docs exact supported matrix; U1-U3 independent pixels, D1-D4 protected route | No accepted benchmark profile latency and full per-slice operator/rights/reopen acceptance. |
| R010/SC-001 | E | Every slice authorized register/render/read/reopen/unsupported deny before exposure | D2–D4 register then protected actual sample; U1-U3 fixture validation; D2 reopen and revoked | No actual R004 map reopen, owned raster, full security/functional acceptance for every declared protocol. |
| R010/SC-002 | E | Control pixels, tile orientation and CRS/coordinate tolerance match independent oracle | U2 fixed WebMercator bbox and independent TIFF quadrants; U3 real GDAL full pixels EPSG4326 and 3857; U1 feature coordinates and controlled PNG | WMS absolute geospatial control point/alpha and all accepted fixture matrix. |
| R010/SC-003 | E | All unauthorized tenant/project/permission/revoke/stale/cache substitution deny | D2 wrong/no-grant/random IDs, revoked zero calls; D3 wrong actor; D4 wrong bounds/extras/CRS and revoke | Missing exhaustive stale and cache-substitution and concurrency/tenant-project permutations matrix. |
| R010/SC-004 | E | All malicious destinations/DNS/TLS/redirect/subresource/parser safely deny | U1 mixed addresses, peer/TLS mismatch, redirect, DTD, JSON/image limits; U2/3 range/matrix/bombs | Not full malicious coverage/actual TLS-service oracle; no live customer requests and no claim zero across untested paths. |
| R010/SC-005 | E | Denied cache/offline/export/unpinned excessive bounds, never claim completeness/editable | D2/D4 no-store, metadata-only; U3 out-of-bounds/over-budget refused; U1 exact read-only feature payload | WFS matched count dropped, full explicit incomplete/consumer rights matrix and immutable snapshot acceptance absent. |
| R010/SC-006 | G | All failure/cancellation/repetition preserve native work/assets and dependency separation | D2 failure no persistent success, G004 corrective evidence | No native mixed-flow and owned asset/layer/map lifecycle, cancel/recovery matrix. |
| R010/SC-007 | G | Controlled service cold/warm latency p95 and bounded over-limit | U1 deadline/size tests, U3 finite range budget | No approved R010 latency benchmark budgets or repeated runs. |
| R010/SC-008 | E | Authorized Core end-to-end for each adapter with visible rights/status | D2-D4 real protected API and U1-U3 pixels/read; ExternalSourcePreview shows rights | Browser all adapters, no live remote or actual mixed Core map layer/owned raster journey. API proof not human acceptance. |

## R011: forty-seven row oracles

| ID | Evidence | Required oracle | Actual assertion or static mapping | Residual / next test |
| --- | --- | --- | --- | --- |
| R011/FR-001 | E | Same project/organization boundary for collab records | C1 revoked current grant denies list/comment/decide, migration 0014 RLS and scoped SQL; C2 no-grant rebase denied | Cross-org and sibling project review/activity direct-ID matrix required. |
| R011/FR-002 | E | Reuse membership/grants/roles, not separate ACL | C1 viewer grant comment denied, editor grant review permitted, disabled user assignment 422 | Assignment SQL duplicates role-resolution logic; effective scope union and service/identity matrix. |
| R011/FR-003 | E | Every protected read/mutation enforces current permissions | C1 unassigned owner decision403, viewer comment403, revocation denied; C2 no-grant read rebase denied | Activity and history links/direct-ID queries/reapply full operation matrix. |
| R011/FR-004 | E | Revoking one grant preserves other effective permissions | A test_workspace_grant_inheritance_is_dynamic_and_project_grant_is_additive: workspace+project grant semantics (R002) | No collaboration-specific additive grant and revocation execution. |
| R011/FR-005 | E | Revoke existing session and deny historical assignee operation | C1 reviewer same client list/comment/decide denied after revoke | Same-session edit, activity/cursor and browser stale-view matrix. |
| R011/FR-006 | E | Viewer cannot edit/commit/assign/decide | C1 viewer comment403 and assignment without eligibility422; C2 no-grant rebase403; R006 reference edit forbidden | Viewer edit/assign/decide direct request and no side effects not all proven. |
| R011/FR-007 | E | Referenced history/data same current ownership and no grant via assignment | C1 historical assignment no residual access; C2 wrong feature anchor422, correct exact old rev | Separate resource/layer/revision existence/retire checks in activity and review lists. |
| R011/FR-008 | S | Switch org/project removes previous responses/selection | CollaborationWorkbenchPanel scoped prefix/query keys, currentProtectedData/matchingDetail; selected review only resolves from current scoped list | No explicit component remount key at Hub; delayed response and local selection/input clearing across context switches need browser oracle. |
| R011/FR-009 | E | Editing uses exact R006 atomic changeset revision identities and actor | C3 invalid bowtie422, valid create/update/delete changeset count3; C2 member second edit and same-actor replay | Two-actor complete journey with atomic rollback and attribution across all geometry types. |
| R011/FR-010 | E | Declared revision condition, stale/readonly denied | C3 stale409 STALE_CONTENT_REVISION current rev, read-only403; C2 unknown rebase history409 | Direct stale edit race and current permission matrix on all editable resource types. |
| R011/FR-011 | E | Incompatible same-base commits deterministic, no lost update | C3 second stale edit409, history length1 after replay/conflicts; C2 different actor cannot steal replay | Concurrent two-actor same-base edit race not tested; separate spatial/map CAS tests are not R006 feature edit races. |
| R011/FR-012 | E | Losing draft preserved and winning data unchanged | C3 stale error draft_preserved true/history1, revert/query restores originals; E2E native graphical stale draft journey previous checkpoint | Actually recover losing actor draft through re-read/reapply UI, durable no residual after revoke. |
| R011/FR-013 | E | Authorized inspect current revision conflicts and refresh/reapply/discard | C2 exact rev2 and safe/conflict feature sets across rev0,rev1,rev2; C3 stale metadata | No full conflicting values/geometry comparison or end-to-end explicit reapply/discard workflow. |
| R011/FR-014 | E | Reapply new attributable change from refreshed base | C2 editor second change from rev1 creates rev2; rebase report advisory no commit | Not a reapplication after losing draft/conflict. Add refresh and fresh validated changeset assertions. |
| R011/FR-015 | E | Nonoverlap preserved or conservative explicit conflict | C2 distinct p1/p2 sequential successful commits and exact reapplicable p1/new vs conflicts p2/p3/missing | No actual two stale concurrent disjoint edits/reapply; conservative conflict and explicit recovery test. |
| R011/FR-016 | E | Failed/no-op/conflict not success; retries reconcile exact operation | C3 invalid geometry422, same-id replay returns same ID, changed intent409 and history1; C2 foreign actor operation409 | Uncertain acknowledged/lost response and canceled draft browser tests for team edit. |
| R011/FR-017 | S | Interactive drafts do not hold long locks | editing repository atomic request transactions; EditingWorkbenchPage local draft state | Measure two interactive drafts session-independent and concurrent commit; no persistent-lock test. |
| R011/FR-018 | E | Map configuration vs data revision independent, private view selection/drafts | Map test_open_is_read_only_and_first_empty_save_has_exact_minimal_receipt, test_designated_viewpoint_preserve_clear_and_safe_history_pagination; C3 source rev changes | Cross-operation proof map rev unchanged by edit/review and private UI interactions not activity. |
| R011/FR-019 | G | Project activity includes exact committed change actor/time/revision | collaboration_repository._record_activity only review.requested/commented/decisions; editing_repository does not populate feed | Integrate authoritative editing history/events into feed; two-member exact event/actor/revision oracle. |
| R011/FR-020 | E | Distinguish review vs committed data, no draft/log-as-history | C4 review request/comment/approval then activity count>=3; event_kind exact code for review | Actual feed lacks committed data events; test exact event kinds/no drafts and editing events. |
| R011/FR-021 | G | Stable event ordering bounded pages with cutoff and reauth | list_activities ORDER BY created_at DESC LIMIT capped200; no id tie-break/cursor/cutoff | Stable keyset pagination/cutoff and permission changes, concurrent inserts tests. |
| R011/FR-022 | G | Filter inaccessible resource/count/actor/history details | Activities list by project only, metadata raw; no linked current resource/history validation; RLS confines project | Use current authorized historic resource scope and avoid restricted existence/counts; test mixed targets. |
| R011/FR-023 | S | Opening history/feature links reauthorize current access | CollaborationWorkbenchPanel getChangeset query requires matching source/current reviewed revision; currentProtectedData | Activity link navigation not implemented; direct denied/retired/delayed link matrix. |
| R011/FR-024 | E | Create optional review exact committed set and assigned eligible member | C1 create after grant, C2 create on old edit, C4 owner self-review 201 | Unassigned not supported; separate review-assignment permission and dedicated review eligibility contract absent. |
| R011/FR-025 | E | Review never draft/latest pointer; exact old rev | C2 old changeset after rev2, correct comment content_revision=rev1 | Test random/unknown/stale draft ID and later edit no inherited review state. |
| R011/FR-026 | E | Current human assignee eligibility at assign/act, auditable actor | C1 disabled/no-grant assignment422, grant success, owner cannot decide, reviewer actor, revoke denies | Assignment race/role union and lost eligibility across changes, separate permissions. |
| R011/FR-027 | E | Eligible comments/dispositions assigned only, unassigned and safe markup | C1 comment actor, assigned approved, owner forbidden, repeated decision409; B self-review display actual comment | Unassigned/reassign not implemented, comments allowed any project editor regardless assignee and completed status; bounded plain text React display static, markup test. |
| R011/FR-028 | S | Review action cannot modify geometry, attributes, grants/publication | decide_review/add_comment SQL touches only collab tables/events; C4 reviewer workflow | Independent before/after source/map revision+permissions assertion missing. |
| R011/FR-029 | E | Immutable attributable event/comments/history | C1 decided_by/author exact, repeated decision409; migration activities immutable trigger and comment insert-only privileges | No reassignment/correction event, exact audit timestamp/history completeness and DB immutability tests for collab. |
| R011/FR-030 | E | Concurrent review status guards current assignment/status, no overwrite | C1 owner forbidden, repeated decision409; decide_review SELECT FOR UPDATE and pending predicate under row lock | Actual simultaneous decision race, reassign/assignment CAS absent. |
| R011/FR-031 | E | Exact reviewed revision not latest | C2 comment rev1 after newer rev2; create_review copies resulting_content_revision from selected set | No later review status inheritance test and correction review journey. |
| R011/FR-032 | G | Needs-changes correction through new authorized change and new review | C3 edit supports new changeset; C1/C4 only approval; status enum changes_requested | No complete reject/repair/new review workflow and cross-revision verification. |
| R011/FR-033 | E | Member sees addressed review/current state/comment history, filtered paged | C1 viewer lists reviews200, C2 comments exact length1; B UI detail | list_reviews fixed100 no pagination, comments unbounded, no assignee filter. |
| R011/FR-034 | G | Coordinator reassign and old assignee loses access | C1 revoke denies historical assignee; no reassignment endpoint | Separate assignment semantics, CAS, auditable old/new reviewer and reassign ACL. |
| R011/FR-035 | E | Safe refresh/retry/resubmit with no duplicate events | C3/C2 change replay exact and owner same ID, wrong actor409; C1 duplicate decision409 | Review creation/comments lack idempotency key and duplicate event protection; no uncertain ack workflow. |
| R011/FR-036 | S | No public sharing/live cursors/CRDT/chat/long locks/notifications | Collaboration HTTP routes only project-scoped activities/reviews/comments/decision/rebase; no sharing/chat endpoints | Explicit negative public/guest access and draft privacy test. |
| R011/FR-037 | E | Post-commit review optional coordination, not publication | C1 commit succeeds before review; C2 review on old committed changeset; B actual review after change | No legal/approval gating/inherited status; ensure publication behavior unchanged after review. |
| R011/FR-038 | E | Supported actions tenant/current permissions and attribution, no vertical modules | C1/C2 real project scoped current grant/actor and exact revision; B Core workbench | Full R002/R006/R007 matrix and independent multi-user browser journeys. |
| R011/SC-001 | E | Two-member one-project viewer/editor edit then revoke, allowed/denied exact | C1 separate actors viewer vs editor and revoke review; C2 separate owner/member commits and actor replay denial | Not unified edit+revoke journey/no-mutation inspection of every fixture op; browser two-member run required. |
| R011/SC-002 | G | At least 20 simultaneous incompatible same-base edit races, exactly one winner | C3 stale sequential conflict; separate map/source/layer CAS tests not feature edit races | No 20 R006 races; create controlled independent actors/transactions and assert winning history/draft recovery. |
| R011/SC-003 | E | Attribute and geometry conflict recovery refresh/reapply/discard with distinct actor/revision evidence | C2 advisory rebase exact sets, C3 stale and revert exact data; E2E stale draft journey | No complete attribute+geometry losing drafts explicit reapplication/discard and history before/after matrix. |
| R011/SC-004 | E | Revoke/context-switch matrix all activity/review/links/save/reapply/cursor/delayed | C1 revoke review list/comment/decision; C2 no-grant rebase; A history current read test | No context-switch async matrix, activity paging or every route, zero leak not established. |
| R011/SC-005 | G | 50 commits fixture activity exact once cutoff across two members | C4 activity count>=3 review events only; no committed edit feed/cutoff | Implement feed+cursor, run >=50 multi-actor exact event oracle. |
| R011/SC-006 | E | Assignment/comment/disposition/correction/new review E2E, exact historic revision | C1 assigned reviewer comment/approval actor; C2 old revision feature anchor; B browser review | No correction/new review paired journey, later status not inherited untested. |
| R011/SC-007 | G | 20 concurrent review-state/assignment/repeated submissions including unassigned | C1 repeated decision409 sequential; row lock static | No unassigned/reassignment/20-race fixtures; review create/comment duplicates unresolved. |
| R011/SC-008 | E | Inaccessible missing stale revoked assignee/resource no restricted content | C1 no-grant/disabled assignee422, revoke denies; C2 invalid feature anchor422 and unknown ancestry409 | Missing wrong-review/foreign-source/missing history payload and activity resource matrix; confirm no metadata. |
| R011/SC-009 | E | Two members independently edit/recover and separate assigned review without admin repair | C2 owner/member commits and rebase inspection; C1 two authenticated actors actual assigned review; B single-actor browser | Not integrated two-member browser edit/conflict recovery plus assigned review without admin interventions. |

## Concrete follow-up priorities

1. R010 actual remote proofs are opt-in fixed operation slices: legitimate real
   pixel/feature payloads, default deny until every fresh request proof. But
   current logical layer/native Map integration and owned raster lifecycle are
   absent; fixed sample capability cannot be described as general external map
   support. Require approved synthetic provider fixture across all declared
   adapter profiles, no real outside or customer endpoints, independent TLS
   trust test and exact request scope, with current rights and no stale result.
   WFS result limitations are a specific actionable gap: numeric matched/total
   values are admitted but removed by normalization, so explicit partial or
   unstable response state needs a contract before broader query exposure.
   Direct browser basemaps are a separate path from the safe provider proxy
   and need their own operator/egress review.
2. R011 activity feed currently records coordination only (review requested,
   comment and decision; source changesets stored separately), so a 50-edit
   activity criterion is structurally unmet. Add authoritative commit
   projections and stable scope-aware ordering/cutoff/pagination; verify
   exact actor/revision/source/target, no drafts, no unauthorized existence
   leakage when linked resource unavailable.
3. Review supports real assigned current reviewers and immutable completed
   decisions. Original optional unassigned and reassign paths, assignment vs
   review permissions, bounded addressed listing/comment paging, duplicate
   create/comment reconciliation and simultaneous review-state fixtures are
   still absent. Require explicit scope decision and guarded state transitions.
4. Run original quantitative gates only after contracts are implemented:
   at least 20 concurrent same-base feature edit races, at least 20 concurrent
   review/assignment/repeated submission races, at least 50 edits with exact
   cutoff activity, two-member browser workflow and revocation/delayed/context
   switch matrix. No unrelated layer-CAS or single-actor test substitutes.
   No DB/browser service started here. No shared reconciliation register edited.
