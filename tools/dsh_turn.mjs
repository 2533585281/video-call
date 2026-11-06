// One phone turn into an existing DSH session.
// stdin: { sessionId, baseUrl, text, images }
// stdout: the assistant text only
import * as nodeCrypto from "node:crypto";
import { readFileSync } from "node:fs";
import WebSocket from "ws";
import { NodeApiClient, unwrap, createTurnCollector } from "file:///D:/DPH/surfcore/src/dsh-client.js";

globalThis.WebSocket = WebSocket;
if (typeof globalThis.crypto?.randomUUID !== "function") {
  globalThis.crypto = Object.assign(globalThis.crypto ?? {}, {
    randomUUID: nodeCrypto.randomUUID,
  });
}

function discoverBaseUrl(preferred) {
  const found = [];
  if (preferred) found.push(String(preferred).replace(/\/+$/, ""));
  try {
    const log = readFileSync(
      "C:/Users/admin/.dsh/surfcore/bridge-supervisor.log",
      "utf8",
    );
    const matches = [...log.matchAll(/DSH=(http:\/\/127\.0\.0\.1:\d+)/g)];
    if (matches.length) found.push(matches[matches.length - 1][1]);
  } catch {
    // The bridge log is only a hint. A configured address can still work.
  }
  return [...new Set(found)];
}

const raw = await new Promise((resolve, reject) => {
  const chunks = [];
  process.stdin.on("data", (chunk) => chunks.push(chunk));
  process.stdin.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
  process.stdin.on("error", reject);
});
const input = JSON.parse(raw);
const sessionId = String(input.sessionId || "");
const candidates = discoverBaseUrl(input.baseUrl);
if (!sessionId) throw new Error("missing sessionId");
if (!candidates.length) throw new Error("DSH address not found");

const phone = [
  "【视频电话】这是主人在视频电话里说的，不是 QQ 消息。",
  "用口语回一两句，方便直接念出来。",
  "表情只能用这些词，写在方括号里，不要念出来：[neutral] [joy] [smirk] [sadness] [anger] [fear] [surprise] [disgust]。",
  "不要调用 QQ 发送工具。",
  "",
  input.text || "（他打开了摄像头，没有说话）",
].join("\n");

const content = [{ type: "text", text: phone }];
for (const url of input.images || []) {
  const match = String(url).match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/);
  if (!match) continue;
  content.push({
    type: "image",
    mediaType: match[1],
    data: match[2],
    name: "camera.jpg",
  });
}

let api = null;
let lastError = null;
for (const baseUrl of candidates) {
  const client = new NodeApiClient(baseUrl);
  try {
    unwrap(await client.settings.describe({}), "settings.describe");
    api = client;
    break;
  } catch (error) {
    lastError = error;
  }
}
if (!api) throw lastError ?? new Error("DSH is not running");
const collector = createTurnCollector();
let resolveOpened;
const opened = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("DSH websocket timed out")), 10000);
  resolveOpened = () => {
    clearTimeout(timer);
    resolve();
  };
});
const stream = api.events.mux({}, undefined, () => resolveOpened());
const done = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error("DSH reply timed out")), 110000);
  (async () => {
    for await (const envelope of stream) {
      const frame = envelope.payload;
      if (frame.type === "session/event" && frame.sessionId === sessionId) {
        const ended = collector.push(frame.event);
        if (ended) {
          clearTimeout(timer);
          resolve(ended);
          return;
        }
      }
      if (frame.type === "stream/error") {
        clearTimeout(timer);
        reject(new Error("DSH event stream error"));
        return;
      }
    }
    clearTimeout(timer);
    reject(new Error("DSH event stream closed"));
  })().catch((error) => {
    clearTimeout(timer);
    reject(error);
  });
});

await opened;
stream.follow(sessionId);
const accepted = unwrap(
  await api.sessions.prompt({
    sessionId,
    mode: "queue",
    content,
  }),
  "session.prompt",
);
if (accepted?.command?.text) {
  process.stdout.write(String(accepted.command.text));
  process.exit(0);
}
const ended = await done;
process.stdout.write(ended.text || "");
process.exit(ended.text ? 0 : 2);
