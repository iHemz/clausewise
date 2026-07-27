import fs from "fs";
import path from "path";

// Scan the Next.js app only; the Python API uses ruff + PEP 8.
const ROOT_DIR = path.join(process.cwd(), "apps", "web");

const IGNORE_DIRS = [
  "node_modules", ".git", ".husky", ".next", "dist", "build", "public",
];

// Next.js / config filenames — exempt from kebab-case rule.
const NEXTJS_SPECIAL_FILES = [
  "page.tsx", "page.ts",
  "layout.tsx", "layout.ts",
  "loading.tsx", "error.tsx", "global-error.tsx",
  "not-found.tsx", "route.ts",
  "template.tsx", "default.tsx",
  "middleware.ts", "proxy.ts", "instrumentation.ts",
  "globals.css",
  // Config / type declaration files
  "next.config.ts", "next.config.js", "next.config.mjs",
  "next-env.d.ts",
  "tailwind.config.ts", "tailwind.config.js",
  "postcss.config.js", "postcss.config.mjs",
  "eslint.config.js", "eslint.config.mjs",
  "tsconfig.json",
];

function isUpperFirst(name) {
  const c = name.charAt(0);
  return c === c.toUpperCase() && c !== c.toLowerCase();
}

function isLowerFirst(name) {
  const c = name.charAt(0);
  return c === c.toLowerCase() && c !== c.toUpperCase();
}

let errors = [];

function processFile(filePath, relativePath) {
  const fileName = path.basename(filePath);

  // Skip dot-files and Next.js reserved names.
  if (fileName.startsWith(".") || NEXTJS_SPECIAL_FILES.includes(fileName)) return;

  if (fileName.endsWith(".tsx")) {
    // tsx files export React components — must start with a capital letter (PascalCase).
    // Exception: hooks directory (use-something.tsx is valid there).
    const inHooks = relativePath.split(path.sep).includes("hooks");
    if (!inHooks && !isUpperFirst(fileName)) {
      errors.push(`TSX component file must start with a capital letter: ${relativePath}`);
    }
  } else if (fileName.endsWith(".ts")) {
    // ts files (utils, queries, api, hooks) — must start with a lowercase letter.
    if (!isLowerFirst(fileName)) {
      errors.push(`TS file must start with a lowercase letter: ${relativePath}`);
    }
  }
}

function processDirectory(dirPath, relativePath = "") {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });

    // Check folder name (skip the root scan entry itself).
    if (relativePath) {
      const folderName = path.basename(dirPath);
      const isNextSpecial = ["[", "(", "_"].some((p) => folderName.startsWith(p));
      if (!IGNORE_DIRS.includes(folderName) && !isNextSpecial) {
        if (!isLowerFirst(folderName)) {
          errors.push(`Folder must start with a lowercase letter: ${relativePath}`);
        }
      }
    }

    for (const entry of entries) {
      const entryPath = path.join(dirPath, entry.name);
      const entryRelativePath = path.join(relativePath, entry.name);

      if (entry.isDirectory()) {
        if (!IGNORE_DIRS.includes(entry.name) && !entry.name.startsWith(".")) {
          processDirectory(entryPath, entryRelativePath);
        }
      } else if (entry.isFile()) {
        processFile(entryPath, entryRelativePath);
      }
    }
  } catch (err) {
    console.error(`Error processing ${dirPath}: ${err.message}`);
  }
}

console.log("Checking file/folder naming conventions...");
processDirectory(ROOT_DIR);

if (errors.length > 0) {
  console.error("\n❌ Naming convention check failed:");
  errors.forEach((e) => console.error(`  - ${e}`));
  console.error("\nConventions:");
  console.error("  🔹 .tsx files must start with a capital letter  → SignOutButton.tsx, DashboardView.tsx");
  console.error("  🔹 .ts  files must start with a lowercase letter → jobs.ts, use-auth.ts, api.ts");
  console.error("  🔹 Folders must start with a lowercase letter   → components/, lib/, queries/");
  process.exit(1);
} else {
  console.log("✅ Naming convention check passed.");
  process.exit(0);
}
