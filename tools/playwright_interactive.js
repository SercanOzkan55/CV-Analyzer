const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

if (process.argv.length < 3) {
  console.log('Usage: node tools/playwright_interactive.js <url> [actions_json] [output_path]');
  process.exit(1);
}

const url = process.argv[2];
const actionsRaw = process.argv[3] || '[]';
const outputPath = process.argv[4] || 'tools/interactive_output.png';

let actions = [];
try {
  actions = JSON.parse(actionsRaw);
} catch (e) {
  console.error('Failed to parse actions JSON:', e.message);
}

(async () => {
  console.log('Launching headless Chromium browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  console.log(`Navigating to: ${url}`);
  await page.goto(url, { waitUntil: 'networkidle' });

  for (let i = 0; i < actions.length; i++) {
    const act = actions[i];
    console.log(`[Action ${i+1}/${actions.length}] Running: ${act.action} on ${act.selector || 'page'}`);
    
    try {
      switch (act.action) {
        case 'click':
          await page.click(act.selector, { timeout: 5000 });
          break;
        case 'type':
          await page.fill(act.selector, act.value, { timeout: 5000 });
          break;
        case 'wait':
          if (typeof act.value === 'number') {
            await page.waitForTimeout(act.value);
          } else if (typeof act.value === 'string') {
            await page.waitForSelector(act.value, { timeout: 5000 });
          }
          break;
        case 'hover':
          await page.hover(act.selector, { timeout: 5000 });
          break;
        case 'press':
          await page.press(act.selector || 'body', act.value);
          break;
        default:
          console.warn(`Unknown action: ${act.action}`);
      }
    } catch (err) {
      console.error(`Error running action ${act.action}:`, err.message);
    }
  }

  // Final wait to let animations settle
  await page.waitForTimeout(2000);

  console.log(`Saving interactive screenshot to: ${outputPath}`);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  await page.screenshot({ path: outputPath, fullPage: true });

  await browser.close();
  console.log('Interactive workflow completed successfully.');
})();
