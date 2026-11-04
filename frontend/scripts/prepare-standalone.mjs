import { cpSync, mkdirSync, readdirSync, rmSync } from "node:fs";
// Remove only generated env copies: runtime secrets must not ship in images.
for (const name of readdirSync(".next/standalone")) {
  if (name === ".env" || name.startsWith(".env.")) rmSync(`.next/standalone/${name}`);
}
mkdirSync(".next/standalone/.next", { recursive: true });
cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
rmSync(".next/standalone/public", { recursive: true, force: true });
cpSync("public", ".next/standalone/public", { recursive: true });
