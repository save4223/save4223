# Requirements Specification: AI-Powered Smart Tool Recommendation Engine (RAG)

## 1. Overview
The "Smart Tool Recommender" is an AI-driven feature integrated into the Save4223 Next.js web application. It allows users to describe their intended project (e.g., "I want to build a wooden drone frame") and receive a curated list of recommended tools and consumables from the laboratory inventory, complete with personalized reasoning.

## 2. Objectives
*   **Improve Accessibility:** Help novice users identify the correct tools for complex tasks.
*   **Enhance Inventory Utility:** Surface relevant tools that users might not know exist in the lab.
*   **Semantic Search:** Move beyond keyword matching to intent-based tool discovery.
*   **High-Quality Ranking:** Use advanced multi-factor reranking to surface the most relevant tools.

## 3. Technical Architecture (RAG Pipeline)

### 3.1. User Input & Query Expansion (LLM)
*   **Action:** User submits a natural language description.
*   **LLM Role:** Analyze the input to identify "Tool Categories" and "Specific Functions."
*   **Output:** A structured search query (e.g., "cutting tools for carbon fiber," "precision measuring instruments").

### 3.2. Vector Retrieval (Vector Database)
*   **Embedding Model:** Convert tool descriptions and names (from `item_types` table) into vector embeddings.
*   **Vector Store:** Store embeddings in **Supabase Vector (pgvector)**.
*   **Matching:** Perform a cosine similarity search between the LLM-expanded query and the tool inventory.

### 3.3. Advanced Multi-Factor Reranking
The reranking system uses a **weighted scoring algorithm** that combines multiple signals:

```
Final Score = w1×SemanticSimilarity + w2×AvailabilityScore +
              w3×CategoryRelevance + w4×PopularityScore + w5×LLMRerankScore
```

#### 3.3.1. Scoring Components

| Component | Weight | Description | Source |
|-----------|--------|-------------|--------|
| **Semantic Similarity** | 0.25 | Vector cosine similarity score | pgvector |
| **Availability Score** | 0.20 | Ratio of available items per type | `items` table |
| **Category Relevance** | 0.15 | LLM-classified category match | LLM analysis |
| **Popularity Score** | 0.10 | Borrow frequency (normalized) | `inventory_transactions` |
| **LLM Rerank Score** | 0.30 | Cross-encoder or LLM pairwise comparison | LLM |

#### 3.3.2. Reranking Pipeline

1. **Initial Retrieval:** Fetch top 50 candidates via vector similarity
2. **Availability Filter:** Remove item types with 0% availability (configurable)
3. **Feature Extraction:** Calculate all scoring components for each candidate
4. **LLM Reranking:** Use LLM to score top 20 candidates against the query
5. **Weighted Fusion:** Combine scores using configurable weights
6. **Final Selection:** Return top K (default: 5) items

#### 3.3.3. LLM Rerank Prompt Template
```
Given the user's project: "{query}"
And these candidate tools:
1. {tool_name}: {tool_description}
2. ...

Score each tool from 0-100 based on relevance to the project.
Consider: task fit, skill level appropriateness, and practical utility.
Return JSON: {"scores": [{"id": 1, "score": 85, "reason": "..."}]}
```

### 3.4. Final Response Generation
*   **Prompting:** Send the project description + the list of $K$ (e.g., 3-5) best-matched tools to the LLM.
*   **Output:** A Markdown-formatted response containing:
    1.  Recommended Tools.
    2.  Recommendation Reason (why this tool is suitable for this specific project).
    3.  Direct links to the tool's location in the lab.

---

## 4. LLM Provider Configuration

### 4.1. Provider Abstraction Layer
The system supports seamless switching between local (Ollama) and external (OpenAI/Anthropic) LLM providers via environment variables.

```typescript
// Environment Variables
LLM_PROVIDER=ollama          # 'ollama' | 'openai' | 'anthropic'
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=llama3.2
OPENAI_API_KEY=sk-...
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_CHAT_MODEL=claude-3-haiku-20241022
```

