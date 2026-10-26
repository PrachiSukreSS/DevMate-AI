# Retrieval Evaluation

Use this small evaluation set to check whether DevMate finds supporting project evidence and rejects unrelated questions. Keep the same saved documents and project ID when comparing retrieval methods.

## Evaluation questions

| Query | Expected source | Expected outcome |
|---|---|---|
| How can a programmer get familiar with a codebase using this tool? | `devmate-guide.txt`, chunk 0 | Retrieve the passage about helping developers understand a software project. |
| Which database stores the project documentation? | `devmate-guide.txt`, chunk 0 | Retrieve the passage that mentions SQLite. |
| Why might an expired access token cause an unauthorized response? | `api-authentication.txt`, chunk 0 | Retrieve the passage about expired tokens and HTTP 401. |
| Which React version powers the dashboard? | None | Return no evidence above the configured threshold. |
| How do Kubernetes pods connect to PostgreSQL? | None | Return no evidence above the configured threshold. |

## Manual evaluation process

1. Run each query against `GET /projects/{project_id}/documents/search` to record the TF-IDF baseline.
2. Run it against `GET /projects/{project_id}/documents/vector-search` with `min_score=0.20` to check the manual Chroma search.
3. Run it against `GET /projects/{project_id}/documents/langchain-search` to check the LangChain retriever adapter.
4. Record the returned filename, chunk index, and score for each route.
5. Count a relevant query as a hit only if its expected source is returned; count an unrelated query as a false positive if any source is returned.
6. Run relevant and unrelated questions through `POST /projects/{project_id}/ask` to check answer and citation behavior.
7. If a relevant source is missing or an unrelated source appears, adjust `VECTOR_SEARCH_MIN_SCORE` and repeat the same queries.

For this small learning dataset, the goal is to retrieve the expected source for all three relevant questions and return no sources for both unrelated questions. This is a starter check, not proof of production quality; more documents and questions are needed for that.

## Planner role evaluation

Compare the previous title-plus-description query with the new `planner_query` returned by `POST /projects/{project_id}/investigate`. Keep the same project documents, vector index, and `min_score=0.20` for every comparison. The baseline query is `title + description`; the planner query also includes safe traceback signals such as an exception class or HTTP status.

### Cases

| Case | Title | Description | Traceback | Expected source |
|---|---|---|---|---|
| Expired token | Authentication failure | Requests return unauthorized after login expires. | `HTTPError: request failed; status_code=401` | `api-authentication.txt`, chunk 0 |
| Codebase orientation | Getting familiar with a codebase | How does this tool help a programmer understand the project? | Omit | `devmate-guide.txt`, chunk 0 |
| Unrelated infrastructure | Kubernetes database connection | How do Kubernetes pods connect to PostgreSQL? | Omit | None |
| Missing product detail | Dashboard version | Which React version powers the dashboard? | Omit | None |

### Procedure

1. For each case, call `POST /projects/{project_id}/investigate` in mock mode and copy its `planner_query` and returned sources. The response pauses for approval; you do not need to approve to inspect the report and sources.
2. In `GET /projects/{project_id}/documents/vector-search`, search once with the baseline query and once with the exact `planner_query`. Keep `min_score=0.20` and compare the top three results.
3. Record whether the expected source appeared in either result set. For unrelated cases, record whether any result appeared.
4. Calculate relevant-source Hit@3 as `relevant cases with expected source in top 3 / relevant cases`. Calculate unrelated false-positive rate as `unrelated cases with any result / unrelated cases`. Planner gain is `planner Hit@3 - baseline Hit@3`.

| Case | Baseline returned expected source? | Planner returned expected source? | Unrelated result returned? |
|---|---|---|---|
| Expired token |  |  | N/A |
| Codebase orientation |  |  | N/A |
| Unrelated infrastructure | N/A | N/A |  |
| Missing product detail | N/A | N/A |  |

This small manual evaluation measures retrieval only. A four-query result is a learning signal, not proof of general quality. Do not claim the planner improves retrieval unless the recorded results show a positive gain without increasing unrelated false positives.
