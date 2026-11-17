const major = Number.parseInt(process.versions.node.split(".")[0] ?? "", 10);

if (major !== 26) {
  console.error(
    `OpenVietGIS requires Node.js 26.x for accepted validation; current runtime is ${process.version}.`
  );
  process.exit(1);
}

console.log(`Node runtime: ${process.version} (accepted baseline)`);
