import { firefox } from "playwright";
import path from "node:path";

const profileDir = process.env.FF_PROFILE_DIR;
if (!profileDir) {
  console.error("FF_PROFILE_DIR env var not set");
  process.exit(1);
}

const outDir = path.resolve("./.tmp/hostinger");

(async () => {
  const context = await firefox.launchPersistentContext(profileDir, {
    headless: true,
    viewport: { width: 1440, height: 900 },
  });
  const page = context.pages()[0] ?? await context.newPage();
  page.setDefaultTimeout(60000);

  await page.goto("https://hpanel.hostinger.com/vps", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(5000);

  const url = page.url();
  const title = await page.title();

  await page.screenshot({ path: path.join(outDir, "hostinger_vps.png"), fullPage: true });

  console.log(JSON.stringify({ url, title }, null, 2));

  await context.close();
})();
