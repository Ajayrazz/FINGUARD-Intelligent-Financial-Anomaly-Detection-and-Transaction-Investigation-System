import type { Plugin } from "vite";

/**
 * echarts-gl (through claygl) turns strings such as "expr(width * 1.0 / 2)" into functions with `new Function(...)`.
 * A strict Content-Security-Policy (no 'unsafe-eval', see docker/caddy/Caddyfile) blocks that, which would break every
 * 3D chart in production. This plugin swaps that one call for a tiny arithmetic evaluator that never evaluates strings
 * as code. The grammar covers exactly what echarts-gl uses: numbers, width/height/dpr, + - * /, parentheses and
 * array literals like "[width * 1.0, height * 1.0]".
 */
export const SAFE_EXPR_SOURCE = `
function __safeExpr(src) {
  var toks = src.match(/\\d+\\.?\\d*|[A-Za-z_]+|[-+*/()\\[\\],]/g) || [];
  var pos = 0;
  function peek() { return toks[pos]; }
  function next() { return toks[pos++]; }
  function expr() {
    var left = term();
    while (peek() === "+" || peek() === "-") { var op = next(); var right = term(); left = bin(op, left, right); }
    return left;
  }
  function term() {
    var left = factor();
    while (peek() === "*" || peek() === "/") { var op = next(); var right = factor(); left = bin(op, left, right); }
    return left;
  }
  function bin(op, a, b) {
    return function (w, h, d) {
      var x = a(w, h, d), y = b(w, h, d);
      return op === "+" ? x + y : op === "-" ? x - y : op === "*" ? x * y : x / y;
    };
  }
  function factor() {
    var t = next();
    if (t === undefined) throw new Error("Invalid expression.");
    if (t === "-") { var f = factor(); return function (w, h, d) { return -f(w, h, d); }; }
    if (t === "(") { var e = expr(); if (next() !== ")") throw new Error("Invalid expression."); return e; }
    if (t === "[") {
      var items = [expr()];
      while (peek() === ",") { next(); items.push(expr()); }
      if (next() !== "]") throw new Error("Invalid expression.");
      return function (w, h, d) { return items.map(function (i) { return i(w, h, d); }); };
    }
    if (/^\\d/.test(t)) { var n = parseFloat(t); return function () { return n; }; }
    if (t === "width") return function (w) { return w; };
    if (t === "height") return function (w, h) { return h; };
    if (t === "dpr") return function (w, h, d) { return d; };
    throw new Error("Invalid expression.");
  }
  var fn = expr();
  if (pos !== toks.length) throw new Error("Invalid expression.");
  fn(1, 1, 1);
  return fn;
}
`;

const TARGET = "new Function('width', 'height', 'dpr', 'return ' + exprRes[1])";

export function claygNoEval(): Plugin {
  return {
    name: "claygl-no-eval",
    enforce: "pre",
    transform(code, id) {
      if (!id.includes("claygl") || !code.includes(TARGET)) return null;
      return {
        code:
          code.replace(TARGET, "__safeExpr(exprRes[1])") +
          "\n" +
          SAFE_EXPR_SOURCE,
        map: null,
      };
    },
  };
}
