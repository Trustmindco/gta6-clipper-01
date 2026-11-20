// main.ts — entry program for make.fun bounty gta6-clipper-01
// ("Clip GTA 6 for the most YouTube views"). Node 22, standard library only.
//
// What the house grades is the video itself: its address sits in VIDEO.json
// at this repository's root, and the house reads the video's views through
// the YouTube Data API. This program's whole job, when the house runs it in
// its sandbox, is to hand that file over: copy VIDEO.json from the
// repository directory to the output directory.
//
// Locally the same run looks like:
//   mkdir -p out && MAKEFUN_BOT_DIR=. MAKEFUN_OUTPUT_DIR=out node main.ts
// MAKEFUN_BOT_DIR names the repository directory (the grader mounts it at
// /bot) and MAKEFUN_OUTPUT_DIR the output directory (the grader's /output).

import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const botDir = process.env.MAKEFUN_BOT_DIR ?? "/bot";
const outputDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";

const source = join(botDir, "VIDEO.json");
const target = join(outputDir, "VIDEO.json");

if (!existsSync(source)) {
  console.error(`main.ts: no VIDEO.json at ${source}; nothing to hand over`);
  process.exit(1);
}

mkdirSync(outputDir, { recursive: true });
copyFileSync(source, target);
console.log(`main.ts: copied ${source} -> ${target}`);
