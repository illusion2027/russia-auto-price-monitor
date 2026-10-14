import { cp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
const root = new URL("../", import.meta.url),
  dist = new URL("dist/", root);
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });
await cp(new URL("public/", root), dist, { recursive: true });
const current = JSON.parse(
  await readFile(new URL("data/current.json", dist), "utf8"),
);
if (current.schema_version !== 1 || !current.models.length)
  throw new Error(
    "Missing/invalid generated data. Run python -m monitor.publish first.",
  );
const hash = createHash("sha256");
for (const file of [
  "index.html",
  "app.js",
  "lib.js",
  "styles.css",
  "data/current.json",
  "data/history.json",
])
  hash.update(await readFile(new URL(file, dist)));
const sw = await readFile(new URL("sw.js", dist), "utf8");
await writeFile(
  new URL("sw.js", dist),
  sw.replace("__BUILD_ID__", hash.digest("hex").slice(0, 16)),
);
await writeFile(new URL(".nojekyll", dist), "");
console.log(
  `Static build ready: ${current.models.length} models. Relative URLs support /russia-auto-price-monitor/.`,
);
