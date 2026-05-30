import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import ModulePanel from "./ModulePanel";
const STORAGE_KEY = "zendaya.hud.notes";
export default function Notes() {
    const [text, setText] = useState("");
    useEffect(() => {
        try {
            const v = localStorage.getItem(STORAGE_KEY);
            if (v != null)
                setText(v);
        }
        catch {
            /* ignore */
        }
    }, []);
    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, text);
        }
        catch {
            /* ignore */
        }
    }, [text]);
    return (_jsxs(ModulePanel, { title: "Notes", children: [_jsx("textarea", { value: text, onChange: (e) => setText(e.target.value), placeholder: "Write something\u2026", spellCheck: false, className: "w-full h-64 p-3 rounded resize-none focus:outline-none", style: {
                    background: "rgba(0,0,0,0.5)",
                    color: "#ffd9b8",
                    fontFamily: '"Share Tech Mono", monospace',
                    fontSize: "0.9em",
                    lineHeight: 1.5,
                    border: "1px solid rgba(255,138,60,0.18)",
                } }), _jsxs("div", { className: "text-xs mt-2 text-right tracking-widest", style: { color: "rgba(255,138,60,0.55)" }, children: [text.length, " chars \u00B7 autosaved"] })] }));
}
