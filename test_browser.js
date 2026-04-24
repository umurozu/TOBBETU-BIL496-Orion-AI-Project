import { chromium } from 'playwright';

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    page.on('console', msg => console.log(`[${msg.type()}] ${msg.text()}`));
    page.on('pageerror', error => console.log(`PAGE EXCEPTION: ${error.message}`));
    
    await page.goto('http://localhost:5173', { waitUntil: 'load' });
    await page.waitForTimeout(2000);
    await browser.close();
})();
