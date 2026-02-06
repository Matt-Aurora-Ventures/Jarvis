#!/usr/bin/env python3
"""
Test and verify all Jarvis automation components.
Run this after initial setup to ensure everything works.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.automation.orchestrator import get_orchestrator
from core.automation.x_multi_account import get_x_manager
from core.automation.google_oauth import get_google_manager
from core.automation.credential_manager import get_credential_manager
from core.automation.browser_cdp import launch_chrome_with_debugging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_browser():
    """Test browser CDP connection."""
    print('\n' + '='*60)
    print('🌐 Testing Browser Automation...')
    print('='*60)

    orch = get_orchestrator()

    # Try to connect to existing Chrome instance
    if not await orch.initialize(debug_port=9222):
        print('❌ Browser connection failed')
        print('💡 Launch Chrome with: chrome.exe --remote-debugging-port=9222')
        return False

    print('✅ Browser connected')

    # Test navigation
    await orch.navigate('https://example.com')
    print('✅ Navigation works')

    # Test screenshot
    screenshot_path = Path(__file__).parent.parent / 'test_screenshot.png'
    await orch.screenshot(str(screenshot_path))
    print(f'✅ Screenshot saved: {screenshot_path}')

    return True


async def test_x_accounts():
    """Test X (Twitter) multi-account manager."""
    print('\n' + '='*60)
    print('🐦 Testing X Multi-Account Manager...')
    print('='*60)

    mgr = get_x_manager()
    accounts = await mgr.list_accounts()

    if not accounts:
        print('⚠️  No X accounts configured')
        print('💡 Add accounts using:')
        print('   await mgr.add_account("account_id", "username", "client_id", "client_secret")')
        return False

    print(f'✅ Found {len(accounts)} X accounts:')
    for account_id in accounts:
        username = mgr.get_username(account_id)
        print(f'   - @{username} ({account_id})')

        # Test token retrieval
        token = await mgr.get_token(account_id)
        if token:
            print(f'     ✅ OAuth token valid (expires: {token.expires_at})')
        else:
            print(f'     ❌ No valid token')

    return True


async def test_google_accounts():
    """Test Google OAuth manager."""
    print('\n' + '='*60)
    print('📧 Testing Google OAuth Manager...')
    print('='*60)

    mgr = get_google_manager()
    accounts = await mgr.list_accounts()

    if not accounts:
        print('⚠️  No Google accounts configured')
        print('💡 Add accounts by calling:')
        print('   token = await mgr.get_token("your@gmail.com")')
        print('   (Will trigger OAuth flow)')
        return False

    print(f'✅ Found {len(accounts)} Google accounts:')
    for account_id in accounts:
        print(f'   - {account_id}')

        token = await mgr.get_token(account_id)
        if token:
            print(f'     ✅ OAuth token valid (expires: {token.expires_at})')
            print(f'     Scopes: {", ".join(token.scopes[:3])}...')
        else:
            print(f'     ❌ No valid token')

    return True


async def test_credentials():
    """Test password manager integration."""
    print('\n' + '='*60)
    print('🔐 Testing Password Manager Integration...')
    print('='*60)

    mgr = get_credential_manager()

    if not mgr.providers:
        print('❌ No password manager CLI found')
        print('💡 Install 1Password or Bitwarden CLI:')
        print('   1Password: https://developer.1password.com/docs/cli/')
        print('   Bitwarden: https://bitwarden.com/help/cli/')
        return False

    for provider in mgr.providers:
        print(f'✅ {provider.__class__.__name__} available')

    # Try to fetch a test credential (won't exist, just testing CLI works)
    try:
        cred = await mgr.get_credential('test', 'test')
        if cred:
            print('✅ Credential retrieval works')
        else:
            print('⚠️  No test credential found (this is expected)')
    except Exception as e:
        print(f'⚠️  CLI may not be unlocked: {e}')

    return True


async def test_orchestrator():
    """Test the full orchestrator integration."""
    print('\n' + '='*60)
    print('🎭 Testing Orchestrator Integration...')
    print('='*60)

    orch = get_orchestrator()
    await orch.initialize()

    # Test X accounts via orchestrator
    x_accounts = await orch.list_x_accounts()
    print(f'✅ X accounts available: {len(x_accounts)}')

    # Test Google accounts via orchestrator
    google_accounts = await orch.list_google_accounts()
    print(f'✅ Google accounts available: {len(google_accounts)}')

    await orch.shutdown()
    print('✅ Orchestrator shutdown clean')

    return True


async def main():
    """Run all tests."""
    print('\n' + '='*60)
    print('🚀 JARVIS AUTOMATION INFRASTRUCTURE TEST')
    print('='*60)

    results = {
        'Browser': await test_browser(),
        'X Multi-Account': await test_x_accounts(),
        'Google OAuth': await test_google_accounts(),
        'Password Manager': await test_credentials(),
        'Orchestrator': await test_orchestrator()
    }

    # Summary
    print('\n' + '='*60)
    print('📊 TEST SUMMARY')
    print('='*60)

    for component, passed in results.items():
        status = '✅ PASS' if passed else '⚠️  INCOMPLETE'
        print(f'{component:.<40} {status}')

    total_passed = sum(results.values())
    total_tests = len(results)

    print('\n' + '='*60)
    print(f'Overall: {total_passed}/{total_tests} components ready')
    print('='*60)

    if total_passed == total_tests:
        print('\n🎉 ALL SYSTEMS OPERATIONAL! Automation infrastructure ready.')
        print('\n📖 See AUTOMATION_SETUP_GUIDE.md for usage examples.')
    else:
        print('\n⚠️  Some components need setup. See messages above.')

    print('\n💡 Next steps:')
    print('   1. Complete any missing setup steps above')
    print('   2. Add accounts (X, Google, LinkedIn)')
    print('   3. Run this test again')
    print('   4. Integrate with Jarvis bots')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n\n⚠️  Test interrupted by user')
    except Exception as e:
        logger.exception('Test failed with error:')
        sys.exit(1)
