import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it("renders a non-color label for running jobs", () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText("Đang chạy")).toBeInTheDocument();
  });

  it("falls back to draft for an unknown state", () => {
    render(<StatusBadge status="future-state" />);
    expect(screen.getByText("Bản nháp")).toBeInTheDocument();
  });
});

