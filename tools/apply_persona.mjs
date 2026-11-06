// Put one 人格工坊 card onto the phone call.
// Usage: node tools/apply_persona.mjs 汐
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { __test } from "file:///D:/DPH/deepseek-intro/render/node_modules/@local/dsh-persona/index.js";

const root = "D:/DPH/video-call";
const name = process.argv[2] || "汐";
const store = JSON.parse(
  readFileSync("C:/Users/admin/.dsh/storages/dsh_persona.json", "utf8"),
);
const persona = Object.values(store.tables.personas).find((item) => item.name === name);
if (!persona) {
  const names = Object.values(store.tables.personas).map((item) => item.name);
  throw new Error(`没有这张卡。现有：${names.join("、")}`);
}

const card = __test.compileCard({ ...persona, useMemes: false });
const call = [
  "你正在和主人打电话。对面就是主人本人：他说话你听得见，他打开摄像头时你看得见这一帧。",
  "用口语回，一次一两句，像打电话，不要写成文章，不要用 markdown，不要列清单。",
  "不要发表情包，这通电话没有表情包工具。脸上的表情只用后面给出的方括号关键词，说出口的话里不要念出方括号。",
  "不要提起人格卡、人格工坊或这段设定本身。",
  "",
  card,
].join("\n");

const confPath = join(root, "conf.yaml");
let text = readFileSync(confPath, "utf8");
text = text.replace("conf_name: 'mao_pro'", "conf_name: 'xi'");
text = text.replace("conf_uid: 'mao_pro_001'", "conf_uid: 'xi_call_001'");
text = text.replace("character_name: 'Mao'", `character_name: '${name}'`);
text = text.replace("human_name: 'Human'", "human_name: '主人'");
const start = text.indexOf("  persona_prompt: |");
const end = text.indexOf("\n  #  ===================", start);
if (start < 0 || end < 0) throw new Error("conf.yaml 里找不到 persona_prompt");
const indented = call
  .split("\n")
  .map((line) => (line.length ? `    ${line}` : ""))
  .join("\n");
text = `${text.slice(0, start)}  persona_prompt: |\n${indented}\n${text.slice(end)}`;
writeFileSync(confPath, text, "utf8");

const alt = [
  "character_config:",
  `  conf_name: "${name}"`,
  '  conf_uid: "xi_call_001"',
  `  character_name: "${name}"`,
  '  human_name: "主人"',
  "  persona_prompt: |",
  indented,
  "",
].join("\n");
writeFileSync(join(root, "characters", "zh_汐.yaml"), alt, "utf8");
console.log(`applied ${name} chars ${call.length}`);