### 4.2. Provider Interface
```typescript
interface LLMProvider {
  generateEmbedding(text: string): Promise<number[]>
  generateEmbeddings(texts: string[]): Promise<number[][]>
  chat(messages: Message[], options?: ChatOptions): Promise<string>
  chatStream(messages: Message[], options?: ChatOptions): AsyncIterable<string>
  rerank(query: string, candidates: Candidate[]): Promise<RerankResult[]>
}

interface ChatOptions {
  temperature?: number
  maxTokens?: number
  responseFormat?: 'text' | 'json'
}
```

### 4.3. Embedding Dimensions by Provider
| Provider | Model | Dimensions |
|----------|-------|------------|
| Ollama | nomic-embed-text | 768 |
| Ollama | mxbai-embed-large | 1024 |
| OpenAI | text-embedding-3-small | 1536 |
| OpenAI | text-embedding-3-large | 3072 |

**Note:** Database schema must use the largest dimension (3072) to support all providers, with padding for smaller embeddings.

---

## 5. Functional Requirements

### 5.1. Web Interface (Next.js)
*   **AI Chat/Search Component:** A clean text area for project descriptions.
*   **Streaming UI:** Use `ai` SDK (Vercel AI SDK) to stream the recommendation text for a better user experience.
*   **Tool Cards:** Display recommended tools with images (from MinIO/Supabase Storage), status badges, and "Request Access" buttons.

### 5.2. Backend Logic (Server Actions / API Routes)
*   **Pipeline Orchestration:** A specialized service to coordinate between the LLM and pgvector.
*   **Inventory Context:** The system must filter out tools that are marked as `MISSING` or `MAINTENANCE` in the `items` table before showing them to the user.

### 5.3. Data Synchronization
*   **Embedding Worker:** A background job (or database trigger) that updates the vector store whenever a new `item_type` is added or a description is modified.

---

## 6. Testing & Evaluation Framework

### 6.1. Test Dataset
Create a curated test set with ground truth recommendations:

```typescript
interface TestCase {
  id: string
  query: string                    // User project description
  expectedTools: string[]          // Expected tool type IDs
  relevantTools: string[]          // Partially relevant tools
  irrelevantTools: string[]        // Should NOT be recommended
  difficulty: 'easy' | 'medium' | 'hard'
  category: string                 // e.g., "woodworking", "electronics"
}
```

### 6.2. Evaluation Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| **Precision@K** | relevant_in_top_k / K | Fraction of relevant items in top K |
| **Recall@K** | relevant_in_top_k / total_relevant | Coverage of relevant items |
| **MRR** | 1 / rank_of_first_relevant | Mean Reciprocal Rank |
| **NDCG@K** | DCG@K / IDCG@K | Normalized ranking quality |
| **Latency** | avg(response_time_ms) | Average response time |

### 6.3. Automated Test Suite

```typescript
// Test categories
describe('Recommendation Engine', () => {
  describe('Retrieval', () => {
    it('should retrieve semantically similar items')
    it('should handle multi-word queries')
    it('should handle ambiguous queries')
  })

  describe('Reranking', () => {
    it('should prioritize available items')
    it('should boost category-relevant items')
    it('should apply LLM reranking correctly')
    it('should respect weight configuration')
  })

  describe('End-to-End', () => {
    it('should achieve >80% Precision@5 on easy test cases')
    it('should achieve >60% Precision@5 on hard test cases')
    it('should respond within 5 seconds')
  })
})
```

### 6.4. Performance Benchmarking Script

```bash
# Run evaluation suite
npm run test:recommendations

# Output: evaluation-report.json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "config": { "provider": "ollama", "model": "llama3.2" },
  "metrics": {
    "precision@5": 0.82,
    "recall@5": 0.71,
    "mrr": 0.89,
    "ndcg@5": 0.85,
    "avg_latency_ms": 2340
  },
  "per_category": {
    "woodworking": { "precision@5": 0.88 },
    "electronics": { "precision@5": 0.79 }
  }
}
```

### 6.5. A/B Testing Support
- Log all recommendation requests with query, results, and user feedback
- Support for comparing different reranking weight configurations
- Dashboard for monitoring recommendation quality over time

