# Hybrid Search Implementation

## Overview

The hybrid search system combines **dense vector** (semantic) search with **sparse vector** (keyword) search to improve recommendation accuracy across different query types.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Hybrid Search                            │
├─────────────────────┬─────────────────────┬─────────────────────┤
│   Dense Vector      │    Sparse Vector    │    Reciprocal       │
│   (Semantic)        │    (Keyword/FTS)    │    Rank Fusion      │
├─────────────────────┼─────────────────────┼─────────────────────┤
│                     │                     │                     │
│  "I want to build   │  "drill" matches   │  RRF Score =       │
│   a wooden shelf"   │   "power drill"    │   1/(k + rank₁) +  │
│                     │   "drill press"    │   1/(k + rank₂)    │
│  → [0.12, -0.34,   │                     │                     │
│      0.56, ...]     │  → ts_rank_cd()    │                     │
│                     │                     │                     │
│  Cosine similarity  │  PostgreSQL FTS     │  Combines both      │
│  with pgvector      │  (GIN index)        │  without score      │
│                     │                     │  calibration        │
└─────────────────────┴─────────────────────┴─────────────────────┘
```

## Why Hybrid Search?

### Dense Vector (Semantic) Search
**Strengths:**
- Good at understanding concepts and intent
- Handles synonyms ("shelf" ≈ "bookcase")
- Works across languages (English ↔ Chinese)

**Weaknesses:**
- May miss exact matches
- Struggles with rare/technical terms
- Can be "too fuzzy" (returns conceptually similar but irrelevant items)

### Sparse Vector (Keyword) Search
**Strengths:**
- Exact matches are highly precise
- Good for technical terms, model numbers, SKUs
- Fast with proper indexing

**Weaknesses:**
- No understanding of synonyms
- Misses conceptual relationships
- Requires exact term matching

### Hybrid Solution
Combining both gives the best of both worlds:
- **Conceptual queries** benefit from semantic search
- **Technical/specific queries** benefit from keyword search
- **Ambiguous queries** get boosted by either method

## Implementation

### 1. Full-Text Search Setup

**GIN Index for Fast Text Search:**
```sql
CREATE INDEX idx_item_types_fts
  ON item_types
  USING gin(to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '')));
```

**How it works:**
- `to_tsvector()` parses text into lexemes (normalized words)
- `to_tsquery()` parses search terms into query structure
- `@@` operator tests if document matches query
- `ts_rank_cd()` calculates relevance score

### 2. Fusion Algorithms

#### Option A: Linear Combination (Default)
```
hybrid_score = semantic_weight × semantic_score + (1 - semantic_weight) × keyword_score
```

**Use when:**
- You want fine-grained control over the balance
- Score ranges are calibrated and comparable

#### Option B: Reciprocal Rank Fusion (RRF)
```
RRF_score = Σ 1 / (k + rank_i)

Where:
- k = constant (typically 20-60)
- rank_i = position in ranking from method i
```

**Use when:**
- Score ranges differ significantly between methods
- You want robust results without calibration
- Rank positions matter more than absolute scores

**Why RRF works well:**
- Score normalization happens automatically
- Items ranked highly in ANY method get boosted
- The k parameter controls "depth sensitivity"
  - Small k (20): Only top ranks matter
  - Large k (60): Deep ranks still contribute

### 3. Query Preprocessing

The `preprocessQuery()` function expands common abbreviations:

```javascript
"I need a drill" → "I need a drill driver"
"Check the pcb"  → "Check the pcb printed circuit board"
"Use the scope"  → "Use the scope oscilloscope"
```

This helps keyword search match variations users might not type.

## Usage

### Basic Hybrid Search
```typescript
import { hybridSearch } from '@/services/reranker/hybrid-scorer'

const results = await hybridSearch("power drill for woodworking", {
  limit: 10,
  semanticWeight: 0.7,  // 70% semantic, 30% keyword
  semanticThreshold: 0.3,
  keywordThreshold: 0.1,
})
```

### With RRF Fusion
```typescript
const results = await hybridSearch("multimeter", {
  useRRF: true,
  rrfK: 60,  // Higher = more forgiving of deep ranks
})
```

### Preprocessing Queries
```typescript
import { preprocessQuery } from '@/services/reranker/hybrid-scorer'

const expanded = preprocessQuery("I need a pcb")
// Result: "I need a pcb printed circuit board"

const results = await hybridSearch(expanded, { useRRF: true })
```

## Performance Considerations

### Query Complexity
| Approach | Queries | Complexity |
|----------|---------|------------|
| Semantic only | 1 | O(n) with HNSW index |
| Hybrid (Linear) | 1 CTE | O(n log n) |
| Hybrid (RRF) | 1 CTE | O(n log n) |

### Index Requirements
```sql
-- Required indexes:
CREATE INDEX idx_item_types_embedding ON item_types USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_item_types_fts ON item_types USING gin(to_tsvector('english', name || ' ' || description));

-- Optional: Trigram for fuzzy matching
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_item_types_trgm ON item_types USING gin(name gin_trgm_ops);
```

### When to Use Each Mode

| Query Type | Recommended Mode | Why |
|------------|------------------|-----|
| "I want to build..." | RRF | Conceptual, benefits from both |
| "DEWALT DCD771C2" | Keyword-heavy (0.3/0.7) | Specific model number |
| "thing for cutting wood" | Semantic-heavy (0.8/0.2) | Very conceptual |
| "saw" | RRF | Ambiguous, many types |

## Testing

Run the test suite to validate hybrid search:
```bash
cd server
npm run test:recommendations:verbose
```

Compare semantic-only vs hybrid:
```typescript
// Test query that benefits from hybrid
const query = "cutting tool"

// Semantic might miss "cutter" vs "cutting"
// Keyword catches "cutting" in description
// Hybrid combines both signals
```

## Future Improvements

1. **Learned Fusion Weights**
   - Train weights based on click-through data
   - A/B test different weight configurations

2. **Query Classification**
   - Detect if query is technical (SKU, model) vs conceptual
   - Automatically adjust weights

3. **Query Expansion with LLM**
   - Use LLM to generate synonyms before search
   - "shelf" → "shelf, bookcase, storage unit"

4. **Multi-language Support**
   - Expand FTS to Chinese (zhparser)
   - Cross-lingual embeddings

5. **BM25 Ranking**
   - Consider BM25 as alternative to ts_rank_cd
   - Better for longer documents
