import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("renders without crashing", () => {
    const { container } = render(<Skeleton />);
    expect(container.firstChild).not.toBeNull();
  });

  it("has animate-pulse class by default", () => {
    const { container } = render(<Skeleton />);
    expect((container.firstChild as HTMLElement).className).toContain("animate-pulse");
  });

  it("applies custom className", () => {
    const { container } = render(<Skeleton className="h-4 w-full" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("h-4");
    expect(el.className).toContain("w-full");
  });

  it("merges custom className with defaults", () => {
    const { container } = render(<Skeleton className="my-custom" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain("animate-pulse");
    expect(el.className).toContain("my-custom");
  });
});
