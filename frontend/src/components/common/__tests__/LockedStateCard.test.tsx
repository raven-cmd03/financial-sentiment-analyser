import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LockedStateCard from "@/components/common/LockedStateCard";

describe("LockedStateCard", () => {
  it("renders the default locked message", () => {
    render(<LockedStateCard />);
    expect(screen.getByText(/Admin features are locked/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Configuration guide/i }),
    ).toBeInTheDocument();
  });

  it("renders a retry button when onRetry is provided", () => {
    const onRetry = vi.fn();
    render(
      <LockedStateCard
        title="Chat is locked"
        description="Configure API_KEY"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByText("Chat is locked")).toBeInTheDocument();

    const retry = screen.getByRole("button", { name: /Retry/i });
    fireEvent.click(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not show a retry button when onRetry is omitted", () => {
    render(<LockedStateCard />);
    expect(
      screen.queryByRole("button", { name: /Retry/i }),
    ).not.toBeInTheDocument();
  });
});
