import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
const playwright = process.env.PLAYWRIGHT_MODULE
  ? await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href)
  : await import("playwright");
const server = spawn(process.execPath, ["scripts/serve.mjs"], {
  env: { ...process.env, PORT: "4174", STATIC_DIR: "dist" },
  stdio: ["ignore", "pipe", "inherit"],
});
let browser;
try {
  await new Promise((resolve, reject) => {
    server.stdout.once("data", resolve);
    server.once("error", reject);
    server.once("exit", (code) => reject(new Error(`Server exited ${code}`)));
  });
  browser = await playwright.chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE }
      : {}),
  });
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({
      viewport,
      acceptDownloads: true,
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (err) => errors.push(err.message));
    const missing = [];
    page.on("response", (r) => {
      if (r.status() >= 400 && r.url().startsWith("http://127.0.0.1"))
        missing.push(`${r.status()} ${r.url()}`);
    });
    await page.goto("http://127.0.0.1:4174/russia-auto-price-monitor/");
    await page.locator(".price-card").first().waitFor();
    assert.equal(await page.locator(".price-card").count(), 39);
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
      "Horizontal overflow",
    );
    await page.selectOption("#brand", "changan");
    assert.equal(await page.locator(".price-card").count(), 8);
    await page.fill("#keyword", "CS75");
    assert.equal(await page.locator(".price-card").count(), 3);
    await page.selectOption("#model", "changan-cs75-plus-new");
    await page.click(".primary");
    assert.equal(await page.locator(".price-card").count(), 1);
    await page.selectOption("#brand", "geely");
    await page.fill("#keyword", "mon");
    assert.equal(await page.locator(".price-card").count(), 1);
    await page.fill("#keyword", "monjro");
    assert.equal(await page.locator(".price-card").count(), 1);
    await page.click('[data-detail="geely-monjaro"]');
    assert.ok(
      await page
        .locator("#detail-body")
        .innerText()
        .then((s) => s.includes("暂未核验价格")),
    );
    await page.click("#close-detail");
    await page.selectOption("#brand", "tenet");
    await page.fill("#keyword", "T7");
    await page.click('[data-detail="tenet-t7"]');
    assert.equal(await page.locator(".offer").count(), 8);
    assert.ok(
      await page
        .locator("#detail-body")
        .innerText()
        .then((s) => s.includes("TP 参考") && s.includes("MSRP")),
    );
    await page.click('#detail-range [data-days="90"]');
    assert.ok(
      await page
        .locator("#detail-history")
        .innerText()
        .then((s) => s.includes("历史数据积累中")),
    );
    await page.click("#close-detail");
    const downloadPromise = page.waitForEvent("download");
    await page.click("#export");
    const download = await downloadPromise;
    assert.ok(download.suggestedFilename().endsWith(".csv"));
    const csv = await readFile(await download.path(), "utf8");
    assert.ok(csv.includes("2625000"));
    await page.click('[data-page="sources"]');
    assert.equal(await page.locator(".source-card").count(), 5);
    await page.click('[data-page="changes"]');
    await page.selectOption("#history-model", "tenet-t7");
    await page.click('#history-range [data-days="7"]');
    assert.ok(
      (await page.locator("#history-content").innerText()).includes(
        "历史数据积累中",
      ),
    );
    await page.click('[data-page="catalog"]');
    await page.selectOption("#brand", "");
    await page.fill("#keyword", "");
    if (process.env.SCREENSHOT_DIR) {
      await page.evaluate(() => {
        document.activeElement?.blur();
        scrollTo(0, 0);
      });
      await mkdir(process.env.SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({
        path: `${process.env.SCREENSHOT_DIR}/${viewport.width === 390 ? "mobile" : "desktop"}.png`,
        fullPage: false,
      });
    }
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    await context.setOffline(true);
    await page.reload();
    await page.locator(".price-card").first().waitFor();
    assert.ok(
      (await page.locator("#data-notice").innerText()).includes("离线旧快照"),
    );
    assert.deepEqual(errors, []);
    assert.deepEqual(missing, []);
    await context.close();
    console.log(
      `Browser PASS ${viewport.width}×${viewport.height}: search, filters, real offers, CSV, trends, sources, PWA offline`,
    );
  }
  // Verify a genuinely empty dataset renders all catalog models without fabricating a price.
  const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      serviceWorkers: "block",
    }),
    page = await context.newPage();
  await page.route("**/data/current.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    for (const model of data.models) {
      model.offers = [];
      model.status = "needs_review";
      model.promo = { min_rub: null, max_rub: null };
      model.msrp = { min_rub: null, max_rub: null };
    }
    await route.fulfill({ json: data });
  });
  await page.goto("http://127.0.0.1:4174/russia-auto-price-monitor/");
  await page.locator(".price-card").first().waitFor();
  assert.equal(await page.locator(".price.pending").count(), 39);
  assert.equal(await page.locator("#verified-count").innerText(), "0");
  await context.close();
  console.log("Browser PASS empty-price dataset");
} finally {
  if (browser) await browser.close();
  server.kill();
}
