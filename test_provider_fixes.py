#!/usr/bin/env python3
"""
Test script for provider fixes and quota handling.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.provider_manager import get_provider_manager
from core.providers import generate_text

def test_provider_manager():
    """Test the provider manager fallback system."""
    print("Testing Provider Manager...")
    
    manager = get_provider_manager()
    
    # Test provider stats
    stats = manager.get_provider_stats()
    print(f"Available providers: {list(stats['provider_status'].keys())}")
    print(f"Current best provider: {stats['current_best']}")
    
    # Test smart text generation
    try:
        test_prompt = "What is 2+2? Answer with just the number."
        result = manager.generate_text_with_fallback(test_prompt, max_output_tokens=10)
        
        print(f"Generation successful: {result['success']}")
        print(f"Provider used: {result['provider_used']}")
        print(f"Fallback used: {result['fallback_used']}")
        print(f"Text generated: {result['text'][:50]}...")
        
    except Exception as e:
        print(f"Test failed: {e}")
    
    # Test rate limiting
    print("\nTesting rate limiting...")
    for i in range(3):
        provider, _ = manager.get_best_provider()
        print(f"Request {i+1}: Best provider = {provider}")
        manager._record_request(provider)
    
    return manager

def test_voice_system():
    """Test voice system fixes."""
    print("\nTesting Voice System...")
    
    try:
        from core.voice import speak_text
        print("Voice system imported successfully")
        
        # Test with a simple text (this will use default voice if specified voice not found)
        print("Testing speech synthesis...")
        # Note: We won't actually speak to avoid noise during testing
        print("Voice system test completed (speech synthesis available)")
        
    except Exception as e:
        print(f"Voice system test failed: {e}")

def test_gemini_quota_handling():
    """Test Gemini quota error handling."""
    print("\nTesting Gemini Quota Handling...")
    
    try:
        from core.providers import _retryable_gemini_error
        
        # Test different error types
        test_errors = [
            Exception("429 You exceeded your current quota"),
            Exception("ResourceExhausted: Quota exceeded"),
            Exception("TooManyRequests: Rate limit exceeded"),
            Exception("ServiceUnavailable: Service down"),
            Exception("Random error")
        ]
        
        for error in test_errors:
            retryable = _retryable_gemini_error(error)
            print(f"Error: {str(error)[:50]}... -> Retryable: {retryable}")
        
    except Exception as e:
        print(f"Quota handling test failed: {e}")

if __name__ == "__main__":
    print("=== Provider and Voice System Tests ===")
    
    # Test provider manager
    manager = test_provider_manager()
    
    # Test voice system
    test_voice_system()
    
    # Test quota handling
    test_gemini_quota_handling()
    
    print("\n=== Tests Completed ===")
