---
title: GO Slim Arc Diagram
---

```js
import * as d3 from "npm:d3@7"

// This reads the prebuilt static JSON snapshot.
// No fetch at runtime: Framework already materialized it during build.
data = FileAttachment("data/go_arc.json").json()

chart = {
  const nodes = data.nodes;
  const links = data.links;

  const orderByName = nodes.slice().sort((a,b)=>d3.ascending(a.label,b.label)).map(d=>d.id);
  const orders = new Map([["by name", orderByName]]);

  const width = 800;
  const step = 14;
  const marginTop = 20;
  const marginRight = 20;
  const marginBottom = 20;
  const marginLeft = 130;
  const height = (nodes.length - 1) * step + marginTop + marginBottom;
  const y = d3.scalePoint(orders.get("by name"), [marginTop, height - marginBottom]);

  const color = d3.scaleOrdinal()
    .domain([...new Set(nodes.map(d => d.group))].sort(d3.ascending))
    .range(d3.schemeCategory10)
    .unknown("#aaa");

  const groups = new Map(nodes.map(d => [d.id, d.group]));
  function samegroup({ source, target }) {
    return groups.get(source) === groups.get(target) ? groups.get(source) : null;
  }

  const svg = d3.create("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .attr("style", "max-width:100%;height:auto;font:10px sans-serif;");

  const Y = new Map(nodes.map(({id}) => [id, y(id)]));

  function arc(d) {
    const y1 = Y.get(d.source);
    const y2 = Y.get(d.target);
    const r = Math.abs(y2 - y1) / 2;
    return `M${marginLeft},${y1}A${r},${r} 0,0,${y1 < y2 ? 1 : 0} ${marginLeft},${y2}`;
  }

  const path = svg.insert("g", "*")
      .attr("fill", "none")
      .attr("stroke-opacity", 0.6)
      .attr("stroke-width", 1.5)
    .selectAll("path")
    .data(links)
    .join("path")
      .attr("stroke", d => color(samegroup(d)))
      .attr("d", arc);

  const label = svg.append("g")
      .attr("text-anchor", "end")
    .selectAll("g")
    .data(nodes)
    .join("g")
      .attr("transform", d => `translate(${marginLeft},${Y.get(d.id)})`)
      .call(g => g.append("text")
          .attr("x", -6)
          .attr("dy", "0.35em")
          .attr("fill", d => d3.lab(color(d.group)).darker(2))
          .text(d => d.label))
      .call(g => g.append("circle")
          .attr("r", 3)
          .attr("fill", d => color(d.group)));

  // Hover effects
  label.append("rect")
      .attr("fill", "none")
      .attr("width", marginLeft + 40)
      .attr("height", step)
      .attr("x", -marginLeft)
      .attr("y", -step / 2)
      .attr("pointer-events", "all")
      .on("pointerenter", (event, d) => {
        svg.classed("hover", true);
        label.classed("primary", n => n === d);
        label.classed("secondary", n => links.some(({source, target}) =>
          (n.id === source && d.id === target) || (n.id === target && d.id === source)
        ));
        path.classed("primary", l => l.source === d.id || l.target === d.id).filter(".primary").raise();
      })
      .on("pointerout", () => {
        svg.classed("hover", false);
        label.classed("primary", false);
        label.classed("secondary", false);
        path.classed("primary", false).order();
      });

  svg.append("style").text(`
    .hover text { fill: #aaa; }
    .hover g.primary text { font-weight: bold; fill: #333; }
    .hover g.secondary text { fill: #333; }
    .hover path { stroke: #ccc; }
    .hover path.primary { stroke: #333; }
  `);

  return svg.node();
}
