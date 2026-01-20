# API Pagination Guide

This document describes the standardized pagination system for the Jarvis API.

## Overview

All list endpoints support pagination with consistent parameters and response formats. Two pagination strategies are available:

1. **Offset/Limit Pagination** - Traditional page-based navigation (default)
2. **Cursor-based Pagination** - For large datasets where total counts are expensive

## Quick Start

### Making Paginated Requests

```bash
# First page (default)
GET /api/credits/history/user123

# Specific page
GET /api/credits/history/user123?page=2&page_size=50

# Filter with pagination
GET /api/credits/history/user123?page=1&page_size=20&type=purchase
```

### Understanding Responses

All paginated endpoints return data with metadata:

```json
{
  "data": [...],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

## Pagination Parameters

### Standard Parameters

| Parameter | Type | Default | Min | Max | Description |
|-----------|------|---------|-----|-----|-------------|
| `page` | int | 1 | 1 | - | Page number (1-indexed) |
| `page_size` | int | 20 | 1 | 100 | Items per page |

### Cursor Parameters (when available)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Opaque cursor for next/prev page |
| `limit` | int | 20 | Items to return |

## Response Structure

### Offset/Limit Response

```typescript
{
  data: T[],                    // Array of items
  pagination: {
    total: number,              // Total items across all pages
    page: number,               // Current page number
    page_size: number,          // Items per page
    total_pages: number,        // Total number of pages
    has_next: boolean,          // Whether more pages exist
    has_prev: boolean           // Whether previous pages exist
  }
}
```

### Cursor Response

```typescript
{
  data: T[],                    // Array of items
  cursor: {
    next_cursor: string | null, // Cursor for next page
    prev_cursor: string | null, // Cursor for previous page
    has_next: boolean,          // Whether more items exist
    has_prev: boolean           // Whether previous items exist
  }
}
```

## Endpoints with Pagination

### Credits

#### Transaction History
```bash
GET /api/credits/history/{user_id}?page=1&page_size=20&type=purchase
```

**Parameters:**
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 20) - Items per page
- `type` (string, optional) - Filter by transaction type

**Returns:** List of transactions with pagination metadata

---

### Rewards

#### Reward History
```bash
GET /api/rewards/history/{wallet}?days=30&page=1&page_size=20
```

**Parameters:**
- `days` (int, default: 30) - Days of history to fetch
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 20) - Items per page

**Returns:** List of reward claims with pagination

---

### Treasury Reports

#### List Reports
```bash
GET /api/treasury/reports?period=weekly&page=1&page_size=10
```

**Parameters:**
- `period` (string, optional) - Filter by period: daily, weekly, monthly
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 10) - Items per page

**Returns:** List of reports with pagination metadata

---

### Partner Stats

#### Stats History
```bash
GET /api/partner/stats/history?period=day&page=1&page_size=30
```

**Parameters:**
- `period` (string, default: "day") - Period: day, week, or month
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 30) - Items per page

#### Token Stats
```bash
GET /api/partner/tokens?page=1&page_size=50
```

**Parameters:**
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 50) - Items per page

#### Claim History
```bash
GET /api/partner/claims/history?page=1&page_size=50
```

**Parameters:**
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 50) - Items per page

---

## Usage Examples

### JavaScript/TypeScript

```typescript
// Fetch first page
async function fetchTransactions(userId: string, page = 1) {
  const response = await fetch(
    `/api/credits/history/${userId}?page=${page}&page_size=20`
  );
  const data = await response.json();

  console.log(`Page ${data.pagination.page} of ${data.pagination.total_pages}`);
  console.log(`Total items: ${data.pagination.total}`);

  return data;
}

// Navigate pages
async function nextPage(currentData) {
  if (currentData.pagination.has_next) {
    return fetchTransactions(userId, currentData.pagination.page + 1);
  }
}
```

### Python

```python
import requests

def fetch_transactions(user_id: str, page: int = 1, page_size: int = 20):
    """Fetch paginated transaction history."""
    response = requests.get(
        f"http://localhost:8766/api/credits/history/{user_id}",
        params={"page": page, "page_size": page_size}
    )
    return response.json()

# Fetch all pages
def fetch_all_transactions(user_id: str):
    """Fetch all transactions across all pages."""
    all_data = []
    page = 1

    while True:
        result = fetch_transactions(user_id, page=page)
        all_data.extend(result["data"])

        if not result["pagination"]["has_next"]:
            break

        page += 1

    return all_data
