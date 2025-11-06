---
title: How Has Stephen Curry's Field Goal Percentage Changed Over His Career?
toc: false
---
<style>
  .hero { text-align:left; margin: 0 0 10px; }
  .hero h1 { margin: 0; font: 700 36px/1.25 system-ui, sans-serif; }
  .hero p.caption { margin: 0px 0 0; color: #b5b3b3ff; font: 18px/1.4 system-ui, sans-serif; }

  .legend { display:flex; flex-wrap:wrap; gap: 12px 16px; justify-content:left; margin: 8px 0 14px; }
  .legend .swatch { display:inline-flex; align-items:center; gap:8px; font: 18px/1.2 system-ui, sans-serif; color:#222; }
  .legend .line { width:18px; height:0; border-radius:2px; border-top:3px solid currentColor; }
  .legend .c-2p { color:#1f77b4; }  /* 2 close enough lol*/
  .legend .c-3p { color:#ff7f0e; }  /* 3 */
  .legend .c-ft { color:#2ca02c; }  /* FT */
  .legend .c-fg { color:#d62728; }  /* FG */

  .label {font: 18px}
</style>

<div class="hero">
  <h1>How Has Stephen Curry’s Shooting Percentage Changed Over Time?</h1>
  <p class="caption">FT% = Free Throw • 2P% = 2-Point • 3P% = 3-Point • FG% = Field Goal (all shots)</p>
</div>

<div class="legend">
  <span class="swatch c-2p"><span class="line"></span>2P%</span>
  <span class="swatch c-3p"><span class="line"></span>3P%</span>
  <span class="swatch c-ft"><span class="line"></span>FT%</span>
  <span class="swatch c-fg"><span class="line"></span>FG%</span>
</div>

<style>
  .controls { text-align:left; margin: 10px 0 18px; font: 13px system-ui, sans-serif; }
  .controls select { font-size: 18px; padding: 4px 8px; }
</style>

<div class="controls">
  <label>Stat:
    <select id="series-select">
      <option value="All" selected>All</option>
    </select>
  </label>
</div>


```js
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7/+esm";

const text = await FileAttachment("./data/curry-seasons.csv").text();
const cleanText = text.replace(/^\uFEFF/, ""); // strip UTF-8 BOM if present

const table = d3.csvParse(cleanText); // no row function here
const headerKeys = Object.keys(table[0] ?? {});
console.log("[csv headers]", headerKeys);

const H = s => String(s ?? "").trim().toLowerCase();

const findKey = (target) => headerKeys.find(k => H(k) === H(target));

const kSeason = findKey("season") || headerKeys.find(k => H(k).includes("season"));
const kFG     = findKey("fg%")    || headerKeys.find(k => H(k).replace(/\s+/g,"") === "fg%");
const k3P     = findKey("3p%")    || headerKeys.find(k => H(k).replace(/\s+/g,"") === "3p%");
const k2P     = findKey("2p%")    || headerKeys.find(k => H(k).replace(/\s+/g,"") === "2p%");
const kFT     = findKey("ft%")    || headerKeys.find(k => H(k).replace(/\s+/g,"") === "ft%");

if (!kSeason || !kFG || !k3P || !k2P || !kFT) {
  display(html`<pre style="color:crimson">
Missing headers. Found: ${headerKeys.join(", ")}
Expected: Season, FG%, 3P%, 2P%, FT%
</pre>`);
  throw new Error("Required headers not found");
}

const S = x => (x == null ? "" : String(x).replace(/[–—]/g, "-").trim()); 
const rows = table.map(d => {
  const season = S(d[kSeason]);
  if (!/^\d{4}-\d{2}$/.test(season)) return null; 
  return {
    season,
    fg:  +S(d[kFG]),
    tp3: +S(d[k3P]),
    tp2: +S(d[k2P]),
    ft:  +S(d[kFT])
  };
}).filter(Boolean);

console.log("[curry] seasons parsed =", rows.length);
if (!rows.length) {
  display(html`<p style="color:crimson">Parsed 0 season rows. Check the CSV header names and that the first column is exactly “Season”.</p>`);
  throw new Error("No season rows parsed");
}
const seasonToDate = s => new Date(Date.UTC(+s.slice(0, 4), 9, 1)); // Oct 1 of start year

const seasonDates = d3.sort(
  Array.from(new Set(rows.map(r => +seasonToDate(r.season))))
).map(t => new Date(t));

const dateToLabel = new Map(
  rows.map(r => [seasonToDate(r.season).getTime(), r.season])
);



const stocks = [];
for (const r of rows) {
  const Date = seasonToDate(r.season);
  stocks.push({ Date, Symbol: "2P%", Close: r.tp2 });
  stocks.push({ Date, Symbol: "3P%", Close: r.tp3 });
  stocks.push({ Date, Symbol: "FT%", Close: r.ft  });
  stocks.push({ Date, Symbol: "FG%", Close: r.fg  });
}
console.log("[curry] stocks rows =", stocks.length);



const width = 1100;    // was 928
const height = 680;    
const marginTop = 44;  
const marginRight = 60;
const marginBottom = 40;
const marginLeft = 56;

const x = d3.scaleUtc()
  .domain(d3.extent(stocks, d => d.Date))
  .range([marginLeft, width - marginRight])
  .clamp(true);

const series = d3.groups(stocks, d => d.Symbol).map(([key, values]) => {
  values.sort((a, b) => d3.ascending(a.Date, b.Date));
  const v = values.find(d => Number.isFinite(d.Close) && d.Close > 0)?.Close ?? 1;
  return { key, values: values.map(({ Date, Close }) => ({ Date, value: Close / v })) };
});

let k = d3.max(series.map(({ values }) => {
  const maxv = d3.max(values, d => d.value);
  const minv = d3.min(values, d => d.value);
  return (Number.isFinite(maxv) && Number.isFinite(minv) && minv > 0) ? maxv / minv : NaN;
}));
if (!Number.isFinite(k) || k <= 0) k = 1.5;

const y = d3.scaleLog()
  .domain([1 / k, k])
  .rangeRound([height - marginBottom, marginTop]);

// Build symmetric log ticks around 1×.
const steps = 6;                      // how many ticks above/below 1
const c = Math.pow(k, 1 / steps);     
const tickValues = d3.range(-steps, steps + 1)
  .map(i => Math.pow(c, i))
  .filter(v => v >= 1 / k - 1e-9 && v <= k + 1e-9);


const fmtMult = d => (Math.abs(d - 1) < 1e-6 ? "1×"
  : d3.format(d >= 10 || d <= 0.1 ? ".1f" : ".2f")(d) + "×");


const z = d3.scaleOrdinal(d3.schemeCategory10).domain(series.map(d => d.key));
const bisect = d3.bisector(d => d.Date).left;


const svg = d3.create("svg")
  .attr("width", width)
  .attr("height", height)
  .attr("viewBox", [0, 0, width, height])
  .attr("style", "max-width: 100%; height: auto; -webkit-tap-highlight-color: transparent;");


const gx = svg.append("g")
  .attr("transform", `translate(0,${height - marginBottom})`)
  .call(
    d3.axisBottom(x)
      .tickValues(seasonDates)                         
      .tickFormat(d => dateToLabel.get(d.getTime()))  
  )
  .call(g => g.select(".domain").remove());

// optional tilt if crowded
gx.selectAll(".tick text")
  .attr("text-anchor", "end")
  .attr("transform", "rotate(-35)")
  .style("font-size", "12px");


const gy = svg.append("g")
  .attr("transform", `translate(${marginLeft},0)`)
  .call(d3.axisLeft(y).tickValues(tickValues).tickFormat(fmtMult))
  .call(g => g.selectAll(".tick line").clone()
    .attr("stroke-opacity", d => Math.abs(d - 1) < 1e-12 ? 0.6 : 0.2) // emphasize 1×
    .attr("x2", width - marginLeft - marginRight))
  .call(g => g.select(".domain").remove());


gy.selectAll(".tick text").style("font-size", "13px");


//rule sits on top of axes, so line always visible
const rule = svg.append("line")
  .attr("y1", marginTop)                
  .attr("y2", height - marginBottom)
  .attr("stroke", "#000000ff")             
  .attr("stroke-width", 10)               
  .attr("stroke-linecap", "round")
  .style("pointer-events", "none");      



const line = d3.line()
  .defined(d => Number.isFinite(d.value) && d.value > 0) // guard for log scale
  .x(d => x(d.Date))
  .y(d => y(d.value));

const serie = svg.append("g")
  .style("font", "bold 10px sans-serif")
  .selectAll("g")
  .data(series)
  .join("g");

  // Populate the dropdown 
const seriesSelect = document.getElementById("series-select");
if (seriesSelect && seriesSelect.options.length <= 1) {
  for (const name of z.domain()) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    seriesSelect.appendChild(opt);
  }
}

function applySeriesFilter(sym) {
  serie.style("display", d => (sym === "All" || d.key === sym) ? null : "none");
}

// Initial state + change handler
applySeriesFilter(seriesSelect ? seriesSelect.value : "All");
seriesSelect?.addEventListener("change", () => applySeriesFilter(seriesSelect.value));


serie.append("path")
  .attr("fill", "none")
  .attr("stroke-width", 1.5)
  .attr("stroke-linejoin", "round")
  .attr("stroke-linecap", "round")
  .attr("stroke", d => z(d.key))
  .attr("d", d => line(d.values));

serie.append("text")
  .datum(d => ({ key: d.key, value: d.values[d.values.length - 1].value }))
  .attr("fill", d => z(d.key))
  .attr("paint-order", "stroke")
  .attr("stroke", "white").attr("stroke-width", 3)
  .attr("x", x.range()[1] + 3)
  .attr("y", d => y(d.value))
  .attr("dy", "0.35em")
  .style("font-size", "14px") 
  .text(d => d.key);
  
const mode = "log";
function update(date) {
  rule.attr("transform", `translate(${x(date)},0)`);

  if (mode === "log") {
    // same vertical-translation math as before
    serie.attr("transform", ({ values }) => {
      const i = d3.bisector(d => d.Date).left(values, date, 0, values.length - 1);
      const v0 = values[0]?.value, vi = values[i]?.value;
      const offset = (Number.isFinite(vi) && Number.isFinite(v0) && v0 > 0) ? y(1) - y(vi / v0) : 0;
      return `translate(0,${offset})`;
    });
  } else {
  }
}

d3.transition().ease(d3.easeCubicOut).duration(3000).tween("date", () => {
  const i = d3.interpolateDate(x.domain()[1], x.domain()[0]);
  return t => update(i(t));
});

const snap = d3.bisector(d => d).center;

svg.on("pointermove", (event) => {
  const [mx] = d3.pointer(event, svg.node());
  const raw = x.invert(mx);
  const i = snap(seasonDates, raw);        // nearest index
  const snapped = seasonDates[i];          // exact season date
  update(snapped);                         // use snapped date everywhere
  event.preventDefault();
});


// Render
display(svg.node());
```