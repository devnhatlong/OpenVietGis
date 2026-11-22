/** Share the static renderer chunk, never a map instance or protected data. */
export function createModuleLoader<T>(request: () => Promise<T>): () => Promise<T> {
  let pending: Promise<T> | undefined;
  return () => {
    if (!pending) {
      pending = request().catch(error => {
        pending = undefined;
        throw error;
      });
    }
    return pending;
  };
}

export const loadMapEngine = createModuleLoader(() => import("./maplibre-engine"));
export type MapEngineFactory = Awaited<ReturnType<typeof loadMapEngine>>["createMapLibreEngine"];
