import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, "dist");

await mkdir(dist, { recursive: true });
const index = await readFile(join(root, "index.html"), "utf8");
await writeFile(
  join(dist, "index.html"),
  index
    .replace('href="src/styles.css"', 'href="styles.css"')
    .replace('src="src/assets/icon.png"', 'src="icon.png"')
    .replace('src="src/i18n.js"', 'src="i18n.js"')
    .replace('src="src/main.js"', 'src="main.js"'),
);
await cp(join(root, "src", "i18n.js"), join(dist, "i18n.js"));
await cp(join(root, "src", "main.js"), join(dist, "main.js"));
await cp(join(root, "src", "styles.css"), join(dist, "styles.css"));
await cp(join(root, "src", "assets", "icon.png"), join(dist, "icon.png"));
await cp(join(root, "src", "assets", "gmind-logo.png"), join(dist, "gmind-logo.png"));
await cp(join(root, "src", "assets", "gmind-logo.svg"), join(dist, "gmind-logo.svg"));
await cp(join(root, "src", "assets", "gmind-mark.svg"), join(dist, "gmind-mark.svg"));
await cp(join(root, "src", "assets", "gmind-menubar.svg"), join(dist, "gmind-menubar.svg"));
await cp(join(root, "src", "assets", "gmind-menubar.png"), join(dist, "gmind-menubar.png"));
