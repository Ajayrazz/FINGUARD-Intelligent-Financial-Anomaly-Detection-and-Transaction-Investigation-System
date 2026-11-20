import { describe, expect, it } from "vitest";
import { SAFE_EXPR_SOURCE } from "./claygl-no-eval";

// the test (not the app) may use Function to load the evaluator source that the plugin injects into the bundle
const make = new Function(`${SAFE_EXPR_SOURCE}; return __safeExpr;`)() as (
  s: string,
) => (w: number, h: number, d: number) => unknown;

describe("claygl safe expression evaluator", () => {
  it("evaluates every expression form echarts-gl uses", () => {
    expect(make("width * 1.0 / 2")(800, 600, 2)).toBe(400);
    expect(make("height * 1.0 / 4")(800, 600, 2)).toBe(150);
    expect(make(" [width * 1.0, height * 1.0] ")(800, 600, 2)).toEqual([
      800, 600,
    ]);
    expect(make("[width * 1.0 / 2, height / 2]")(800, 600, 1)).toEqual([
      400, 300,
    ]);
    expect(make("(width + 2) * dpr - -1")(10, 0, 2)).toBe(25);
  });
  it("rejects anything that is not plain arithmetic, so no string is ever run as code", () => {
    for (const bad of [
      "alert(1)",
      "width; 1",
      "constructor",
      "width +",
      "((width)",
      "this.x",
      "1 ? 2 : 3",
      "[1,",
      "width.length",
    ]) {
      expect(() => make(bad), bad).toThrow("Invalid expression.");
    }
  });
});
