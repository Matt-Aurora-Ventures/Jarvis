// Automated VPS Deployment via Hostinger Web Terminal
// This script uses Puppeteer to control the browser and execute commands

const puppeteer = require('puppeteer');
const fs = require('fs');

async function deployJarvisVPS() {
    console.log('🚀 Starting automated VPS deployment...\n');

    const browser = await puppeteer.launch({
        headless: false, // Show browser so user can see progress
        defaultViewport: { width: 1920, height: 1080 }
    });

    const page = await browser.newPage();

    try {
        // Step 1: Navigate to Hostinger VPS terminal
        console.log('📡 Navigating to Hostinger VPS...');
        await page.goto('https://hpanel.hostinger.com/vps/1277677/overview', {
            waitUntil: 'networkidle2',
            timeout: 60000
        });

        // Check if we need to login
        const isLoginPage = await page.$('input[type="password"]');
        if (isLoginPage) {
            console.log('⚠️  Not logged in. Please login to Hostinger in the browser window.');
            console.log('   (Script will continue after you login...)');

            // Wait for navigation away from login page
            await page.waitForNavigation({ timeout: 300000 }); // 5 min timeout
        }

        // Step 2: Click Terminal button
        console.log('🖥️  Opening web terminal...');
        await page.waitForSelector('[data-testid="terminal-button"], button:has-text("Terminal"), a:has-text("Terminal")', {
            timeout: 30000
        });

        // Try multiple selectors for the terminal button
        const terminalButton = await page.$('[data-testid="terminal-button"]')
            || await page.$('button:has-text("Terminal")')
            || await page.$('a:has-text("Terminal")');

        if (terminalButton) {
            await terminalButton.click();
            await page.waitForTimeout(3000);
        } else {
            console.log('⚠️  Could not find Terminal button. Trying direct URL...');
            await page.goto('https://hpanel.hostinger.com/vps/1277677/terminal', {
                waitUntil: 'networkidle2'
            });
        }

        // Step 3: Wait for terminal to load
        console.log('⏳ Waiting for terminal to initialize...');
        await page.waitForTimeout(5000);

        // Step 4: Get root password from user or environment
        console.log('\n📝 Terminal ready. Starting deployment...\n');

        // Send commands to terminal
        const commands = [
            'clear',
            'echo "=== JARVIS VPS AUTOMATED DEPLOYMENT ==="',
            'cd /tmp',
            'curl -o deploy.sh https://raw.githubusercontent.com/Matt-Aurora-Ventures/Jarvis/main/vps-ultimate-deployment.sh',
            'chmod +x deploy.sh',
            'bash deploy.sh 2>&1 | tee deployment.log',
            'echo "=== DEPLOYMENT COMPLETE ==="'
        ];

        for (const cmd of commands) {
            console.log(`💻 Executing: ${cmd}`);
            await page.keyboard.type(cmd);
            await page.keyboard.press('Enter');
            await page.waitForTimeout(2000);
        }

        console.log('\n✅ Deployment script launched!');
        console.log('📊 Monitor progress in the browser window.');
        console.log('⏱️  Estimated time: 5-10 minutes\n');
        console.log('🔍 The browser will stay open so you can watch progress.');
        console.log('   Close it manually when deployment completes.\n');

        // Keep browser open for monitoring
        console.log('Press Ctrl+C to close browser and exit...');
        await new Promise(() => {}); // Keep alive

    } catch (error) {
        console.error('❌ Error during deployment:', error.message);
        console.log('\n💡 Troubleshooting:');
        console.log('1. Make sure you\'re logged into Hostinger');
        console.log('2. Check that VPS terminal is accessible');
        console.log('3. Verify the VPS is running\n');
    }
}

// Run the automation
deployJarvisVPS().catch(console.error);
