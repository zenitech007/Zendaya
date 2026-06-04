import { useEffect, useRef, useState } from "react";
import { useZendaya } from "../../store/zendayaStore";
import { parseCommand } from "../../commands/parseCommand";
import { runSlash } from "../../commands/slashRegistry";
import { sendChat } from "../../api/backend";
import { useCommandHotkey } from "../../hooks/useCommandHotkey";

const OFFLINE_MSG = "⚠ can't reach Zendaya (is the backend running?)";

export default function CommandTerminal() {
  useCommandHotkey();

  const open = useZendaya((s) => s.terminalOpen);
  const log = useZendaya((s) => s.terminalLog);
  const text = useZendaya((s) => s.text);
  const connected = useZendaya((s) => s.connected);
  const push = useZendaya((s) => s.pushTerminalLine);

  const [input, setInput] = useState("");
  const awaiting = useRef(false);
  const prevText = useRef(text);
  const inputRef = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  // Echo Zendaya's reply (broadcast as `text`) into the transcript once, after
  // a chat line was submitted. Ignores the value present at mount.
  useEffect(() => {
    if (text !== prevText.current) {
      prevText.current = text;
      if (awaiting.current && text) {
        push("zendaya", text);
        awaiting.current = false;
      }
    }
  }, [text, push]);

  // Focus the input + scroll to the latest line when opened or on new lines.
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log.length]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = parseCommand(input);
    if (!parsed) return;
    push("user", input.trim());
    setInput("");
    if (parsed.kind === "slash") {
      push("system", runSlash(parsed.name, parsed.args));
      return;
    }
    // chat
    if (!connected) {
      push("system", OFFLINE_MSG);
      return;
    }
    awaiting.current = true;
    sendChat(parsed.text).catch(() => {
      awaiting.current = false;
      push("system", OFFLINE_MSG);
    });
  }

  if (!open) return null;

  return (
    <div className="zen-terminal" data-testid="command-terminal">
      <div className="zen-terminal-log" ref={logRef}>
        {log.length === 0 && (
          <div className="zen-terminal-line-system">
            Type a command or talk to Zendaya. Try <strong>/help</strong>.
          </div>
        )}
        {log.map((line) => (
          <div key={line.id} className={`zen-terminal-line-${line.role}`}>
            {line.role === "user" ? "› " : line.role === "zendaya" ? "Zendaya: " : ""}
            {line.text}
          </div>
        ))}
      </div>
      <form className="zen-terminal-form" onSubmit={handleSubmit}>
        <span className="zen-terminal-prompt">›</span>
        <input
          ref={inputRef}
          data-testid="command-input"
          className="zen-terminal-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={connected ? "message or /command…" : "offline — /commands still work"}
          autoComplete="off"
          spellCheck={false}
        />
      </form>
    </div>
  );
}
