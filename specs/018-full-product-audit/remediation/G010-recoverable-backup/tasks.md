# Tasks: G010 recoverable backup
- [ ] B001 Coordinate branch/base, approved recovery profile and consistency strategy.
- [ ] B002 Establish failing independent empty-artifact-root restoration test with synthetic required files.
- [ ] B003 Inventory required asset/source/derived references and explicit exclusions/lifecycle; protect staged snapshot.
- [ ] B004 Implement snapshot covering DB plus required bytes/checksums and atomic complete marker.
- [ ] B005 Validate manifest/path safety and isolated never-overwrite restore; fail closed on corruption or incompleteness.
- [ ] B006 Restore data and assets into new targets; verify counts/digests, exact required bytes, authorized workflow downloads.
- [ ] B007 Verify current identity/authorization reconciliation and interrupted job recovery; negative tenant/revocation and duplicate publication tests.
- [ ] B008 Record RPO/RTO measurements against separately approved profile targets, review full candidate, close G010 only with complete evidence.
