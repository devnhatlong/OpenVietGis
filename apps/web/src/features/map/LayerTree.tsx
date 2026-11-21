import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";

import {
  createLayerCommands,
  invokeLayerCommand,
  type LayerCommandId
} from "./commands";
import { buildLayerPanelItemView } from "./layer-view";
import { capability, previewMove } from "./workspace";

function geometryLabel(value: string): string {
  return {
    Point: "Điểm",
    LineString: "Đường",
    Polygon: "Vùng"
  }[value] ?? value;
}

export function LayerTree({
  layers,
  metadata,
  active,
  locked,
  states,
  change,
  choose,
  zoom,
  openAddData
}: {
  layers: MapLayerReference[];
  metadata: (SpatialLayer | undefined)[];
  active: string | null;
  locked: boolean;
  states: string[];
  change: (layers: MapLayerReference[]) => void;
  choose: (id: string) => void;
  zoom: (id: string) => void;
  openAddData: () => void;
}) {
  return (
    <aside className="map-layers" aria-label="Danh sách lớp bản đồ">
      <div className="map-layer-panel-head">
        <div>
          <h2>
            Lớp dữ liệu <span className="map-badge">{layers.length}/32</span>
          </h2>
          <p>Thứ tự trên xuống tương ứng với thứ tự hiển thị trên bản đồ.</p>
        </div>
        <button
          type="button"
          className="map-add-data-trigger"
          disabled={locked}
          onClick={openAddData}
        >
          + Thêm dữ liệu
        </button>
      </div>

      {!layers.length ? (
        <div className="map-layer-empty">
          <strong>Chưa có lớp dữ liệu trên bản đồ</strong>
          <span>
            Thêm một lớp đã có trong danh mục hoặc nhập dữ liệu mới để bắt đầu.
          </span>
          <button type="button" disabled={locked} onClick={openAddData}>
            Thêm dữ liệu
          </button>
        </div>
      ) : null}

      <ol>
        {layers.map((reference, index) => {
          const layer = metadata[index];
          const view = buildLayerPanelItemView(
            reference,
            layer,
            states[index] ?? "loading",
            active,
            index,
            layers.length
          );
          const commands = createLayerCommands(
            {
              name: view.name,
              canZoom: view.canZoom,
              canMoveUp: view.canMoveUp,
              canMoveDown: view.canMoveDown,
              visible: view.visible,
              canRemove: view.canRemove,
              locked,
              disabledReason: view.disabledReason
            },
            (id: LayerCommandId) => {
              if (id === "layer.zoom") zoom(reference.layer_id);
              if (id === "layer.move-up")
                change(previewMove(layers, reference.layer_id, -1));
              if (id === "layer.move-down")
                change(previewMove(layers, reference.layer_id, 1));
              if (id === "layer.toggle-visibility")
                change(
                  layers.map((item) =>
                    item.layer_id === reference.layer_id
                      ? { ...item, visible: !item.visible }
                      : item
                  )
                );
              if (id === "layer.remove")
                change(
                  layers.filter(
                    (item) => item.layer_id !== reference.layer_id
                  )
                );
            }
          );

          const zoomCommand = commands.find((item) => item.id === "layer.zoom");
          const upCommand = commands.find((item) => item.id === "layer.move-up");
          const downCommand = commands.find(
            (item) => item.id === "layer.move-down"
          );
          const visibilityCommand = commands.find(
            (item) => item.id === "layer.toggle-visibility"
          );
          const removeCommand = commands.find(
            (item) => item.id === "layer.remove"
          );

          return (
            <li
              key={reference.layer_id}
              data-testid={"map-layer-" + reference.layer_id}
              className={view.active ? "is-active" : ""}
            >
              <div className="map-layer-title">
                <input
                  type="checkbox"
                  aria-label={"Hiển thị " + view.name}
                  checked={reference.visible}
                  disabled={!visibilityCommand?.enabled}
                  onChange={() =>
                    invokeLayerCommand(commands, "layer.toggle-visibility")
                  }
                />
                <button
                  type="button"
                  aria-label={"Chọn " + view.name + " làm lớp hiện hành"}
                  aria-pressed={view.active}
                  onClick={() => choose(reference.layer_id)}
                >
                  {view.name}
                </button>
              </div>

              <div className="map-layer-summary">
                <span
                  className={"map-layer-state is-" + view.availability}
                  data-testid={"viewport-state-" + reference.layer_id}
                  data-state={view.availability}
                >
                  {view.availabilityLabel}
                </span>
                {layer ? (
                  <span>
                    {geometryLabel(layer.source.schema.geometry_family)}
                    {" · "}
                    {layer.source.stored_crs
                      ? "EPSG:" + layer.source.stored_crs.code
                      : "CRS chưa xác định"}
                  </span>
                ) : null}
              </div>

              <div className="map-layer-tools">
                <button
                  type="button"
                  disabled={!zoomCommand?.enabled}
                  title={zoomCommand?.reason ?? undefined}
                  aria-label={"Thu phóng tới " + view.name}
                  onClick={() => invokeLayerCommand(commands, "layer.zoom")}
                >
                  Thu phóng
                </button>
                <button
                  type="button"
                  disabled={!upCommand?.enabled}
                  title={upCommand?.reason ?? undefined}
                  aria-label={"Đưa " + view.name + " lên trên"}
                  onClick={() => invokeLayerCommand(commands, "layer.move-up")}
                >
                  ↑
                </button>
                <button
                  type="button"
                  disabled={!downCommand?.enabled}
                  title={downCommand?.reason ?? undefined}
                  aria-label={"Đưa " + view.name + " xuống dưới"}
                  onClick={() =>
                    invokeLayerCommand(commands, "layer.move-down")
                  }
                >
                  ↓
                </button>
                <button
                  type="button"
                  disabled={!removeCommand?.enabled}
                  title={removeCommand?.reason ?? undefined}
                  aria-label={"Gỡ " + view.name + " khỏi bản đồ"}
                  onClick={() => invokeLayerCommand(commands, "layer.remove")}
                >
                  Gỡ
                </button>
              </div>

              <details>
                <summary>Tùy chỉnh hiển thị</summary>
                <fieldset disabled={locked || !capability(layer, "style")}>
                  <label>
                    Màu sắc{" "}
                    <input
                      type="color"
                      aria-label={"Màu sắc " + view.name}
                      data-testid={"color-" + reference.layer_id}
                      value={reference.style.color}
                      onChange={(event) =>
                        change(
                          layers.map((item) =>
                            item.layer_id === reference.layer_id
                              ? {
                                  ...item,
                                  style: {
                                    ...item.style,
                                    color: event.target.value
                                  }
                                }
                              : item
                          )
                        )
                      }
                    />
                  </label>
                  {(["opacity", "width", "radius"] as const).map((key) => {
                    const label =
                      key === "opacity"
                        ? "Độ mờ"
                        : key === "width"
                          ? "Độ rộng"
                          : "Bán kính";
                    return (
                      <label key={key}>
                        {label}
                        <input
                          type="range"
                          aria-label={label + " " + view.name}
                          min={key === "opacity" ? 0 : key === "width" ? 1 : 2}
                          max={key === "opacity" ? 1 : key === "width" ? 12 : 20}
                          step={key === "opacity" ? 0.1 : 1}
                          value={reference.style[key]}
                          onChange={(event) =>
                            change(
                              layers.map((item) =>
                                item.layer_id === reference.layer_id
                                  ? {
                                      ...item,
                                      style: {
                                        ...item.style,
                                        [key]: Number(event.target.value)
                                      }
                                    }
                                  : item
                              )
                            )
                          }
                        />
                        <output>{reference.style[key]}</output>
                      </label>
                    );
                  })}
                </fieldset>
              </details>

              {layer ? (
                <details className="map-layer-technical">
                  <summary>Thông tin kỹ thuật</summary>
                  <dl>
                    <dt>Mã lớp</dt>
                    <dd><code>{layer.id}</code></dd>
                    <dt>Mã nguồn</dt>
                    <dd><code>{layer.source_id}</code></dd>
                  </dl>
                </details>
              ) : null}
            </li>
          );
        })}
      </ol>

      <p className="map-muted">
        Sắp xếp và kiểu hiển thị chỉ là cấu hình bản đồ. Dữ liệu nguồn không bị
        thay đổi.
      </p>
    </aside>
  );
}
