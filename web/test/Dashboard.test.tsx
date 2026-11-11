import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App, Dashboard } from "../src/app/App";
import { fixture } from "./fixture";

const ok = (body: unknown) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) } as Response);
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("states", () => {
  it("shows a skeleton while loading", () => {
    render(<App fetcher={() => new Promise<Response>(() => {})} />);
    expect(screen.getByRole("status", { name: "Loading results" })).toBeTruthy();
  });

  it("explains a failure and retries", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({ ok: false, status: 500 } as Response).mockImplementation(() => ok(fixture));
    render(<App fetcher={fetcher as unknown as (u: string) => Promise<Response>} />);
    expect((await screen.findByRole("alert")).textContent).toContain("500");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeTruthy());
  });

  it("names the command for every missing piece", () => {
    render(<Dashboard summary={{ ...fixture, hero: null, ops: { dev: null, heldout: null }, pricing: { dev: null, heldout: null }, causal: null, sensing: { dev: null, heldout: null }, gate: null }} />);
    expect(screen.getAllByText(/^make /, { selector: "code" }).length).toBeGreaterThanOrEqual(6);
  });
});

describe("content", () => {
  it("scrubs the street map by hour and plays the day", () => {
    vi.useFakeTimers();
    render(<Dashboard summary={fixture} />);
    expect(screen.getByText("08:00")).toBeTruthy();
    fireEvent.change(screen.getByRole("slider", { name: "Hour" }), { target: { value: "18" } });
    expect(screen.getByText("18:00")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Play the day" }));
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.getByText("20:00")).toBeTruthy();
  });

  it("shows the hold decision for the planner and the gate", () => {
    render(<Dashboard summary={fixture} />);
    expect(screen.getAllByText(/hold: keep the heuristic/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Not met: ops: planner beats heuristic/)).toBeTruthy();
  });

  it("falls back to the dev city when the held-out city is not scored", () => {
    render(<Dashboard summary={fixture} />);
    expect(screen.getByRole("radio", { name: "Dev city" }).getAttribute("aria-checked")).toBe("true");
  });
});
