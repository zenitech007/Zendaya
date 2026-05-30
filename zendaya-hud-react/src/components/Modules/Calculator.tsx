import { useState } from "react";
import ModulePanel from "./ModulePanel";

const BTNS = [
  ["C", "±", "%", "÷"],
  ["7", "8", "9", "×"],
  ["4", "5", "6", "−"],
  ["1", "2", "3", "+"],
  ["0", ".", "⌫", "="],
];

function evaluate(expr: string): string {
  const safe = expr
    .replace(/×/g, "*")
    .replace(/÷/g, "/")
    .replace(/−/g, "-");
  if (!/^[\d+\-*/.() ]+$/.test(safe)) return "ERR";
  try {
    // eslint-disable-next-line no-new-func
    const v = Function('"use strict";return (' + safe + ")")();
    if (typeof v === "number" && Number.isFinite(v)) {
      return String(Math.round(v * 1e10) / 1e10);
    }
    return "ERR";
  } catch {
    return "ERR";
  }
}

export default function Calculator() {
  const [expr, setExpr] = useState("");

  const press = (k: string) => {
    if (k === "C") return setExpr("");
    if (k === "⌫") return setExpr((s) => s.slice(0, -1));
    if (k === "=") return setExpr(evaluate(expr));
    if (k === "±") {
      if (expr.startsWith("-")) return setExpr(expr.slice(1));
      return setExpr("-" + expr);
    }
    setExpr((s) => s + k);
  };

  return (
    <ModulePanel title="Calculator">
      <div
        className="text-right text-2xl px-3 py-3 rounded mb-3 min-h-[2.5em]"
        style={{
          background: "rgba(0,0,0,0.5)",
          color: "#ffd9b8",
          fontFamily: '"Share Tech Mono", monospace',
          border: "1px solid rgba(255,138,60,0.18)",
        }}
      >
        {expr || "0"}
      </div>
      <div className="grid grid-cols-4 gap-2">
        {BTNS.flat().map((b) => {
          const isOp = ["÷", "×", "−", "+", "=", "%"].includes(b);
          const isFn = ["C", "±", "⌫"].includes(b);
          return (
            <button
              key={b}
              onClick={() => press(b)}
              className="h-12 rounded text-lg transition-all active:scale-95 hover:brightness-125"
              style={{
                background: isOp
                  ? "rgba(255,138,60,0.18)"
                  : isFn
                  ? "rgba(255,255,255,0.05)"
                  : "rgba(255,138,60,0.05)",
                color: isOp ? "#ff8a3c" : "#ffd9b8",
                border: "1px solid rgba(255,138,60,0.2)",
                fontFamily: '"Share Tech Mono", monospace',
              }}
            >
              {b}
            </button>
          );
        })}
      </div>
    </ModulePanel>
  );
}
