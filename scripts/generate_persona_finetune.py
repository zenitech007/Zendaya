"""
Generate persona finetune dataset from conversation memories.
This script reads memories stored by the backend and produces
a JSONL dataset that can be used for offline finetuning.
"""

import json
import os
from datetime import datetime

MEMORY_DIR = "zendaya_backend/data/memory"
OUTPUT_FILE = "zendaya_backend/data/persona_finetune.jsonl"

os.makedirs("zendaya_backend/data", exist_ok=True)

def load_memories():
    memories = []
    if not os.path.exists(MEMORY_DIR):
        print(f"No memory directory found at {MEMORY_DIR}")
        return memories

    for file in os.listdir(MEMORY_DIR):
        if not file.endswith(".json"):
            continue
        try:
            with open(os.path.join(MEMORY_DIR, file), "r", encoding="utf-8") as f:
                entries = json.load(f)
                memories.extend(entries if isinstance(entries, list) else [entries])
        except Exception as e:
            print(f"Error loading memory file {file}: {e}")

    return memories

def convert_to_finetune_format(memories):
    dataset = []
    for m in memories:
        prompt = m.get("user_message", "")
        response = m.get("zendaya_reply", "")

        if not prompt or not response:
            continue
        
        dataset.append({
            "prompt": prompt,
            "response": response,
            "timestamp": m.get("time", datetime.utcnow().isoformat())
        })

    return dataset

def save_dataset(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row) + "\n")

    print(f"✅ Persona finetune dataset saved to {OUTPUT_FILE}")
    print(f"📦 {len(data)} samples exported")

if __name__ == "__main__":
    memories = load_memories()
    if not memories:
        print("⚠️ No memories found yet. Talk to Zendaya first!")
    else:
        dataset = convert_to_finetune_format(memories)
        save_dataset(dataset)
