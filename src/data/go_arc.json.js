
import fs from "fs";

const raw = JSON.parse(fs.readFileSync("src/data/go_out_arc.json", "utf8"));

const sankeyStyle = typeof raw.links[0]?.source === "number";
const idOf = (i) => raw.nodes[i]?.id ?? raw.nodes[i]?.name;

const nodes = sankeyStyle
  ? raw.nodes.map((n) => ({
      id: n.id ?? n.name,
      label: n.label ?? n.name ?? n.id,
      group: n.namespace ?? n.group ?? "unknown",
    }))
  : raw.nodes.map((n) => ({
      id: n.id,
      label: n.label ?? n.name ?? n.id,
      group: n.namespace ?? n.group ?? "unknown",
    }));

const links = sankeyStyle
  ? raw.links.map((e) => ({
      source: idOf(e.source),
      target: idOf(e.target),
      type: e.type ?? "is_a",
    }))
  : raw.links.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type ?? "is_a",
    }));

// Output a clean JSON object
process.stdout.write(JSON.stringify({ nodes, links }, null, 2));

