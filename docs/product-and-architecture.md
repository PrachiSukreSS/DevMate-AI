# DevMate product and architecture

## Product goal

Help a software developer understand project material and investigate errors. DevMate should return explanations tied to evidence, show uncertainty when evidence is missing, and require human approval before consequential actions such as submitting issues or modifying a repository.

## First user journey

A developer submits a question about a project. The backend validates it, gathers relevant project evidence, asks a language model to reason over that evidence, then returns an answer with source references. The first increments build a working API, project-management endpoints, and persistent storage before adding AI.

## Component responsibilities

- React will present projects, questions, results, citations, and approval controls.
- FastAPI will expose HTTP endpoints, validate requests, and coordinate application services.
- Python services will contain application logic such as model calls and retrieval.
- RAG will find relevant project passages and give them to the model as context.
- LangChain may later provide reusable model, embedding, and retrieval integrations.
- LangGraph may later coordinate workflows with explicit state, routing, retries, and approval pauses.
- SQLite stores application records during local learning; PostgreSQL and vector storage can be evaluated when deployment and retrieval require them.

## Design principles

1. Build and understand conventional application code before adding agent autonomy.
2. Keep model-provider code behind a service boundary so the rest of the app does not depend on one vendor's API shape.
3. Treat retrieved documents as untrusted input; document text cannot override application rules.
4. Cite evidence and report uncertainty rather than inventing repository facts.
5. Give tools narrow permissions; never offer unrestricted shell or repository-write access to a model.
6. Add frameworks and infrastructure when a specific problem justifies them.

## Initial API contract

`GET /health` returns `{"status":"ok","service":"devmate-api"}`. It confirms the web process can answer requests. It does not yet prove that a model, database, or document index is healthy; those checks will be added only when those components exist.

## Project registration API

`POST /projects` accepts a JSON object with a required nonblank `name` (up to 100 characters) and an optional `description` (up to 1,000 characters). It returns HTTP 201 and a response containing a generated UUID, the normalized name, and the description. Pydantic validates the request before route logic runs. The service stores records in SQLite, so they remain after the API restarts.

`GET /projects` returns a JSON array containing all projects currently stored in SQLite. An empty project collection is returned as `[]`. It is a read operation, so it does not create or change project records.

`GET /projects/{project_id}` looks up one project by its UUID. FastAPI parses the path value as a UUID; malformed IDs are rejected as invalid requests. If the UUID is valid but no project has that ID, the endpoint returns HTTP 404. The service queries SQLite; if there is no matching row, it returns `None` and the API layer turns that into a clear HTTP error.

`DELETE /projects/{project_id}` removes one project from SQLite. If it succeeds, it returns HTTP 204 with no response body. If the UUID is valid but no record exists, the endpoint returns HTTP 404. The service returns `True` when a record was removed and `False` when it was not found; the API layer converts that result into the appropriate HTTP response.

`PATCH /projects/{project_id}` changes only the fields included in the request. The update schema allows a name, a description, or both; a blank or null name is rejected. Sending `"description": null` clears the description. Sending an empty JSON object is rejected because it does not request a change. The service uses Pydantic's `model_dump(exclude_unset=True)` so omitted fields remain unchanged. A missing project returns HTTP 404; a successful update returns the updated project with HTTP 200.

## SQLite persistence

Project records now live in a local SQLite database at `backend/devmate.db`, so they remain after the API process restarts. Python's built-in `sqlite3` module opens connections; `database.py` creates the table and safely closes each connection. The `projects` table has an ID primary key, a required name, and an optional description. SQL `?` placeholders keep values separate from SQL instructions. This simple local database teaches persistence and SQL before we later decide whether PostgreSQL is needed.


## First LLM request

