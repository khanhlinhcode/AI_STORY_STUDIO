import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SceneCard } from "@/components/scene-card";

const scene = {
  id: "scene-1",
  episode_id: "episode-1",
  order_index: 0,
  synopsis: "Mimi mở chiếc ô cho Tí.",
  duration_ms: 8200,
  current_revision_id: "revision-1",
};

describe("SceneCard", () => {
  it("exposes selection state and calls its action", () => {
    const onSelect = vi.fn();
    render(<SceneCard scene={scene} selected onSelect={onSelect} />);
    const button = screen.getByRole("button", { pressed: true });
    fireEvent.click(button);
    expect(onSelect).toHaveBeenCalledOnce();
    expect(screen.getByText("Mimi mở chiếc ô cho Tí.")).toBeInTheDocument();
  });
});

