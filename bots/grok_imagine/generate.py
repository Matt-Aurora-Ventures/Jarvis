"""
Generate images/videos with Grok Imagine.
Usage: python generate.py "your prompt here" [--video] [--mode normal|fun|spicy]
"""

import asyncio
import argparse
import logging
from pathlib import Path
from grok_imagine import GrokImagine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def generate(prompt: str, video: bool = False, mode: str = "normal", headless: bool = True):
    """Generate image or video with Grok Imagine."""

    grok = GrokImagine(headless=headless)

    try:
        await grok.start()

        # Check login
        if not await grok.is_logged_in():
            print("\n[ERROR] Not logged in!")
            print("Run: python setup_login.py")
            return None

        print(f"\n[INFO] Generating {'video' if video else 'image'}...")
        print(f"[INFO] Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"[INFO] Mode: {mode}")

        if video:
            result = await grok.generate_video(prompt, mode=mode)
        else:
            result = await grok.generate_image(prompt, mode=mode)

        if result:
            print(f"\n[SUCCESS] Generated: {result}")
            return result
        else:
            print("\n[ERROR] Generation failed")
            return None

    finally:
        await grok.stop()


def main():
    parser = argparse.ArgumentParser(description="Generate with Grok Imagine")
    parser.add_argument("prompt", help="Text prompt for generation")
    parser.add_argument("--video", action="store_true", help="Generate video instead of image")
    parser.add_argument("--mode", choices=["normal", "fun", "spicy"], default="normal")
    parser.add_argument("--show", action="store_true", help="Show browser (not headless)")

    args = parser.parse_args()

    result = asyncio.run(generate(
        prompt=args.prompt,
        video=args.video,
        mode=args.mode,
        headless=not args.show
    ))

    return result


if __name__ == "__main__":
    main()