`POST /chat` accepts a question and returns the model's text plus the model name. The route validates the request, while `llm_service.py` handles provider configuration and the API call. The OpenAI SDK reads the secret from `OPENAI_API_KEY`; `OPENAI_MODEL` can select another model available to the user's API project. If no key is configured, the API returns 503 without affecting its other endpoints. Provider failures return a generic 502 message. This first endpoint has no RAG context and must not be treated as an answer grounded in private project files.

## Local mock mode

Chat runs in `LLM_MODE=mock` by default. It returns a predictable demo answer without sending a request to an external model. This lets us learn the API flow without API credits. For a real OpenAI request, set `LLM_MODE=openai` and provide `OPENAI_API_KEY` in the server environment. The selected mode is explicit in the answer's `model` field (`mock-llm` or the configured OpenAI model).

## First RAG ingestion step

`POST /projects/{project_id}/documents` accepts a filename and plain text content. The service splits text into overlapping 1,000-character chunks with 150 characters of overlap, then stores document metadata and chunk text in SQLite. Character-based splitting is a simple teaching step; it is not token-aware and does not create embeddings or answer questions yet. Later lessons will add retrieval, embeddings, and source citations. Deleting a project also deletes its documents and chunks through SQLite foreign-key cascades.

## Local keyword retrieval

`GET /projects/{project_id}/documents/search` searches a project's saved chunks. This first baseline tokenizes the query into words, counts matching occurrences in each chunk, and returns up to 10 chunks ranked by that count. It uses no embeddings and makes no external model call. It is intentionally simple and may miss relevant text when the wording differs; later we will compare it with semantic retrieval using embeddings.

## Document-grounded question endpoint

`POST /projects/{project_id}/ask` embeds the question locally, retrieves matching chunks from Chroma, applies `VECTOR_SEARCH_MIN_SCORE`, and passes accepted evidence to the configured LLM mode. If no chunks meet the threshold, it returns an explicit no-evidence answer and does not call the model. OpenAI mode receives instructions to answer only from the supplied evidence, cite filenames and chunk numbers, and treat document text as untrusted input. Mock mode returns the retrieved sources but clearly says it did not generate an AI answer.

`GET /projects/{project_id}/documents` returns each saved document's ID, filename, and number of stored chunks. An existing project with no documents returns an empty array; an unknown project returns HTTP 404. The SQL `LEFT JOIN` keeps a document visible even if it has no chunks.

`DELETE /projects/{project_id}/documents/{document_id}` deletes a document only when it belongs to the requested project. The database's foreign-key cascade removes its chunks automatically. A successful delete returns HTTP 204 with no body; an unknown document or one owned by another project returns HTTP 404.

## Plain text file upload

`POST /projects/{project_id}/documents/upload` accepts a UTF-8 `.txt` file as multipart form data, with the form field named `file`. It limits the file to 100 KB, converts its bytes to text, then reuses the existing ingestion service to split and store the content. It does not save the original file to disk. FastAPI file uploads require `python-multipart`; JSON request bodies cannot be used for this multipart upload route.

## Project question history

Each `POST /projects/{project_id}/ask` interaction is saved in the `project_questions` table with its question, answer, model label, source excerpts, and creation time. `GET /projects/{project_id}/history` returns these interactions newest first. The project foreign key cascades so deleting a project also deletes its question history.

## TF-IDF retrieval ranking

Document search now uses TF-IDF with cosine similarity instead of raw occurrence counts. TF-IDF gives less weight to words that appear in many chunks and more weight to terms that distinguish a chunk. Cosine similarity returns a normalized score that helps rank chunks against the query. This is still lexical search: it cannot match synonyms or understand meaning, and it uses no external model or API.

## LangChain retriever adapter

`ProjectDocumentRetriever` wraps the manual Chroma vector search behind LangChain's `BaseRetriever` interface. It returns LangChain `Document` objects with source metadata and the configured relevance threshold. Both `/documents/langchain-search` and the `/ask` workflow invoke it using the standard `invoke()` method. LangChain changes the retrieval interface here; FastEmbed, Chroma, and the scoring threshold still implement the underlying search behavior.


