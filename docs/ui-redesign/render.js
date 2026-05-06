const path = require("path");
const { chromium } = require("/Users/dairui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");

const root = __dirname;
const html = `file://${path.join(root, "index.html")}`;
const shots = [
  ["home", "01-home-redesign.png"],
  ["mine", "02-mine-redesign.png"],
  ["upload", "03-upload-redesign.png"],
  ["detail", "04-task-detail-redesign.png"],
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1760, height: 940 },
    deviceScaleFactor: 2,
  });
  await page.goto(html);
  await page.screenshot({ path: path.join(root, "00-overview.png"), fullPage: true });
  for (const [id, file] of shots) {
    const el = page.locator(`#${id}`);
    await el.screenshot({ path: path.join(root, file) });
  }
  await browser.close();
})();
