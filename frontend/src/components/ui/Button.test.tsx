import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeDefined();
  });

  it("shows a spinner when loading", () => {
    render(<Button loading>Saving</Button>);
    const button = screen.getByRole("button");
    expect(button.querySelector(".animate-spin")).not.toBeNull();
  });

  it("is disabled when loading", () => {
    render(<Button loading>Saving</Button>);
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>Submit</Button>);
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("does not show spinner when not loading", () => {
    render(<Button>Submit</Button>);
    expect(screen.getByRole("button").querySelector(".animate-spin")).toBeNull();
  });

  it("calls onClick when clicked", async () => {
    const handler = vi.fn();
    render(<Button onClick={handler}>Go</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(handler).toHaveBeenCalledOnce();
  });
});
