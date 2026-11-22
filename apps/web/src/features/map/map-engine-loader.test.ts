import { describe, expect, it, vi } from "vitest";
import { createModuleLoader } from "./map-engine-loader";

describe("shared static map engine module loader", () => {
  it("does not eagerly request a renderer; concurrent callers share one import", async () => {
    let resolve: (factory: { factory: string }) => void = () => {};
    const request = vi.fn(() => new Promise<{ factory: string }>(r => { resolve = r; }));
    const load = createModuleLoader(request);
    expect(request).not.toHaveBeenCalled();
    const first = load();
    expect(load()).toBe(first);
    expect(request).toHaveBeenCalledTimes(1);
    const module = { factory: "only static code" };
    resolve(module);
    expect(await first).toBe(module);
    expect(await load()).toBe(module);
    expect(request).toHaveBeenCalledTimes(1);
  });
  it("does not keep a permanently rejected loader promise", async () => {
    const request = vi.fn<() => Promise<string>>()
      .mockRejectedValueOnce(new Error("chunk unavailable"))
      .mockResolvedValueOnce("renderer");
    const load = createModuleLoader(request);
    await expect(load()).rejects.toThrow("chunk unavailable");
    await expect(load()).resolves.toBe("renderer");
    expect(request).toHaveBeenCalledTimes(2);
  });
});
