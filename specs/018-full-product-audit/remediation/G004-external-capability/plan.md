# Plan: G004 capability truth

1. Pin separately coordinated implementation branch; preserve baseline failing probe.
2. Implement evidence-backed capability/availability policy and non-destructive legacy metadata treatment. Update API consumers and UI labels; unverified sources cannot be rendered/read as working.
3. Review original security/rights/metadata scope and define controlled reference provider + independent response oracle for each approved slice, not arbitrary public URL. Verify destination validation at connect and redirect, resource bounds, parser safety, cache/auth lifecycle.
4. Deliver only approved and independently verified adapter slices. Keep unsupported slices disabled. Test actual map layer rendering/reading, reopen, revocation, unsupported operations and cross-tenant negatives.
5. Rerun G004 probes, full security and browser acceptance; close only with independent exact-candidate evidence. No deployment under audit.
