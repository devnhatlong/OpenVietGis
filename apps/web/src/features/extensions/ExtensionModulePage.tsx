import { listExtensionManifests, listProjectActivations } from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../../app/api";
import { getOfficialModuleFrontend } from "./registry";

export function ExtensionModulePage() {
  const { organizationId = "", projectId = "", extensionKey = "" } = useParams();
  const activations = useQuery({
    queryKey: ["extensions", organizationId, projectId, "activations"],
    queryFn: () => listProjectActivations(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId),
    staleTime: 0,
    refetchOnMount: "always"
  });
  const manifests = useQuery({
    queryKey: ["extensions", organizationId, "manifests"],
    queryFn: () => listExtensionManifests(apiClient, organizationId),
    enabled: Boolean(organizationId),
    staleTime: 0,
    refetchOnMount: "always"
  });
  const frontend = getOfficialModuleFrontend(extensionKey);
  const active = activations.data?.items.find(
    (item) => item.extension_key === extensionKey && item.status === "active"
  );
  const manifest = manifests.data?.items.find(
    (item) => item.id === active?.manifest_id && item.extension_key === extensionKey
  );

  if (activations.isLoading || manifests.isLoading) {
    return <main className="ovg-suite-body"><p>Đang kiểm tra trạng thái module…</p></main>;
  }
  if (!active || !manifest) {
    return (
      <main className="ovg-suite-body">
        <section className="ovg-card">
          <h1>Module chưa được kích hoạt</h1>
          <p>Module này không hoạt động trong dự án hiện tại hoặc quyền truy cập đã thay đổi.</p>
          <Link to={`/organizations/${organizationId}/projects/${projectId}/platform-hub`}>
            Quay lại Nền tảng
          </Link>
        </section>
      </main>
    );
  }
  if (!frontend) {
    return (
      <main className="ovg-suite-body">
        <section className="ovg-card">
          <h1>{manifest.display_name}</h1>
          <p>Backend module đã hoạt động nhưng gói giao diện tương ứng không có trong bản build này.</p>
        </section>
      </main>
    );
  }
  const Component = frontend.Component;
  return <Component organizationId={organizationId} projectId={projectId} />;
}
