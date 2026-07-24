const major = Number.parseInt(process.versions.node.split(".")[0] ?? "0", 10);

if (Number.isNaN(major) || major < 22) {
  console.error(
    `Compose AI requires Node.js 22 or newer. Current runtime: ${process.version}.`,
  );
  console.error("Switch to Node 22+ before running frontend or workspace commands.");
  process.exit(1);
}
