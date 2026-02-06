const fs = require('fs');
const { chromium } = require('playwright');

(async () => {
  const userDataDir = process.env.CHROME_USER_DATA || "C:\\Users\\lucid\\AppData\\Local\\Temp\\chrome-profile-notebooklm";
  const profileDir = process.env.CHROME_PROFILE_DIR || "Default";
  const outFile = process.env.OUT_FILE || "C:\\Users\\lucid\\OneDrive\\Desktop\\Projects\\Jarvis\\reports\\notebooklm_source.md";
  const url = "https://notebooklm.google.com/notebook/33528f04-1127-4190-8d7b-56c703bfaa20";

  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    channel: 'chrome',
    args: [`--profile-directory=${profileDir}`]
  });

  const page = await context.newPage();
  page.setDefaultTimeout(60000);

  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(12000);

  const text = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(outFile, `# NotebookLM Export\n\n${text}`);

  await context.close();
  process.exit(0);
})().catch(err => {
  const outFile = process.env.OUT_FILE || "C:\\Users\\lucid\\OneDrive\\Desktop\\Projects\\Jarvis\\reports\\notebooklm_source.md";
  fs.writeFileSync(outFile, `ERROR: ${err.message}\n${err.stack}`);
  process.exit(1);
});
