import {readFile} from "node:fs/promises";
import {csvParse, csvFormat} from "d3-dsv";

export default async function () {
  // read your original CSV from src/data/raw/
  const raw = await readFile(new URL("./raw/curry_seasons.csv", import.meta.url), "utf8");

  // parse, clean, and keep the four shooting percentages
  const rows = csvParse(raw, d => {
    const S = (x) => (x == null ? "" : String(x).trim());
    const season = S(d.Season).replace(/[–—]/g, "-"); // normalize dashes
    if (!/^\d{4}-\d{2}$/.test(season)) return null;   // skip summary rows like "17 Yrs"

    return {
      season,
      fg:  +S(d["FG%"]),
      tp3: +S(d["3P%"]),
      tp2: +S(d["2P%"]),
      ft:  +S(d["FT%"])
    };
  }).filter(Boolean);

  // write out a clean CSV
  return csvFormat(rows, ["season", "fg", "tp3", "tp2", "ft"]);
}
