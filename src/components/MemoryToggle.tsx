// src/components/MemoryToggle.tsx
import React from "react";

type Props = {
  allowed: boolean;
  onChange: (val: boolean) => void;
};

export const MemoryToggle: React.FC<Props> = ({ allowed, onChange }) => {
  return (
    <div className="flex items-center gap-3">
      <label className="text-sm">Allow Zendaya to remember (opt-in)</label>
      <input
        type="checkbox"
        checked={allowed}
        onChange={(e) => onChange(e.target.checked)}
        aria-label="Allow memory"
      />
    </div>
  );
};
