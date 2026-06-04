export type ParsedCommand =
  | { kind: "slash"; name: string; args: string[] }
  | { kind: "chat"; text: string };

/** Split a raw input line into a slash command or a chat message.
 *  Returns null for empty input (caller should no-op). A lone "/" → /help. */
export function parseCommand(input: string): ParsedCommand | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("/")) {
    const body = trimmed.slice(1).trim();
    if (!body) return { kind: "slash", name: "help", args: [] };
    const parts = body.split(/\s+/);
    return { kind: "slash", name: parts[0].toLowerCase(), args: parts.slice(1) };
  }
  return { kind: "chat", text: trimmed };
}