## Local embedding index

`POST /projects/{project_id}/documents/index` reads the project's saved SQLite chunks, creates local embeddings with FastEmbed, and upserts them into a persistent Chroma collection. SQLite remains the source of truth for document text and metadata; Chroma stores a searchable vector copy. Repeating the operation updates existing chunk IDs and removes stale vectors for that project. The index is stored under `backend/vector_store/` and excluded from Git. This endpoint builds or refreshes the index used by vector search. The TF-IDF endpoint remains available as a baseline for comparison.


## Embedding-based vector search

`GET /projects/{project_id}/documents/vector-search` embeds the query locally and asks Chroma for the nearest chunks belonging to that project. It returns source metadata and cosine similarity scores using the same response shape as TF-IDF search, so the approaches can be compared. Optional `min_score` and `filename` query parameters filter low-scoring chunks or restrict search to one document. Nearest-neighbor search can return unrelated chunks when no threshold is supplied, so the endpoint exposes an optional threshold for evaluation.


## Vector retrieval in project Q&A

`POST /projects/{project_id}/ask` now uses the local vector index and accepts chunks whose cosine similarity meets `VECTOR_SEARCH_MIN_SCORE`. The default threshold is 0.20, provisionally selected from the first manual comparison: a relevant paraphrase scored about 0.385 and an unrelated question scored about 0.075. This is only an initial calibration from one document and two queries; it must be revisited as the evaluation set and project corpus grow. Document ingestion and deletion now refresh the project index automatically; the index endpoint remains available for retries or manual rebuilds.


## Metadata filtering

The vector search service can filter Chroma results by both project ID and an optional filename. `ProjectDocumentRetriever` carries the filename filter into LangChain retrieval, and the API exposes it as a query parameter on the direct and LangChain search endpoints. Filtering narrows the evidence candidates before similarity ranking; it does not change the embedding model or relevance threshold.


## Reusable RAG prompt

`app/rag/prompts.py` defines the document-grounded system and human messages with LangChain's `ChatPromptTemplate`. `llm_service.py` formats those messages with the current question and retrieved evidence, then passes the messages to the existing OpenAI Responses API integration. This separates prompt design from provider transport; mock mode still makes no external call. Retrieved evidence remains untrusted input and cannot override the system instructions.


## Structured project answers

RAG answers now include a validated structure with an answer, optional suspected cause, evidence summary, qualitative confidence label, and suggested next steps. `PydanticOutputParser` supplies format instructions to the LangChain prompt and validates OpenAI output against `StructuredProjectAnswer`. Mock mode returns an explicit low-confidence structure without a model call. The original top-level `answer` field remains for compatibility; history stores the structured fields as JSON, and the database initializer adds the nullable column to existing databases. Confidence is a qualitative model label, not a calibrated probability.


## First bounded investigation tool

`create_project_search_tool` creates a LangChain tool that can search indexed documentation for one existing project. The project ID is bound by the application, so the tool caller supplies only a short query. It returns at most three evidence chunks and performs no writes or file-system actions. `scripts/run_search_tool.py` invokes the tool directly for learning; this step does not let an LLM choose or call tools yet.


## First issue investigation workflow

`POST /projects/{project_id}/investigate` accepts an issue title, description, and optional traceback. The application invokes its project-scoped, read-only `search_project_docs` tool, then passes the retrieved evidence to the existing structured-answer flow. The model does not choose tools yet; Python controls this first workflow. The question history stores the title and description, not the traceback. In mock mode, the route still returns a predictable low-confidence response without an external API call.


## Model-selected investigation tool

In OpenAI mode, `/investigate` exposes only the project-bound `search_project_docs` function to the Responses API. The application validates the model's function name and arguments, executes at most one read-only search, sends the result back using the function-call output, and parses the final response against the structured Pydantic schema. Mock mode keeps the deterministic local workflow and makes no external call. The one-call limit and project binding constrain this first agent step.

## First LangGraph workflow

