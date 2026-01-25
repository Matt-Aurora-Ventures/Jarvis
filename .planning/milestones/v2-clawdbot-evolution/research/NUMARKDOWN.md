# Research Report: NuMarkdown-8B-Thinking
Generated: 2026-01-25T15:05:15Z
Status: COMPLETE
Confidence: HIGH

---

## Summary

NuMarkdown-8B-Thinking is the first reasoning-enabled OCR Vision Language Model (VLM) specifically trained to convert documents into clean Markdown. Built on Qwen2.5-VL-7B, it uses a novel thinking tokens approach where the model reasons about document layout before generating output. It ranks #2 in arena benchmarks, competitive with Gemini 2.5 Flash reasoning, and significantly outperforms GPT-4o and specialized OCR models.

---

## Questions Answered

### Q1: What is NuMarkdown and what are its capabilities?

**Answer:** NuMarkdown-8B-Thinking is a vision-language model that converts document images to structured Markdown. Key capabilities:
- **Reasoning-based OCR**: Generates thinking tokens (20%-500% of output length) to analyze document layout before producing Markdown
- **Complex layout handling**: Excels at documents with unusual layouts, merged table cells, multi-column text
- **Table extraction**: High-quality table-to-markdown conversion with proper formatting
- **RAG-optimized output**: Clean, parseable Markdown ideal for retrieval-augmented generation

**Source:** HuggingFace model card (https://huggingface.co/numind/NuMarkdown-8B-Thinking)
**Confidence:** HIGH
