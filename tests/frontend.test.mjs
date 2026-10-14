import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  normalize,
  matchScore,
  filterModels,
  escapeHtml,
  safeUrl,
  toCsv,
  csvCell,
  historyGroups,
  refreshModels,
  offerStatus,
  latestOfferChange,
} from "../public/lib.js";
const catalog = JSON.parse(
  await readFile(new URL("../data/catalog.json", import.meta.url)),
);
const models = catalog.models.map((m) => ({
  ...m,
  status: "needs_review",
  offers: [],
  promo: { min_rub: null },
  msrp: { min_rub: null },
}));
test("aliases handle Chinese, Cyrillic, whitespace, case and prefix", () => {
  const mon = models.find((m) => m.model_id === "geely-monjaro");
  assert.equal(normalize(" CS 75+ Plus "), "cs75plus");
  for (const query of ["mon", "MON JARO", "蒙扎罗", "Монджаро", "monjro"])
    assert.ok(matchScore(mon, query, catalog.brands) > 0, query);
});
test("ambiguous CS75 returns three separate candidates", () => {
  const rows = filterModels(
    models,
    { brand: "changan", query: "CS75" },
    catalog.brands,
  );
  assert.equal(rows.length, 3);
  assert.equal(new Set(rows.map((m) => m.model_id)).size, 3);
});
test("brand filtering keeps Hongqi H5 separate from HAVAL H5", () => {
  const rows = filterModels(
    models,
    { brand: "hongqi", query: "H5" },
    catalog.brands,
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].model_id, "hongqi-h5");
});
test("unknown query has a friendly empty result; short valid prefix succeeds", () => {
  assert.equal(
    filterModels(models, { query: "totallyunknown" }, catalog.brands).length,
    0,
  );
  assert.ok(filterModels(models, { query: "CS" }, catalog.brands).length > 1);
});
test("price sorting never treats missing values as zero", () => {
  const rows = structuredClone(models.slice(0, 3));
  rows[0].promo.min_rub = 2549000;
  rows[1].promo.min_rub = 2625000;
  for (const sort of ["asc", "desc"])
    assert.equal(
      filterModels(rows, { sort }).at(-1).model_id,
      rows[2].model_id,
    );
});
test("CSV exports missing price as empty and defuses spreadsheet formulas", () => {
  const csv = toCsv(models.slice(0, 1));
  assert.ok(csv.startsWith("\ufeff"));
  assert.ok(csv.includes('"needs_review"'));
  assert.ok(!csv.includes('"0"'));
  for (const text of [
    '=HYPERLINK("https://evil")',
    " +SUM(1,2)",
    "@cmd",
    "\t=1",
    "-1+2",
  ])
    assert.ok(csvCell(text).startsWith("\"'"));
  assert.equal(csvCell('a"b\nc'), '"a""b\nc"');
});
test("HTML and URL safety for imported fields", () => {
  assert.equal(escapeHtml('<script>"&'), "&lt;script&gt;&quot;&amp;");
  for (const url of [
    "javascript:alert(1)",
    "http://example.com",
    "https://user:pass@example.com",
  ])
    assert.equal(safeUrl(url), "#");
  assert.equal(safeUrl("https://haval.ru/"), "https://haval.ru/");
});
test("client hides expired and older than three days prices even on a cached page", () => {
  const model = structuredClone(models[0]);
  model.offers = [
    {
      price_kind: "official_promotional_reference",
      price_rub: 2549000,
      price_basis: "starting_at",
      status: "verified",
      verified_at: "2026-10-10T12:00:00Z",
      valid_until: "2026-10-15",
      effective_date: null,
    },
  ];
  assert.equal(
    refreshModels([model], new Date("2026-10-11T12:00:00Z"))[0].promo.min_rub,
    2549000,
  );
  let view = refreshModels([model], new Date("2026-10-14T12:00:00Z"))[0];
  assert.equal(view.status, "stale");
  assert.equal(view.promo.min_rub, null);
  view = refreshModels([model], new Date("2026-10-16T12:00:00Z"))[0];
  assert.equal(view.status, "expired");
  assert.equal(view.promo.min_rub, null);
});
test("different scope never joins the same chart series; 7/30/90 day filters work", () => {
  const now = new Date("2026-10-14T12:00:00Z");
  const observations = [
    { model_id: "x", comparison_key: "old", at: "2026-09-01T12:00:00Z" },
    { model_id: "x", comparison_key: "new", at: "2026-10-10T12:00:00Z" },
    { model_id: "x", comparison_key: "new", at: "2026-10-14T12:00:00Z" },
  ];
  assert.equal(historyGroups(observations, "x", 7, now).length, 1);
  assert.equal(historyGroups(observations, "x", 30, now).flat().length, 2);
  assert.equal(historyGroups(observations, "x", 90, now).length, 2);
});
test("offer expires at Moscow midnight, not UTC midnight", () => {
  const offer = {
    status: "verified",
    verified_at: "2026-10-14T12:00:00Z",
    valid_until: "2026-10-14",
  };
  assert.equal(
    offerStatus(offer, new Date("2026-10-14T20:59:00Z")),
    "verified",
  );
  assert.equal(offerStatus(offer, new Date("2026-10-14T21:00:00Z")), "expired");
});
test("card change compares the previous observation, not an old sticky price event", () => {
  const offer = {
    trim: "Optimum",
    price_kind: "official_promotional_reference",
    price_rub: 2549000,
  };
  const row = (at, key, price) => ({
    at,
    model_id: "x",
    comparison_key: key,
    offer: { ...offer, price_rub: price },
  });
  const history = {
    observations: [
      row("2026-10-13", "a", 2549000),
      row("2026-10-14", "a", 2549000),
    ],
    changes: [],
  };
  assert.equal(latestOfferChange(history, "x", offer), "与上次可比核验持平");
  history.observations[1].comparison_key = "b";
  assert.equal(latestOfferChange(history, "x", offer), "口径变更");
  history.observations[1].comparison_key = "a";
  history.observations[0].offer.price_rub = 2599000;
  assert.ok(latestOfferChange(history, "x", offer).startsWith("−"));
});
test("static shell and PWA paths work in a Pages repository subdirectory", async () => {
  const html = await readFile(
    new URL("../public/index.html", import.meta.url),
    "utf8",
  );
  for (const name of [
    "brand",
    "model",
    "keyword",
    "query-form",
    "cards",
    "sources",
    "history-range",
  ])
    assert.ok(html.includes(`id="${name}"`));
  assert.ok(!/(?:src|href)="\//.test(html));
  const manifest = JSON.parse(
    await readFile(new URL("../public/manifest.webmanifest", import.meta.url)),
  );
  assert.equal(manifest.start_url, "./");
  assert.equal(manifest.scope, "./");
  for (const icon of manifest.icons)
    assert.ok(
      (await readFile(new URL("../public/" + icon.src, import.meta.url)))
        .length > 100,
    );
});
