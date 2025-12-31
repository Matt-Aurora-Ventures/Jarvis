#!/usr/bin/env python3
"""
Test script for the research system.
"""

from core import research_engine

def test_research():
    """Test the research system."""
    print("Testing research system...")
    
    # Get research engine
    engine = research_engine.get_research_engine()
    
    # Test search
    print("\n1. Testing web search...")
    results = engine.search_web("autonomous AI agents", max_results=3)
    print(f"Found {len(results)} results:")
    for i, result in enumerate(results):
        print(f"  {i+1}. {result['title']}")
        print(f"     URL: {result['url']}")
        print(f"     Snippet: {result['snippet'][:100]}...")
    
    # Test content extraction
    if results:
        print("\n2. Testing content extraction...")
        url = results[0]['url']
        print(f"Extracting from: {url}")
        content = engine.extract_content(url)
        if content:
            print(f"Content extracted ({len(content)} chars):")
            print(content[:500] + "...")
        else:
            print("Failed to extract content")
    
    # Test full research cycle
    print("\n3. Testing full research cycle...")
    result = engine.research_topic("prompt engineering", max_pages=2)
    print(f"Research result: {result}")
    
    # Check database
    print("\n4. Checking database...")
    summary = engine.get_research_summary(limit=5)
    print(f"Database has {len(summary)} entries")
    
    print("\nTest complete!")

if __name__ == "__main__":
    test_research()