```

### cURL

```bash
# First page
curl "http://localhost:8766/api/credits/history/user123?page=1&page_size=20"

# Second page
curl "http://localhost:8766/api/credits/history/user123?page=2&page_size=20"

# Large page size
curl "http://localhost:8766/api/credits/history/user123?page=1&page_size=100"
```

## Best Practices

### 1. Use Appropriate Page Sizes

- **Small lists (< 100 items)**: Use larger page sizes (50-100)
- **Medium lists (100-1000 items)**: Use default (20-50)
- **Large lists (> 1000 items)**: Consider cursor pagination

### 2. Handle Edge Cases

```typescript
// Check if results exist
if (response.pagination.total === 0) {
  console.log("No results found");
}

// Check if page is out of range
if (page > response.pagination.total_pages) {
  console.log("Page out of range");
}
```

### 3. Cache Total Counts

The `total` count is consistent across pages for the same filter. Cache it client-side:

```typescript
let cachedTotal = null;

async function fetchPage(page: number) {
  const data = await fetch(url);

  if (!cachedTotal) {
    cachedTotal = data.pagination.total;
  }

  return data;
}
```

### 4. Show User Feedback

```typescript
// Progress indicator
const progress = (page / total_pages) * 100;
console.log(`Loading: ${progress}%`);

// Item range
const start = (page - 1) * page_size + 1;
const end = Math.min(start + page_size - 1, total);
console.log(`Showing ${start}-${end} of ${total}`);
```

## Cursor Pagination (Advanced)

For endpoints that support cursor-based pagination:

### Making Cursor Requests

```bash
# First page
GET /api/endpoint?limit=20

# Next page (using cursor from previous response)
GET /api/endpoint?cursor=eyJpZCI6MTIzfQ==&limit=20
```

### Cursor Response Example

```json
{
  "data": [...],
  "cursor": {
    "next_cursor": "eyJpZCI6MTQzfQ==",
    "prev_cursor": "eyJpZCI6MTAzfQ==",
    "has_next": true,
    "has_prev": true
  }
}
```

### Cursor Navigation

```typescript
async function fetchCursorPage(cursor: string | null = null) {
  const params = new URLSearchParams();
  if (cursor) params.set('cursor', cursor);
  params.set('limit', '20');

  const response = await fetch(`/api/endpoint?${params}`);
  return response.json();
}

// Navigate forward
async function nextCursorPage(currentData) {
  if (currentData.cursor.has_next) {
    return fetchCursorPage(currentData.cursor.next_cursor);
  }
}
```

## Error Handling

### Invalid Page Number

```json
{
  "error": {
    "code": "VAL_001",
    "message": "Validation error",
    "details": {
      "page": ["ensure this value is greater than or equal to 1"]
    }
  }
}
```

### Invalid Page Size

```json
{
  "error": {
    "code": "VAL_001",
    "message": "Validation error",
    "details": {
      "page_size": ["ensure this value is less than or equal to 100"]
    }
  }
}
```

### Invalid Cursor

```json
{
  "error": {
    "code": "VAL_001",
    "message": "Invalid cursor"
  }
}
```

## Performance Considerations

### Client-Side

1. **Lazy Loading**: Only fetch pages as needed
2. **Caching**: Cache fetched pages to avoid refetching
3. **Prefetching**: Prefetch next page while user views current
4. **Virtual Scrolling**: For large lists, render only visible items

### Server-Side

The pagination system:
- Uses database-level limits where possible
- Caches total counts for 5 minutes (some endpoints)
- Supports efficient cursor-based navigation for large datasets

## Migration from Legacy Endpoints

If you're using older endpoints without pagination:

### Before
```bash
GET /api/endpoint?limit=50
```

### After (Backward Compatible)
```bash
# Same behavior (defaults to page=1, page_size=20)
GET /api/endpoint

# Equivalent to old limit param
GET /api/endpoint?page=1&page_size=50
```

All pagination parameters are optional with sensible defaults, ensuring backward compatibility.

## Support

For issues or questions about pagination:
- Check the OpenAPI docs: `http://localhost:8766/api/docs`
- Review this guide
- Check endpoint-specific documentation
