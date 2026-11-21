// Isolated static fixture shell. Never proxies requests to a live API.
import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join, extname } from "node:path";
const root = fileURLToPath(new URL("../../apps/web/dist/", import.meta.url));
const files = new Map([["/index.html","index.html"],["/offline-shell-sw.js","offline-shell-sw.js"]]);
for (const name of await readdir(join(root,"assets"))) files.set("/assets/"+name, join("assets",name));
const mime = {".html":"text/html; charset=utf-8",".js":"text/javascript",".mjs":"text/javascript",".css":"text/css",".png":"image/png",".svg":"image/svg+xml"};
const server = createServer(async (req,res)=>{
  const path = new URL(req.url ?? "/", "http://127.0.0.1").pathname;
  const name = files.get(path) ?? (/^\/offline-field\/[^/]+\/[^/]+\/?$/.test(path) ? "index.html" : null);
  if (!name || req.method !== "GET") {
    res.writeHead(path.startsWith("/api/") ? 503 : 404);
    res.end("Static test server; no API forwarding.");
    return;
  }
  try {
    const bytes = await readFile(join(root,name));
    res.writeHead(200,{"Content-Type":mime[extname(name)] ?? "application/octet-stream","Cache-Control":"no-store"});
    res.end(bytes);
  } catch {res.writeHead(404);res.end();}
});
server.listen(5184,"127.0.0.1");