---

## 7. Non-Functional Requirements
*   **Latency:** The initial "thinking" phase should be under 2 seconds; total response under 5 seconds.
*   **Relevance:** At least 80% of recommended tools should be logically applicable to the user's project.
*   **Safety:** The LLM must not recommend dangerous tool combinations without safety warnings.
*   **Configurability:** Reranking weights should be configurable without code changes.

---

## 8. Data Schema Updates (Drizzle ORM)

```typescript name=src/db/schema.ts
import { index } from 'drizzle-orm/pg-core';
import { vector } from 'drizzle-orm/pg-core';

export const itemTypes = pgTable('item_types', {
  // ... existing columns
  embedding: vector('embedding', { dimensions: 3072 }), // Max dimension for all providers
}, (table) => ({
  embeddingIndex: index('embedding_idx').using('hnsw', table.embedding.op('vector_cosine_ops')),
}));
```

---

## 9. Future Enhancements
*   **Usage History:** Recommend tools based on what other users used for similar projects.
*   **Multi-modal RAG:** Allow users to upload a photo of a material or a sketch to get tool recommendations.
*   **Learning to Rank:** Train a custom ranking model on user feedback data.

---

## 10. Implementation Phases

### Phase 1: Database & Infrastructure (Day 1-2)
1.1. Enable `pgvector` extension in Supabase
1.2. Add embedding column to `item_types` table with HNSW index
1.3. Create LLM provider abstraction layer (`/src/lib/llm/`)
1.4. Configure Ollama as default provider with environment toggle

### Phase 2: Embedding Generation (Day 2-3)
2.1. Create embedding service with provider abstraction
2.2. Implement batch embedding for existing item types
2.3. Create admin API to regenerate embeddings
2.4. Add embedding trigger on item_type create/update

### Phase 3: Retrieval & Reranking Engine (Day 3-5)
3.1. Implement vector similarity search service
3.2. Create availability scoring module
3.3. Create popularity scoring module (from transaction history)
3.4. Implement LLM-based reranking with pairwise comparison
3.5. Build weighted fusion reranker with configurable weights
3.6. Create recommendation pipeline orchestrator

### Phase 4: API & Frontend (Day 5-6)
4.1. Create streaming recommendation API route
4.2. Build Project Assistant page with chat UI
4.3. Implement tool cards with status display
4.4. Add navigation and user feedback collection

### Phase 5: Testing & Evaluation (Day 6-7)
5.1. Create test dataset with 20+ test cases
5.2. Implement evaluation metrics (Precision@K, MRR, NDCG)
5.3. Build automated test suite for retrieval
5.4. Build automated test suite for reranking
5.5. Create performance benchmarking script
5.6. Document baseline performance metrics

---

## 11. File Structure After Implementation

```
server/src/
├── app/
│   ├── api/
│   │   ├── admin/embeddings/
│   │   │   └── regenerate/route.ts
│   │   └── user/recommendations/
│   │       └── route.ts
│   └── user/assistant/
│       └── page.tsx
├── lib/
│   └── llm/
│       ├── index.ts                    # Provider factory
│       ├── types.ts                    # Interfaces
│       ├── ollama-provider.ts          # Ollama implementation
│       ├── openai-provider.ts          # OpenAI implementation
│       └── anthropic-provider.ts       # Anthropic implementation
├── services/
│   ├── embedding-service.ts
│   ├── recommendation-service.ts       # Main RAG pipeline
│   └── reranker/
│       ├── index.ts                    # Reranker orchestrator
│       ├── semantic-scorer.ts
│       ├── availability-scorer.ts
│       ├── popularity-scorer.ts
│       ├── llm-reranker.ts
│       └── weighted-fusion.ts
├── test/
│   └── recommendations/
│       ├── test-cases.ts               # Test dataset
│       ├── evaluation.ts               # Metrics calculation
│       ├── retrieval.test.ts
│       └── reranking.test.ts
└── db/
    └── schema.ts                       # Updated with embedding
```