`app/agents/investigation_graph.py` represents issue investigation as nodes that share a typed state. The graph first prepares the issue text, then routes to the local mock search path or the OpenAI model-agent path, and finally saves the structured answer and its sources. This makes the workflow's steps and route visible in code. SQLite-backed checkpoints record each run, and the local search node has a bounded retry rule. The graph also pauses for user approval before saving suggested steps as a project action plan. Install the added dependency from `backend/` with `python -m pip install -e .`. The default mock path requires no API key or API billing.

## Persistent LangGraph checkpoints

The issue-investigation graph now compiles with LangGraph's `SqliteSaver`. Each run gets a unique `thread_id`, and the graph saves its node state to `backend/langgraph_checkpoints.db` as it progresses. This is separate from the application database and stays local (the repository ignores `*.db` files). Install `langgraph-checkpoint-sqlite` with the project dependencies. The endpoint returns the graph thread ID as `workflow_id`; a later approval lesson can use it to pause and resume a graph. Traceback text is passed to the model at runtime but is not copied into the checkpoint state.

## Bounded retrieval retry

The graph retries only the local document-search node when Chroma surfaces a SQLite `OperationalError`. It makes at most two attempts total, with a short delay. Validation errors and model-provider errors are not retried; in particular, a 429 or billing/quota response should be fixed at the provider/account level rather than sent again automatically. LangGraph applies retry policies per node, so this retry does not repeat issue preparation or answer persistence.

## Human approval for action plans

After `/investigate` prepares and saves a report, the graph pauses at an approval interrupt and returns `approval_status: "pending"` plus `workflow_id`. Send `POST /projects/{project_id}/investigations/{workflow_id}/approval` with `{"approved": true}` to save the suggested steps as a project action plan in SQLite, or `{"approved": false}` to reject without saving it. The endpoint checks the project ID and confirms the graph is still waiting before resuming it with LangGraph `Command(resume=...)`. The action-plan insert is idempotent for a workflow. This approval gate controls a local database write; the project still has no external tracker or repository-write tool.

## First specialized investigation roles

The graph now has separate planner, researcher, and reviewer nodes. `agents/roles.py` contains the billing-free planner (it builds a short query from the issue title and description) and reviewer (it checks that retrieved chunks are nonempty, unique, under the result limit, and above the configured score threshold). The researcher uses the existing project-scoped search tool in mock mode; OpenAI mode keeps the bounded model-selected tool call. This creates clear role boundaries, but the local planner and reviewer are deterministic Python functions, not independent LLM agents. We still need to compare retrieval and answer quality against the single-agent baseline before claiming a multi-agent benefit.

## Typed role handoffs

The planner now returns an `InvestigationPlan` object containing the bounded `search_query` and full `question`. The reviewer returns an `EvidenceReview` object containing its `passed` decision, notes, and only the accepted chunks. Pydantic validates these shapes before the next node uses them. The handoff models live in `backend/app/schemas/agent.py`; `backend/app/agents/roles.py` produces them. This improves clarity and catches malformed data, but it does not itself improve search relevance. The planner still uses the issue title and description as the baseline query, so the next evaluation must measure search quality before we claim the roles help.

## Traceback-aware planning

The planner now adds only safe technical signals from the last useful traceback lines: an exception class such as `HTTPError` and an HTTP code such as `401`. It never copies the raw traceback into graph state or the returned search query. The query is capped at 200 characters, with title and error signals before the description. The investigation response includes `planner_query`, so a learner can reuse that exact query in `/documents/vector-search` and compare it with the prior title-plus-description query. This is a retrieval hypothesis to evaluate, not a claimed quality improvement.

## Reading approved action plans

`GET /projects/{project_id}/action-plans` returns approved plans newest first. The API router handles the HTTP path and 404 response, the service checks the project and reads SQLite, and `ActionPlanResponse` validates each item. A project with no approved plans returns `[]`; a missing project returns 404.
