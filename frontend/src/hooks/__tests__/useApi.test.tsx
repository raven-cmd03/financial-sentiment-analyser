import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "@/hooks/useApi";
import { ApiLockedError } from "@/api/client";

describe("useApi", () => {
  it("returns data on success", async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 42 });
    const { result } = renderHook(() => useApi(() => fetcher(), []));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ value: 42 });
    expect(result.current.error).toBeNull();
    expect(result.current.locked).toBe(false);
  });

  it("sets locked=true on ApiLockedError", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValue(new ApiLockedError(401, "API key required"));
    const { result } = renderHook(() => useApi(() => fetcher(), []));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.locked).toBe(true);
    expect(result.current.error).toBe("API key required");
    expect(result.current.data).toBeNull();
  });

  it("surfaces other errors without locking", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("Network boom"));
    const { result } = renderHook(() => useApi(() => fetcher(), []));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.locked).toBe(false);
    expect(result.current.error).toBe("Network boom");
  });
});
