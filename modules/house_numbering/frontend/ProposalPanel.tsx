import {
  createHouseNumberingProposal,
  listHouseNumberingBuildings,
  listHouseNumberingRoutes,
  listHouseNumberingRules,
  transitionHouseNumberingProposal,
  type HouseNumberingProposal
} from "./api";
import { useState } from "react";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props = { organizationId: string; projectId: string };

export function ProposalPanel({ organizationId, projectId }: Props) {
  const rules = useReloadable(() => listHouseNumberingRules(hnClient, organizationId, projectId), [organizationId, projectId]);
  const routes = useReloadable(() => listHouseNumberingRoutes(hnClient, organizationId, projectId), [organizationId, projectId]);
  const buildings = useReloadable(() => listHouseNumberingBuildings(hnClient, organizationId, projectId), [organizationId, projectId]);
  const [routeId, setRouteId] = useState("");
  const [ruleId, setRuleId] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [proposal, setProposal] = useState<HouseNumberingProposal | null>(null);
  const [comment, setComment] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function transition(action: "submit" | "approve" | "reject") {
    if (!proposal) return;
    setError(null);
    try {
      await withCsrf(async () => {
        const updated = await transitionHouseNumberingProposal(hnClient, organizationId, projectId, proposal.id, {
          expected_revision: proposal.revision, action, comment: comment.trim() || null
        });
        setProposal(updated); setNotice(`Proposal: ${updated.status}.`);
      });
    } catch (err) { setError(await uiError(err)); }
  }

  return <section className="hn-card">
    <h2>Phương án và phê duyệt</h2>
    <div className="hn-form">
      <label>Tuyến<select value={routeId} onChange={(e) => setRouteId(e.target.value)}><option value="">Chọn tuyến</option>{(routes.data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      <label>Rule<select value={ruleId} onChange={(e) => setRuleId(e.target.value)}><option value="">Chọn rule</option>{(rules.data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.version} · {r.status}</option>)}</select></label>
    </div>
    <div className="hn-checks">{(buildings.data?.items ?? []).filter((b) => !routeId || b.route_id === routeId).map((b) => <label key={b.id}><input type="checkbox" checked={selected.includes(b.id)} onChange={(e) => setSelected((x) => e.target.checked ? [...x, b.id] : x.filter((id) => id !== b.id))} />{b.parcel_ref ?? b.id.slice(0, 8)}</label>)}</div>
    <div className="hn-form">
      <button className="hn-btn" type="button" disabled={!routeId || !ruleId || !selected.length} onClick={() => void (async () => {
        setError(null);
        try { await withCsrf(async () => { const result = await createHouseNumberingProposal(hnClient, organizationId, projectId, { scope_kind: "route", scope_id: routeId, rule_id: ruleId, building_ids: selected }); setProposal(result.proposal); setNotice("Đã tạo draft proposal."); }); } catch (err) { setError(await uiError(err)); }
      })()}>Tạo draft</button>
      <button className="hn-btn" type="button" disabled={!proposal || proposal.status !== "draft"} onClick={() => void transition("submit")}>Trình duyệt</button>
      <button className="hn-btn" type="button" disabled={!proposal || proposal.status !== "submitted"} onClick={() => void transition("approve")}>Phê duyệt</button>
      <button className="hn-btn danger" type="button" disabled={!proposal || proposal.status !== "submitted" || !comment.trim()} onClick={() => void transition("reject")}>Trả lại</button>
      <label>Ý kiến<textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Bắt buộc khi trả lại" /></label>
    </div>
    {proposal && <p>Proposal <code>{proposal.id}</code> · <span className="hn-badge">{proposal.status}</span> · revision {proposal.revision}</p>}
    {notice && <div className="hn-ok">{notice}</div>}{error && <div className="hn-error">{error}</div>}
  </section>;
}
