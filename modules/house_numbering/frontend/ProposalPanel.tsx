import {
  createHouseNumberingProposal,
  listHouseNumberingBuildingLineage,
  listHouseNumberingBuildings,
  listHouseNumberingRoutes,
  listHouseNumberingRules,
  recordHouseNumberingBuildingLineage,
  setHouseNumberingPlaqueStatus,
  transitionHouseNumberingProposal,
  type HouseNumberingBuilding,
  type HouseNumberingBuildingLineage,
  type HouseNumberingProposal
} from "./api";
import { useState } from "react";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props = { organizationId: string; projectId: string };

export function ProposalPanel({ organizationId, projectId }: Props) {
  const rules = useReloadable(
    () => listHouseNumberingRules(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const routes = useReloadable(
    () => listHouseNumberingRoutes(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const buildings = useReloadable(
    () => listHouseNumberingBuildings(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );

  const [routeId, setRouteId] = useState("");
  const [ruleId, setRuleId] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [proposal, setProposal] = useState<HouseNumberingProposal | null>(null);
  const [comment, setComment] = useState("");

  const [plaqueBuildingId, setPlaqueBuildingId] = useState("");
  const [plaqueStatus, setPlaqueStatus] =
    useState<HouseNumberingBuilding["plaque_status"]>("planned");

  const [lineageKind, setLineageKind] = useState<"split" | "merge">("split");
  const [predecessors, setPredecessors] = useState<string[]>([]);
  const [successors, setSuccessors] = useState<string[]>([]);
  const [historyBuildingId, setHistoryBuildingId] = useState("");
  const [history, setHistory] = useState<HouseNumberingBuildingLineage[]>([]);

  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function guarded(action: () => Promise<void>) {
    setError(null);
    try {
      await withCsrf(action);
    } catch (err) {
      setError(await uiError(err));
    }
  }

  async function transition(action: "submit" | "withdraw" | "approve" | "reject") {
    if (!proposal) return;
    await guarded(async () => {
      const updated = await transitionHouseNumberingProposal(
        hnClient,
        organizationId,
        projectId,
        proposal.id,
        {
          expected_revision: proposal.revision,
          action,
          comment: comment.trim() || null
        }
      );
      setProposal(updated);
      setNotice(`Proposal: ${updated.status}.`);
    });
  }

  async function updatePlaque() {
    const building = buildings.data?.items.find(
      (item) => item.id === plaqueBuildingId
    );
    if (!building) return;
    await guarded(async () => {
      await setHouseNumberingPlaqueStatus(
        hnClient,
        organizationId,
        projectId,
        building.id,
        {
          expected_revision: building.revision,
          status: plaqueStatus
        }
      );
      setNotice(`Đã cập nhật trạng thái biển: ${plaqueStatus}.`);
      await buildings.reload();
    });
  }

  async function recordLineage() {
    const items = buildings.data?.items ?? [];
    const participantIds = [...new Set([...predecessors, ...successors])];
    const expectedRevisions = Object.fromEntries(
      participantIds.map((id) => {
        const building = items.find((item) => item.id === id);
        return [id, building?.revision ?? 0];
      })
    );
    await guarded(async () => {
      const result = await recordHouseNumberingBuildingLineage(
        hnClient,
        organizationId,
        projectId,
        {
          relation_kind: lineageKind,
          operation_id: crypto.randomUUID(),
          predecessor_building_ids: predecessors,
          successor_building_ids: successors,
          expected_revisions: expectedRevisions
        }
      );
      setNotice(
        `Đã ghi ${lineageKind} với ${result.items.length} cạnh lineage. Số cũ không tự chuyển sang công trình mới.`
      );
      await buildings.reload();
      const focus = successors[0] ?? predecessors[0];
      if (focus) {
        const rows = await listHouseNumberingBuildingLineage(
          hnClient,
          organizationId,
          projectId,
          focus
        );
        setHistoryBuildingId(focus);
        setHistory(rows.items);
      }
    });
  }

  async function loadHistory(buildingId: string) {
    setHistoryBuildingId(buildingId);
    if (!buildingId) {
      setHistory([]);
      return;
    }
    try {
      const rows = await listHouseNumberingBuildingLineage(
        hnClient,
        organizationId,
        projectId,
        buildingId
      );
      setHistory(rows.items);
    } catch (err) {
      setError(await uiError(err));
    }
  }

  function toggle(
    current: string[],
    setCurrent: (value: string[]) => void,
    id: string,
    checked: boolean
  ) {
    setCurrent(checked ? [...current, id] : current.filter((value) => value !== id));
  }

  return (
    <>
      <section className="hn-card">
        <h2>Phương án và phê duyệt</h2>
        <div className="hn-form">
          <label>
            Tuyến
            <select value={routeId} onChange={(e) => setRouteId(e.target.value)}>
              <option value="">Chọn tuyến</option>
              {(routes.data?.items ?? []).map((route) => (
                <option key={route.id} value={route.id}>
                  {route.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Rule
            <select value={ruleId} onChange={(e) => setRuleId(e.target.value)}>
              <option value="">Chọn rule</option>
              {(rules.data?.items ?? []).map((rule) => (
                <option key={rule.id} value={rule.id}>
                  {rule.version} · {rule.status}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="hn-checks">
          {(buildings.data?.items ?? [])
            .filter((building) => !routeId || building.route_id === routeId)
            .map((building) => (
              <label key={building.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(building.id)}
                  onChange={(e) =>
                    setSelected((current) =>
                      e.target.checked
                        ? [...current, building.id]
                        : current.filter((id) => id !== building.id)
                    )
                  }
                />
                {building.parcel_ref ?? building.id.slice(0, 8)}
              </label>
            ))}
        </div>
        <div className="hn-form">
          <button
            className="hn-btn"
            type="button"
            disabled={!routeId || !ruleId || !selected.length}
            onClick={() =>
              void guarded(async () => {
                const result = await createHouseNumberingProposal(
                  hnClient,
                  organizationId,
                  projectId,
                  {
                    scope_kind: "route",
                    scope_id: routeId,
                    rule_id: ruleId,
                    building_ids: selected
                  }
                );
                setProposal(result.proposal);
                setNotice("Đã tạo draft proposal.");
              })
            }
          >
            Tạo draft
          </button>
          <button
            className="hn-btn"
            type="button"
            disabled={!proposal || proposal.status !== "draft"}
            onClick={() => void transition("submit")}
          >
            Trình duyệt
          </button>
          <button
            className="hn-btn secondary"
            type="button"
            disabled={
              !proposal || proposal.status !== "submitted" || !comment.trim()
            }
            onClick={() => void transition("withdraw")}
          >
            Rút trình
          </button>
          <button
            className="hn-btn"
            type="button"
            disabled={!proposal || proposal.status !== "submitted"}
            onClick={() => void transition("approve")}
          >
            Phê duyệt
          </button>
          <button
            className="hn-btn danger"
            type="button"
            disabled={
              !proposal || proposal.status !== "submitted" || !comment.trim()
            }
            onClick={() => void transition("reject")}
          >
            Trả lại
          </button>
          <label>
            Ý kiến
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Bắt buộc khi trả lại"
            />
          </label>
        </div>
        {proposal ? (
          <p>
            Proposal <code>{proposal.id}</code> ·{" "}
            <span className="hn-badge">{proposal.status}</span> · revision{" "}
            {proposal.revision}
          </p>
        ) : null}
      </section>

      <section className="hn-card">
        <h2>Trạng thái gắn biển</h2>
        <div className="hn-form">
          <label>
            Công trình
            <select
              value={plaqueBuildingId}
              onChange={(e) => setPlaqueBuildingId(e.target.value)}
            >
              <option value="">Chọn công trình</option>
              {(buildings.data?.items ?? []).map((building) => (
                <option key={building.id} value={building.id}>
                  {building.parcel_ref ?? building.id.slice(0, 8)} ·{" "}
                  {building.plaque_status}
                </option>
              ))}
            </select>
          </label>
          <label>
            Trạng thái
            <select
              value={plaqueStatus}
              onChange={(e) =>
                setPlaqueStatus(
                  e.target.value as HouseNumberingBuilding["plaque_status"]
                )
              }
            >
              <option value="not_planned">Chưa kế hoạch</option>
              <option value="planned">Đã lên kế hoạch</option>
              <option value="installed">Đã gắn</option>
              <option value="replaced">Đã thay/cấp lại</option>
              <option value="removed">Đã tháo</option>
            </select>
          </label>
          <button
            className="hn-btn"
            type="button"
            disabled={!plaqueBuildingId}
            onClick={() => void updatePlaque()}
          >
            Cập nhật biển
          </button>
        </div>
        <p className="hn-muted">
          Gắn/thay biển chỉ được phép khi công trình có số approved.
        </p>
      </section>

      <section className="hn-card">
        <h2>Tách / gộp công trình</h2>
        <div className="hn-form">
          <label>
            Nghiệp vụ
            <select
              value={lineageKind}
              onChange={(e) => {
                setLineageKind(e.target.value as "split" | "merge");
                setPredecessors([]);
                setSuccessors([]);
              }}
            >
              <option value="split">Tách 1 → nhiều</option>
              <option value="merge">Gộp nhiều → 1</option>
            </select>
          </label>
        </div>
        <h3>Công trình nguồn</h3>
        <div className="hn-checks">
          {(buildings.data?.items ?? []).map((building) => (
            <label key={"pre-" + building.id}>
              <input
                type="checkbox"
                checked={predecessors.includes(building.id)}
                onChange={(e) =>
                  toggle(
                    predecessors,
                    setPredecessors,
                    building.id,
                    e.target.checked
                  )
                }
              />
              {building.parcel_ref ?? building.id.slice(0, 8)}
            </label>
          ))}
        </div>
        <h3>Công trình mới</h3>
        <div className="hn-checks">
          {(buildings.data?.items ?? []).map((building) => (
            <label key={"succ-" + building.id}>
              <input
                type="checkbox"
                checked={successors.includes(building.id)}
                onChange={(e) =>
                  toggle(successors, setSuccessors, building.id, e.target.checked)
                }
              />
              {building.parcel_ref ?? building.id.slice(0, 8)}
            </label>
          ))}
        </div>
        <button
          className="hn-btn"
          type="button"
          disabled={
            lineageKind === "split"
              ? predecessors.length !== 1 || successors.length < 2
              : predecessors.length < 2 || successors.length !== 1
          }
          onClick={() => void recordLineage()}
        >
          Ghi tách/gộp
        </button>
        <p className="hn-muted">
          Ledger chỉ ghi quan hệ và đóng công trình nguồn. Số cũ được giữ lịch sử;
          công trình mới phải qua preview/proposal riêng.
        </p>
      </section>

      <section className="hn-card">
        <h2>Lịch sử tách/gộp</h2>
        <label>
          Công trình
          <select
            value={historyBuildingId}
            onChange={(e) => void loadHistory(e.target.value)}
          >
            <option value="">Chọn công trình</option>
            {(buildings.data?.items ?? []).map((building) => (
              <option key={building.id} value={building.id}>
                {building.parcel_ref ?? building.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        <table className="hn-table">
          <thead>
            <tr>
              <th>Loại</th>
              <th>Nguồn</th>
              <th>Đích</th>
              <th>Operation</th>
            </tr>
          </thead>
          <tbody>
            {history.map((item) => (
              <tr key={item.id}>
                <td>{item.relation_kind}</td>
                <td>{item.predecessor_building_id.slice(0, 8)}</td>
                <td>{item.successor_building_id.slice(0, 8)}</td>
                <td>
                  <code>{item.operation_id.slice(0, 8)}</code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {notice ? <div className="hn-ok">{notice}</div> : null}
      {error ? <div className="hn-error">{error}</div> : null}
    </>
  );
}
