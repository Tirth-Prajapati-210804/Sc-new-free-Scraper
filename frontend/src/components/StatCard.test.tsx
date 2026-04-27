import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Database } from "lucide-react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("renders the label", () => {
    render(<StatCard label="Total Prices" value={42} icon={Database} />);
    expect(screen.getByText("Total Prices")).toBeDefined();
  });

  it("renders a numeric value", () => {
    render(<StatCard label="Total Prices" value={42} icon={Database} />);
    expect(screen.getByText("42")).toBeDefined();
  });

  it("renders a string value", () => {
    render(<StatCard label="Coverage" value="87.5%" icon={Database} />);
    expect(screen.getByText("87.5%")).toBeDefined();
  });
});
