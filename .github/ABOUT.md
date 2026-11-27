# About Linkwise-Graph

**Linkwise-Graph** is a hybrid **GraphRAG** and **vector retrieval** platform for document intelligence. It ingests PDFs, builds a **Neo4j** knowledge graph and a **ChromaDB** semantic index per account, and answers questions in **vector**, **graph**, or **hybrid** mode—with **[Page X] citations**, reasoning chains, and an interactive **D3** graph explorer.

## Why it exists

Vector-only RAG finds similar text but struggles to follow how entities relate across a document. Linkwise-Graph indexes each upload twice: as a property graph for multi-hop relational reasoning and as dense embeddings for semantic recall. A **Google Gemini** synthesis layer fuses both paths into grounded answers.

## What you get

- **Full-stack application** — FastAPI backend, Next.js 16 frontend, JWT authentication, and tenant-isolated data stores.
- **Production ingestion** — Active-content screening, content-hash deduplication, parse-before-mutate ordering, and rollback on failure.
- **Three query modes** — Trade semantic breadth (`vector`), relational precision (`graph`), or combined coverage (`hybrid`).
- **Open source** — MIT License; documentation and API reference in the root [README](../README.md).

## Links

| Resource | URL |
|----------|-----|
| Live application | http://116.202.210.102:20324 |
| In-app About page | http://116.202.210.102:20324/about |
| Source repository | https://github.com/AmanBadola01/Linkwise-Graph |

## Maintainers: GitHub sidebar “About”

Repository settings (the pencil icon beside **About** on the repo home) should match [repository-metadata.json](./repository-metadata.json). Run `scripts/update-github-about.sh` after granting a token **Administration: Read and write** on this repository (fine-grained PAT) or **repo** scope (classic PAT).