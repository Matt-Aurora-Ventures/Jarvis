""
Test Script for Window Interaction

This script demonstrates how to use the window interaction capabilities
we've added to the BrowserAutomation class.
"""

import time
from core.browser_automation import get_browser_automation
from core.window_interaction_task import WindowInteractionTaskHandler

def test_window_interaction():
    """Test the window interaction functionality."""
    print("Starting window interaction test...")
    
    # Get the browser automation instance
    browser = get_browser_automation()
    
    # Create a task handler
    task_handler = WindowInteractionTaskHandler(browser)
    
    # List all browser windows
    print("\n=== Listing browser windows ===")
    windows = browser.interact_with_browser("list_windows")
    print(f"Found {len(windows.get('windows', []))} browser windows")
    
    if not windows.get('windows'):
        print("No browser windows found. Please open a browser and try again.")
        return
    
    # Print the first window's title
    first_window = windows['windows'][0]
    print(f"First window title: {first_window.get('title')}")
    
    # Activate the first browser window
    print("\n=== Activating browser window ===")
    activate_result = browser.interact_with_browser(
        "activate_window", 
        title=first_window.get('title', '')
    )
    print(f"Activation result: {activate_result}")
    
    # Get screen size
    print("\n=== Getting screen size ===")
    screen_size = browser.interact_with_browser("get_screen_size")
    print(f"Screen size: {screen_size}")
    
    # Get mouse position
    print("\n=== Getting mouse position ===")
    mouse_pos = browser.interact_with_browser("get_mouse_position")
    print(f"Mouse position: {mouse_pos}")
    
    # Create a task to navigate to a URL
    print("\n=== Creating navigation task ===")
    nav_task = task_handler.create_task("navigate_to_url", {
        "url": "https://www.google.com"
    })
    print(f"Created task {nav_task.task_id}")
    
    # Execute the navigation task
    print("\n=== Executing navigation task ===")
    nav_result = task_handler.execute_task(nav_task)
    print(f"Navigation result: {nav_result}")
    
    # Wait for the page to load
    print("\nWaiting for page to load...")
    time.sleep(3)
    
    # Extract text from the page
    print("\n=== Extracting text from the page ===")
    extract_task = task_handler.create_task("extract_text", {})
    extract_result = task_handler.execute_task(extract_task)
    
    if extract_result.get('success'):
        print(f"Extracted text (first 500 chars): {extract_result.get('text', '')[:500]}...")
    else:
        print(f"Failed to extract text: {extract_result.get('error', 'Unknown error')}")
    
    print("\n=== Test complete ===")

if __name__ == "__main__":
    test_window_interaction()
