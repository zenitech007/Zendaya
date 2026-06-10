interface Props {
  text: string;
}

export default function SpeechBubble({ text }: Props) {
  if (!text) return null;
  return (
    <div className="absolute top-[12%] right-4 max-w-[60%] pointer-events-none">
      <div className="relative bg-white/95 text-zinc-800 rounded-2xl rounded-bl-none px-4 py-2 shadow-2xl text-sm leading-snug">
        {text}
        <span
          aria-hidden
          className="absolute -bottom-2 left-3 w-3 h-3 bg-white/95 transform rotate-45"
        />
      </div>
    </div>
  );
}
