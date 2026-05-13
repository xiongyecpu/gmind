import { cp, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");

await mkdir(dist, { recursive: true });
await cp(join(root, "index.html"), join(dist, "index.html"));
await cp(join(root, "src", "main.js"), join(dist, "main.js"));
await cp(join(root, "src", "styles.css"), join(dist, "styles.css"));
await cp(join(root, "src", "assets", "icon.png"), join(dist, "icon.png"));
await cp(join(root, "src", "assets", "gmind-menubar.svg"), join(dist, "gmind-menubar.svg"));
await cp(join(root, "src", "assets", "gmind-menubar.png"), join(dist, "gmind-menubar.png"));
