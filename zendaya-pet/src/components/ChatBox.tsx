import { useState, type FormEvent } from "react";
import { postChat } from "../lib/api";

interface Props {
  connected: boolean;
}

export default function ChatBox({ connected }: Props) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const msg = value.trim();
    if (!msg || pending) return;
    setPending(true);
    setValue("");
    try {
      await postChat(msg);
    } catch {
      // The hook will flip `connected` on next poll. Restoring the
      // input lets the user retry without retyping.
      setValue(msg);
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="w-full flex gap-2"
    >
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={
          connected ? "Talk to Zendaya…" : "Backend offline — start zendaya.py"
        }
        disabled={!connected || pending}
        className="flex-1 bg-black/40 backdrop-blur-md rounded-2xl border border-white/15 text-white placeholder-white/50 px-4 py-2 outline-none focus:border-white/40 transition disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={!connected || pending || value.trim() === ""}
        className="rounded-2xl border border-white/15 bg-white/10 backdrop-blur-md text-white px-4 py-2 hover:bg-white/20 disabled:opacity-40 transition"
      >
        {pending ? "…" : "Send"}
      </button>
    </form>
  );
}
