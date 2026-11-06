// HTTPS reverse proxy in front of Open-LLM-VTuber.
// The app itself stays on http://127.0.0.1:12393.
// Phones on the home LAN use https://<this-computer>:12394
// The cert download page is plain HTTP on 12392, because the phone
// cannot trust the certificate until it has installed it.
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const tlsDir = path.join(root, "tls");
const helpFile = path.join(__dirname, "cert-help.html");

const TARGET_HOST = "127.0.0.1";
const TARGET_PORT = 12393;
const HELP_PORT = 12392;
const HTTPS_PORT = 12394;

const certFiles = {
  "/ca.cer": ["ca.cer", "application/x-x509-ca-cert"],
  "/ca.crt": ["ca.crt", "application/x-x509-ca-cert"],
  "/ca.mobileconfig": ["ca.mobileconfig", "application/x-apple-aspen-config"],
};

function sendFile(res, filePath, type) {
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("missing");
      return;
    }
    res.writeHead(200, {
      "Content-Type": type,
      "Content-Length": data.length,
      "Cache-Control": "no-store",
    });
    res.end(data);
  });
}

function serveCert(req, res) {
  const url = (req.url || "/").split("?")[0];
  if (url === "/cert-help.html") {
    sendFile(res, helpFile, "text/html; charset=utf-8");
    return true;
  }
  const spec = certFiles[url];
  if (spec) {
    sendFile(res, path.join(tlsDir, spec[0]), spec[1]);
    return true;
  }
  return false;
}

function proxyRequest(req, res) {
  const headers = { ...req.headers };
  const upstream = http.request(
    {
      host: TARGET_HOST,
      port: TARGET_PORT,
      method: req.method,
      path: req.url,
      headers,
    },
    (pres) => {
      res.writeHead(pres.statusCode || 502, pres.headers);
      pres.pipe(res);
    },
  );
  upstream.on("error", () => {
    if (!res.headersSent) {
      res.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" });
    }
    res.end("Open-LLM-VTuber 还没起来。先在电脑上打开 http://127.0.0.1:12393 确认服务在跑。");
  });
  req.pipe(upstream);
}

function proxyUpgrade(req, socket, head) {
  const upstream = net.connect(TARGET_PORT, TARGET_HOST, () => {
    let raw = `${req.method} ${req.url} HTTP/1.1\r\n`;
    for (const [key, value] of Object.entries(req.headers)) {
      if (Array.isArray(value)) {
        for (const item of value) raw += `${key}: ${item}\r\n`;
      } else if (value != null) {
        raw += `${key}: ${value}\r\n`;
      }
    }
    raw += "\r\n";
    upstream.write(raw);
    if (head && head.length) upstream.write(head);
    upstream.pipe(socket);
    socket.pipe(upstream);
  });
  const kill = () => {
    socket.destroy();
    upstream.destroy();
  };
  upstream.on("error", kill);
  socket.on("error", kill);
}

const help = http.createServer((req, res) => {
  const url = (req.url || "/").split("?")[0];
  if (url === "/") {
    sendFile(res, helpFile, "text/html; charset=utf-8");
    return;
  }
  if (!serveCert(req, res)) {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("这个地址只用来下载家里的证书。通话请打开 https:// 那一个端口。");
  }
});

const secure = https.createServer(
  {
    key: fs.readFileSync(path.join(tlsDir, "server.key")),
    cert: fs.readFileSync(path.join(tlsDir, "server.crt")),
    minVersion: "TLSv1.2",
  },
  (req, res) => {
    if (!serveCert(req, res)) proxyRequest(req, res);
  },
);
secure.on("upgrade", (req, socket, head) => {
  proxyUpgrade(req, socket, head);
});

help.listen(HELP_PORT, "0.0.0.0", () => {
  console.log(`cert help  http://0.0.0.0:${HELP_PORT}/cert-help.html`);
});
secure.listen(HTTPS_PORT, "0.0.0.0", () => {
  console.log(`https proxy https://0.0.0.0:${HTTPS_PORT}/`);
});
