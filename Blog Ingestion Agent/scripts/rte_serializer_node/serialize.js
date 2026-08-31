#!/usr/bin/env node
/**
 * CLI boundary: HTML -> Contentstack JSON RTE, via the official
 * @contentstack/json-rte-serializer (htmlToJson). Called as a subprocess
 * from the Python pipeline so node construction (uids, node types, attrs)
 * always matches whatever Contentstack's own editor would produce.
 *
 * Usage:
 *   node serialize.js < body.html > body.json
 *   node serialize.js --file body.html --output body.json
 *
 * Internal entry-reference links: to get a native Contentstack `reference`
 * node (UID-backed, survives URL changes, shows up in "used in" lookups)
 * instead of a plain <a href>, emit the anchor with this exact attribute
 * contract before piping it through this script:
 *
 *   <a class="embedded-entry redactor-component block-entry" target="_blank"
 *      type="entry"
 *      data-sys-entry-uid="bltXXXXXXXXXXXXXXXX"
 *      data-sys-content-type-uid="blog_post"
 *      data-sys-entry-locale="en-us"
 *      sys-style-type="link">Anchor text</a>
 *
 * That shape is not a guess — it's lifted directly from this package's own
 * test fixtures (test/expectedJson.ts, case "8"). Any internal link the
 * pipeline can't resolve to a UID should fall back to a plain <a href="...">
 * (handled fine by the standard converter) rather than block the run.
 */

const fs = require("fs");
const { JSDOM } = require("jsdom");
const { htmlToJson } = require("@contentstack/json-rte-serializer");

function readInput(args) {
  const fileFlagIndex = args.indexOf("--file");
  if (fileFlagIndex !== -1) {
    const path = args[fileFlagIndex + 1];
    if (!path) {
      throw new Error("--file requires a path argument");
    }
    return fs.readFileSync(path, "utf8");
  }
  return fs.readFileSync(0, "utf8"); // stdin
}

function writeOutput(args, json) {
  const outputFlagIndex = args.indexOf("--output");
  const text = JSON.stringify(json, null, 2);
  if (outputFlagIndex !== -1) {
    const path = args[outputFlagIndex + 1];
    if (!path) {
      throw new Error("--output requires a path argument");
    }
    fs.writeFileSync(path, text + "\n", "utf8");
  } else {
    process.stdout.write(text + "\n");
  }
}

function main() {
  const args = process.argv.slice(2);
  const html = readInput(args);

  const dom = new JSDOM(html);
  const body = dom.window.document.querySelector("body");
  const json = htmlToJson(body);

  writeOutput(args, json);
}

try {
  main();
} catch (err) {
  process.stderr.write(`rte_serializer_node: ${err.message}\n`);
  process.exit(1);
}
