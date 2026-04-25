// server/remoteScorer.js
const express = require("express");
const fetch = require("node-fetch");
const bodyParser = require("body-parser");
const app = express();
app.use(bodyParser.json());

app.post("/score-wake", async (req, res) => {
  const { transcript } = req.body;
  if (!transcript) return res.status(400).json({ error: "missing transcript" });

  // Example prompt: keep short, ask model for wake probability
  const prompt = `Rate how likely the following phrase is intended to wake an assistant. Return a JSON: {"score":0.0} with score 0..1 only.\n\nPhrase: """${transcript}"""`;

  try {
    // Replace below with your LLM provider call (OpenAI/GPT-mini etc)
    const llmResp = await fetch("https://api.example-llm.com/v1/generate", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.LLM_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt, max_tokens: 20 }),
    });
    const json = await llmResp.json();
    // parse model reply heuristically
    let text = (json.choices?.[0]?.text || json.output || "").toString();
    const m = text.match(/{"score"\s*:\s*([0-9.]+)/);
    let score = 0.0;
    if (m) score = parseFloat(m[1]);
    else {
      // fallback: if text contains "likely" etc
      score = /likely|yes|true/.test(text) ? 0.85 : 0.15;
    }
    res.json({ score });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "scoring failed" });
  }
});

app.listen(3001, () => console.log("remoteScorer listening on :3001"));
