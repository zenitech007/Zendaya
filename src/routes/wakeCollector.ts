// server/collect.js
const express = require("express");
const bodyParser = require("body-parser");
const fs = require("fs");
const app = express();
app.use(bodyParser.json({ limit: "1mb" }));

app.post("/collect-wake-example", (req, res) => {
  const { transcript, label } = req.body;
  if (!transcript) return res.status(400).send("missing transcript");
  const entry = { transcript, label: label ? 1 : 0, ts: Date.now() };
  fs.appendFileSync("./wake_examples.ndjson", JSON.stringify(entry) + "\n");
  res.json({ ok: true });
});

app.listen(3002, () => console.log("collector on :3002"));
