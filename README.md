# DevMate AI

DevMate helps software developers understand a codebase and investigate issues using evidence from project documentation. We are building it in small milestones so every component has a clear purpose and can be explained.

## Learning approach

For each milestone: understand the problem, design the inputs and outputs, implement a small feature, run it, inspect behavior, then explain the design and tradeoffs. AI coding tools may assist, but the learner should be able to explain every line they keep.

## Current milestone
A document-grounded FastAPI backend and React project workspace. The frontend now includes project and document management, cited Q&A, conversation history, issue investigation, and approval screens. The backend uses local embeddings, Chroma, LangChain tools, and a LangGraph workflow. Mock mode works without OpenAI billing; OpenAI mode is optional.

## Run locally

From `backend/`, create and activate a Python virtual environment, install the project in editable mode, then start the server:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` for the health response and `http://127.0.0.1:8000/docs` for the interactive API page.

## Project map

- `backend/app/main.py`: creates the FastAPI application, enables local frontend CORS, and connects its routers.
- `frontend/src/App.tsx`: renders the dashboard, document manager, cited chat, history, issue triage, and approval screens.
- `frontend/src/api.ts`: defines response types and makes HTTP requests to the FastAPI endpoints.
- `frontend/src/main.tsx`: mounts the React app into the browser page.
- `frontend/src/styles.css`: defines the dashboard layout, colors, and responsive styles.
- `backend/app/api/health.py`: HTTP route for checking service availability.
- `backend/app/api/chat.py`: validates a chat request and returns the model answer.
- `backend/app/schemas/chat.py`: request and response shapes for chat.
- `backend/app/services/llm_service.py`: sends the question to the configured model provider.
- `backend/app/api/documents.py`: endpoints for adding, uploading, listing, deleting, and searching text documentation.
- `backend/app/api/questions.py`: endpoints for project Q&A, history, issue investigation, pending approvals, and approval decisions.
- `backend/app/schemas/question.py`: question request, structured answer, source citation, and pending investigation shapes.
- `backend/app/services/qa_service.py`: saves grounded answers, citations, and history.
- `backend/app/agents/investigation_graph.py`: orchestrates planner, researcher, reviewer, report, and approval nodes.
- `backend/app/agents/roles.py`: contains the local planner and evidence-review rules.
- `backend/app/schemas/agent.py`: validates the planner and reviewer handoffs with Pydantic.
- `backend/app/agents/investigation_agent.py`: in OpenAI mode, lets the model request one approved project-document search.
- `backend/app/schemas/document.py`: validates document ingestion data.
- `backend/app/services/document_service.py`: chunks document text, stores it, and searches stored chunks.
- `backend/app/rag/langchain_retriever.py`: adapts local vector search to LangChain's retriever interface.
- `backend/app/rag/prompts.py`: keeps the document-grounded LangChain prompt and Pydantic output parser reusable.
- `backend/app/rag/embedding_service.py`: converts text to local embedding vectors.
- `backend/app/rag/vector_store.py`: stores and searches project chunk embeddings in Chroma on disk.
- `backend/scripts/embedding_demo.py`: compares embeddings for related and unrelated text.
- `backend/app/schemas/health.py`: typed response shape for the health endpoint.
- `backend/app/api/projects.py`: HTTP endpoint for creating projects.
- `backend/app/schemas/project.py`: validated project request and response shapes.
- `backend/app/services/project_service.py`: creates, reads, updates, and deletes project records using SQL.
- `backend/app/db/database.py`: opens/closes SQLite connections and creates the application tables, including saved pending approvals.
- `backend/devmate.db`: local database file created when the API starts (ignored by Git).
- `backend/app/services/`: business logic will go here as the app grows.
- `backend/tests/`: automated checks will be added when we reach testing as a lesson.
- `docs/`: product and architecture decisions, including why we make them.

## Planned progression

1. API foundation, CRUD endpoints, and SQLite persistence
2. LLM call behind a provider service
3. Document ingestion and RAG built from understandable Python functions
4. Retrieval evaluation and citations
5. LangChain components where they reduce integration work
6. Bounded tools and an agent loop
7. LangGraph workflow, retries, and approval pauses
8. React UI, persistence, security, and deployment

We will add infrastructure only when the feature needs it. For example, a vector database arrives with document retrieval, not in the initial API milestone.

## Current API endpoints

- `GET /health`: check whether the API responds.
- `POST /chat`: ask the configured LLM a general question.
- `POST /projects`: create a project record in SQLite.
- `GET /projects`: list project records stored in SQLite.
- `POST /projects/{project_id}/documents`: store plain text project documentation and its chunks.
- `POST /projects/{project_id}/documents/upload`: upload a UTF-8 `.txt` file.
- `GET /projects/{project_id}/documents`: list saved documents and chunk counts.
- `DELETE /projects/{project_id}/documents/{document_id}`: delete a document and its chunks.
- `GET /projects/{project_id}/documents/search?query=...`: rank matching chunks using local TF-IDF similarity.
- `GET /projects/{project_id}/documents/vector-search?query=...&min_score=...&filename=...`: find indexed chunks by embedding similarity with optional score and filename filters.
- `GET /projects/{project_id}/documents/langchain-search?query=...&filename=...`: run Chroma vector search through LangChain's retriever interface, optionally filtered to a filename.
- `POST /projects/{project_id}/documents/index`: manually refresh the local embeddings index. Document uploads and deletions also refresh it automatically.
- `POST /projects/{project_id}/ask`: answer a question using matching project chunks and return source excerpts.
- `POST /projects/{project_id}/investigate`: search project evidence, return a structured report, and pause for action-plan approval.
- `POST /projects/{project_id}/investigations/{workflow_id}/approval`: approve or reject saving the suggested action plan.
- `GET /projects/{project_id}/investigations/pending`: list investigations waiting for approval, including after a browser refresh.
- `GET /projects/{project_id}/history`: list saved questions, answers, and their sources.

Use `/docs` in the running local server to try each endpoint.

- `GET /projects/{project_id}`: retrieve one project by its UUID, or receive 404 if it does not exist.
- `DELETE /projects/{project_id}`: delete a project by UUID; returns 204 when successful or 404 when it does not exist.
- `PATCH /projects/{project_id}`: update only supplied fields; returns the updated project or 404 when missing.

## Project data storage

Projects are stored in `backend/devmate.db` using Python's built-in SQLite support. Unlike the earlier in-memory version, records remain after the API server restarts. The database file is local and ignored by Git.

## First model endpoint

`POST /chat` defaults to local mock mode, which makes no external API call. To call OpenAI, set `LLM_MODE=openai` and `OPENAI_API_KEY` in the server environment. Optionally set `OPENAI_MODEL`; the default is `gpt-6-astra`. Never commit an API key. ChatGPT subscription billing is separate from API billing. The first chat endpoint cannot see private project documents yet.











- `GET /projects/{project_id}/action-plans`: list action plans that were saved after approval.

## Frontend setup

The React + TypeScript workspace lives in `frontend/`. It lists and creates projects, manages `.txt` documents, asks document-grounded questions with expandable citations, shows saved history, submits issue investigations, and lets the user approve or reject suggested action plans. The frontend calls `http://127.0.0.1:8000` by default. Start the backend, then in a second terminal run:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The backend allows requests from the local Vite development origins. Set `VITE_API_BASE_URL` only if the backend runs at another address.
