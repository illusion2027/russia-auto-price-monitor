import http from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
const root = process.env.STATIC_DIR
  ? resolve(process.env.STATIC_DIR)
  : resolve(fileURLToPath(new URL("../public/", import.meta.url)));
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".webmanifest": "application/manifest+json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
};
const port = Number(process.env.PORT || 4173);
http
  .createServer(async (req, res) => {
    try {
      let path = decodeURIComponent(
        new URL(req.url, "http://localhost").pathname,
      );
      path = path.replace(/^\/russia-auto-price-monitor(?=\/|$)/, "");
      if (path.endsWith("/")) path += "index.html";
      const target = resolve(root, "." + path);
      if (target !== root && !target.startsWith(root + sep)) {
        res.writeHead(403);
        return res.end("Forbidden");
      }
      const body = await readFile(target);
      res.writeHead(200, {
        "Content-Type": mime[extname(target)] || "application/octet-stream",
        "Cache-Control": "no-cache",
      });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end("Not found");
    }
  })
  .listen(port, "127.0.0.1", () =>
    console.log(`Local: http://127.0.0.1:${port}/russia-auto-price-monitor/`),
  );
