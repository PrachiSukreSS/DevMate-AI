import { useEffect, useState, type FormEvent } from "react";
import {
  askProject,
  createProject,
  decideInvestigationApproval,
  deleteProjectDocument,
  fetchHealth,
  fetchProjectActionPlans,
  fetchProjectDocuments,
  fetchProjectHistory,
  fetchPendingInvestigations,
  fetchProjects,
  investigateProject,
  uploadProjectDocument,
  type ActionPlan,
  type Project,
  type ProjectAnswer,
  type ProjectDocument,
  type QuestionHistoryItem,
  type PendingInvestigation,
} from "./api";
import "./styles.css";

type WorkspaceSection = "overview" | "documents" | "chat" | "history" | "investigations" | "approvals";

function EvidenceSources({ answer }: { answer: ProjectAnswer }) {
  if (!answer.sources.length) {
    return <p className="no-sources">No matching project documents were found for this answer.</p>;
  }

  return (
    <section className="evidence-panel" aria-label="Evidence sources">
      <h3>Sources</h3>
      {answer.sources.map((source) => (
        <details className="source-card" key={`${source.document_id}-${source.chunk_index}`}>
          <summary>
            <span className="source-file-icon">TXT</span>
            <span>{source.filename}</span>
            <span className="source-chunk">Chunk {source.chunk_index + 1}</span>
          </summary>
          <p>{source.excerpt}</p>
        </details>
      ))}
    </section>
  );
}

function StructuredFindings({ answer }: { answer: ProjectAnswer }) {
  const findings = answer.structured_answer;
  if (!findings) return null;
  return (
    <section className="findings-panel">
      {findings.suspected_cause && <div><h3>Possible cause</h3><p>{findings.suspected_cause}</p></div>}
      <div><h3>Evidence summary</h3><p>{findings.evidence_summary}</p></div>
      <div><h3>Confidence</h3><span className={`confidence-badge ${findings.confidence}`}>{findings.confidence}</span></div>
      {findings.suggested_next_steps.length > 0 && <div><h3>Suggested next steps</h3><ol>{findings.suggested_next_steps.map((step, index) => <li key={`${index}-${step}`}>{step}</li>)}</ol></div>}
    </section>
  );
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>("overview");
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const [history, setHistory] = useState<QuestionHistoryItem[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [question, setQuestion] = useState("");
  const [latestAnswer, setLatestAnswer] = useState<ProjectAnswer | null>(null);
  const [isAsking, setIsAsking] = useState(false);
  const [issueTitle, setIssueTitle] = useState("");
  const [issueDescription, setIssueDescription] = useState("");
  const [traceback, setTraceback] = useState("");
  const [investigationResult, setInvestigationResult] = useState<ProjectAnswer | null>(null);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [pendingInvestigations, setPendingInvestigations] = useState<PendingInvestigation[]>([]);
  const [actionPlans, setActionPlans] = useState<ActionPlan[]>([]);
  const [approvalInProgressId, setApprovalInProgressId] = useState<string | null>(null);
  const [apiIsOnline, setApiIsOnline] = useState<boolean | null>(null);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;

  useEffect(() => {
    let active = true;
    fetchProjects()
      .then((items) => {
        if (!active) return;
        setProjects(items);
        setSelectedProjectId(items[0]?.id ?? null);
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : "Projects could not be loaded.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    fetchHealth().then(() => { if (active) setApiIsOnline(true); }).catch(() => { if (active) setApiIsOnline(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setDocuments([]);
      setHistory([]);
      setPendingInvestigations([]);
      setActionPlans([]);
      return;
    }

    let active = true;
    setDocuments([]);
    setHistory([]);
    setPendingInvestigations([]);
    setActionPlans([]);
    setIsDocumentsLoading(true);
    setIsHistoryLoading(true);

    fetchProjectDocuments(selectedProjectId)
      .then((items) => { if (active) setDocuments(items); })
      .catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "Documents could not be loaded."); })
      .finally(() => { if (active) setIsDocumentsLoading(false); });
    fetchProjectHistory(selectedProjectId)
      .then((items) => { if (active) setHistory([...items].reverse()); })
      .catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "History could not be loaded."); })
      .finally(() => { if (active) setIsHistoryLoading(false); });
    fetchPendingInvestigations(selectedProjectId)
      .then((items) => { if (active) setPendingInvestigations(items); })
      .catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "Pending approvals could not be loaded."); });
    fetchProjectActionPlans(selectedProjectId)
      .then((items) => { if (active) setActionPlans(items); })
      .catch((requestError: unknown) => { if (active) setError(requestError instanceof Error ? requestError.message : "Approved plans could not be loaded."); });

    return () => { active = false; };
  }, [selectedProjectId]);

  async function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSaving(true);
    try {
      const project = await createProject({ name: projectName.trim(), description: projectDescription.trim() || null });
      setProjects((current) => [project, ...current]);
      setSelectedProjectId(project.id);
      setActiveSection("overview");
      setProjectName("");
      setProjectDescription("");
      setShowCreateForm(false);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Project could not be created.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !uploadFile) return;
    const form = event.currentTarget;
    setError(null);
    setIsUploading(true);
    try {
      const uploaded = await uploadProjectDocument(selectedProjectId, uploadFile);
      setDocuments((current) => [uploaded, ...current]);
      setUploadFile(null);
      form.reset();
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Document upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDeleteDocument(document: ProjectDocument) {
    if (!selectedProjectId) return;
    setError(null);
    setDeletingDocumentId(document.document_id);
    try {
      await deleteProjectDocument(selectedProjectId, document.document_id);
      setDocuments((current) => current.filter((item) => item.document_id !== document.document_id));
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Document deletion failed.");
    } finally {
      setDeletingDocumentId(null);
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !question.trim()) return;
    const projectId = selectedProjectId;
    const submittedQuestion = question.trim();
    setError(null);
    setIsAsking(true);
    try {
      const answer = await askProject(projectId, submittedQuestion);
      if (projectId !== selectedProjectId) return;
      setLatestAnswer(answer);
      setQuestion("");
      setHistory((current) => [...current, { ...answer, question: submittedQuestion, created_at: new Date().toISOString() }]);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Your question could not be answered.");
    } finally {
      setIsAsking(false);
    }
  }

  async function handleInvestigate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProjectId || !issueTitle.trim() || !issueDescription.trim()) return;
    const projectId = selectedProjectId;
    setError(null);
    setIsInvestigating(true);
    setInvestigationResult(null);
    try {
      const result = await investigateProject(projectId, {
        title: issueTitle.trim(),
        description: issueDescription.trim(),
        ...(traceback.trim() ? { traceback: traceback.trim() } : {}),
      });
      if (projectId !== selectedProjectId) return;
      setInvestigationResult(result);
      const [newHistory, pending] = await Promise.all([
        fetchProjectHistory(projectId),
        fetchPendingInvestigations(projectId),
      ]);
      setHistory([...newHistory].reverse());
      setPendingInvestigations(pending);
      if (result.approval_status === "pending") setActiveSection("approvals");
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The investigation could not be completed.");
    } finally {
      setIsInvestigating(false);
    }
  }

  async function handleApproval(item: PendingInvestigation, approved: boolean) {
    if (!selectedProjectId) return;
    setError(null);
    setApprovalInProgressId(item.workflow_id);
    try {
      const result = await decideInvestigationApproval(selectedProjectId, item.workflow_id, approved);
      setPendingInvestigations((current) => current.filter((pending) => pending.workflow_id !== item.workflow_id));
      setInvestigationResult(result);
      const [plans, newHistory] = await Promise.all([
        fetchProjectActionPlans(selectedProjectId),
        fetchProjectHistory(selectedProjectId),
      ]);
      setActionPlans(plans);
      setHistory([...newHistory].reverse());
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The approval decision could not be saved.");
    } finally {
      setApprovalInProgressId(null);
    }
  }

  const sectionTitle: Record<WorkspaceSection, string> = {
    overview: selectedProject?.name ?? "Your projects",
    documents: "Project documents",
    chat: "Ask DevMate",
    history: "Conversation history",
    investigations: "Investigate an issue",
    approvals: "Review and approve",
  };
  const sectionSubtitle: Record<WorkspaceSection, string> = {
    overview: selectedProject?.description || "A workspace for project knowledge and evidence-based investigations.",
    documents: "Upload and manage the text documents DevMate can search.",
    chat: "Ask a question about this project's documents and inspect the evidence.",
    history: "Revisit questions, answers, and the sources that supported them.",
    investigations: "Submit an issue report and let DevMate search project evidence.",
    approvals: "Review suggested action plans before saving them to this project.",
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" aria-label="DevMate home"><span className="brand-mark">D</span><span>devmate<span className="brand-period">.</span></span></a>
        <div className="sidebar-section-heading"><span>Your projects</span><span className="project-count">{projects.length}</span></div>
        <nav className="project-list" aria-label="Projects">
          {projects.map((project) => <button className={`project-nav-item ${project.id === selectedProjectId ? "selected" : ""}`} key={project.id} onClick={() => { setSelectedProjectId(project.id); setActiveSection("overview"); }} type="button"><span className="project-dot" aria-hidden="true" /><span className="project-nav-name">{project.name}</span></button>)}
        </nav>
        <button className="new-project-link" onClick={() => { setError(null); setShowCreateForm((current) => !current); }} type="button"><span className="plus-icon">+</span> New project</button>
        {selectedProject && <nav className="workspace-nav" aria-label="Project workspace">
          {(["overview", "documents", "chat", "history", "investigations", "approvals"] as WorkspaceSection[]).map((section) => (
            <button className={activeSection === section ? "workspace-nav-item selected" : "workspace-nav-item"} key={section} onClick={() => setActiveSection(section)} type="button">
              {section === "overview" ? "Overview" : section === "documents" ? "Documents" : section === "chat" ? "Ask DevMate" : section === "history" ? "History" : section === "investigations" ? "Investigate issue" : "Approvals"}
              {section === "documents" && <span>{documents.length}</span>}
              {section === "history" && <span>{history.length}</span>}
              {section === "approvals" && <span>{pendingInvestigations.length}</span>}
            </button>
          ))}
        </nav>}
        <div className="sidebar-footer"><span className="connection-dot" /> Local workspace</div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> {selectedProject?.name ?? "Projects"} <span>/</span> {sectionTitle[activeSection]}</div>
          <div className={`api-status ${apiIsOnline === false ? "offline" : ""}`}><span className="status-dot" /> {apiIsOnline === null ? "Checking API" : apiIsOnline ? "DevMate API online" : "DevMate API offline"}</div>
        </header>
        <section className="page-content">
          <div className="page-heading-row"><div><p className="eyebrow">{selectedProject ? "PROJECT WORKSPACE" : "WORKSPACE"}</p><h1>{sectionTitle[activeSection]}</h1><p className="page-subtitle">{sectionSubtitle[activeSection]}</p></div>{activeSection === "overview" && <button className="primary-button" onClick={() => setShowCreateForm(true)} type="button"><span aria-hidden="true">+</span> New project</button>}</div>
          {error && <div className="error-banner" role="alert">{error}</div>}
          {showCreateForm && <form className="create-card" onSubmit={handleCreateProject}>
            <div className="create-card-heading"><div><p className="eyebrow">GET STARTED</p><h2>Create a project</h2></div><button className="icon-button" onClick={() => setShowCreateForm(false)} type="button" aria-label="Close form">×</button></div>
            <label htmlFor="project-name">Project name</label><input id="project-name" maxLength={100} onChange={(event) => setProjectName(event.target.value)} placeholder="e.g. DevMate Learning" required value={projectName} />
            <label htmlFor="project-description">Description <span className="optional-label">Optional</span></label><textarea id="project-description" maxLength={1000} onChange={(event) => setProjectDescription(event.target.value)} placeholder="What is this project about?" rows={3} value={projectDescription} />
            <div className="form-actions"><button className="secondary-button" onClick={() => setShowCreateForm(false)} type="button">Cancel</button><button className="primary-button" disabled={isSaving || !projectName.trim()} type="submit">{isSaving ? "Creating…" : "Create project"}</button></div>
          </form>}

          {isLoading ? <div className="loading-card"><span className="spinner" /> Loading your projects…</div> : !selectedProject ? (
            <div className="empty-state-card"><div className="empty-art" aria-hidden="true"><span /><span /><span /></div><p className="eyebrow">A CLEAR HOME FOR EVERY CODEBASE</p><h2>Start with your first project</h2><p className="muted-copy">Create a project to keep its documentation, questions, and investigations together.</p><button className="primary-button" onClick={() => setShowCreateForm(true)} type="button">Create your first project</button></div>
          ) : activeSection === "overview" ? (
            <div className="dashboard-grid">
              <article className="overview-card project-summary-card"><div className="card-icon purple-icon">{selectedProject.name.slice(0, 1).toUpperCase()}</div><p className="card-label">ACTIVE PROJECT</p><h2>{selectedProject.name}</h2><p className="muted-copy">{selectedProject.description || "No description added yet."}</p><div className="project-id-row"><span>Project ID</span><code>{selectedProject.id}</code></div></article>
              <article className="overview-card metric-card"><p className="card-label">PROJECT KNOWLEDGE</p><strong>{documents.length}</strong><span>documents</span><button className="text-action" onClick={() => setActiveSection("documents")} type="button">Manage documents →</button></article>
              <article className="overview-card metric-card"><p className="card-label">QUESTIONS ASKED</p><strong>{history.length}</strong><span>saved answers</span><button className="text-action" onClick={() => setActiveSection("chat")} type="button">Ask a question →</button></article>
              <article className="overview-card metric-card"><p className="card-label">NEEDS YOUR REVIEW</p><strong>{pendingInvestigations.length}</strong><span>pending approvals</span><button className="text-action" onClick={() => setActiveSection("approvals")} type="button">Review actions →</button></article>
              <article className="overview-card metric-card"><p className="card-label">SAVED ACTION PLANS</p><strong>{actionPlans.length}</strong><span>approved plans</span><button className="text-action" onClick={() => setActiveSection("approvals")} type="button">View plans →</button></article>
            </div>
          ) : activeSection === "documents" ? (
            <section className="documents-workspace">
              <form className="upload-card" onSubmit={handleUploadDocument}><label htmlFor="document-file">Choose a .txt file</label><div className="upload-controls"><input id="document-file" accept=".txt,text/plain" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} required type="file" /><button className="primary-button" disabled={!uploadFile || isUploading} type="submit">{isUploading ? "Uploading…" : "Upload document"}</button></div><p className="upload-hint">UTF-8 text files, up to 100 KB. Other formats are not supported yet.</p></form>
              {isDocumentsLoading ? <div className="loading-card"><span className="spinner" /> Loading documents…</div> : documents.length ? <div className="document-list" aria-label="Uploaded documents">{documents.map((document) => <article className="document-row" key={document.document_id}><div className="document-file-icon" aria-hidden="true">TXT</div><div className="document-info"><h3>{document.filename}</h3><p>{document.chunks_created} searchable {document.chunks_created === 1 ? "chunk" : "chunks"}</p></div><button className="delete-button" disabled={deletingDocumentId === document.document_id} onClick={() => void handleDeleteDocument(document)} type="button">{deletingDocumentId === document.document_id ? "Deleting…" : "Delete"}</button></article>)}</div> : <div className="empty-documents-card"><div className="empty-art" aria-hidden="true"><span /><span /><span /></div><h2>No documents yet</h2><p className="muted-copy">Upload a .txt file to give this project searchable knowledge.</p></div>}
            </section>
          ) : activeSection === "chat" ? (
            <section className="chat-workspace">
              <div className="chat-transcript" aria-live="polite">
                {history.length === 0 && !latestAnswer && <div className="empty-chat"><div className="card-icon purple-icon">?</div><h2>Ask about this project</h2><p>DevMate searches your uploaded documents and shows the excerpts behind its answer.</p></div>}
                {history.slice(-10).map((item) => <article className="conversation-pair" key={item.interaction_id}><div className="user-message"><span className="message-avatar">You</span><p>{item.question}</p></div><div className="assistant-message"><span className="message-avatar assistant-avatar">D</span><div className="message-content"><p>{item.answer}</p><StructuredFindings answer={item} /><EvidenceSources answer={item} /><span className="model-label">{item.model}</span></div></div></article>)}
                {isAsking && <div className="loading-card"><span className="spinner" /> Searching project evidence…</div>}
              </div>
              <form className="chat-composer" onSubmit={handleAsk}><label htmlFor="chat-question">Your question</label><textarea id="chat-question" maxLength={4000} onChange={(event) => setQuestion(event.target.value)} placeholder="e.g. How does authentication work in this project?" rows={3} value={question} /><div className="composer-footer"><span>Answers use this project's indexed documents.</span><button className="primary-button" disabled={isAsking || !question.trim()} type="submit">{isAsking ? "Searching…" : "Ask DevMate"}</button></div></form>
            </section>
          ) : activeSection === "history" ? (
            <section className="history-list">{isHistoryLoading ? <div className="loading-card"><span className="spinner" /> Loading history…</div> : history.length ? [...history].reverse().map((item) => <article className="history-card" key={item.interaction_id}><div className="history-meta"><span>{new Date(item.created_at).toLocaleString()}</span><span>{item.model}</span></div><h2>{item.question}</h2><p>{item.answer}</p><EvidenceSources answer={item} /></article>) : <div className="empty-documents-card"><h2>No conversation history</h2><p className="muted-copy">Your questions and grounded answers will appear here.</p><button className="primary-button" onClick={() => setActiveSection("chat")} type="button">Ask your first question</button></div>}</section>
          ) : activeSection === "investigations" ? (
            <section className="investigation-workspace"><form className="create-card issue-form" onSubmit={handleInvestigate}><p className="eyebrow">ISSUE TRIAGE</p><h2>Describe the problem</h2><label htmlFor="issue-title">Issue title</label><input id="issue-title" maxLength={100} onChange={(event) => setIssueTitle(event.target.value)} placeholder="e.g. Login returns 401 after token expiry" required value={issueTitle} /><label htmlFor="issue-description">What happened?</label><textarea id="issue-description" maxLength={4000} onChange={(event) => setIssueDescription(event.target.value)} placeholder="Describe what you expected and what happened instead." required rows={4} value={issueDescription} /><label htmlFor="issue-traceback">Traceback or error details <span className="optional-label">Optional</span></label><textarea id="issue-traceback" maxLength={12000} onChange={(event) => setTraceback(event.target.value)} placeholder="Paste the relevant error output, if available." rows={6} value={traceback} /><div className="form-actions"><button className="primary-button" disabled={isInvestigating || !issueTitle.trim() || !issueDescription.trim()} type="submit">{isInvestigating ? "Investigating…" : "Investigate issue"}</button></div></form>
              {isInvestigating && <div className="workflow-status"><span className="spinner" /> Searching project documentation and reviewing evidence…</div>}
              {investigationResult && <article className="result-card"><div className="result-heading"><div><p className="eyebrow">INVESTIGATION REPORT</p><h2>{issueTitle}</h2></div><span className={`workflow-badge ${investigationResult.approval_status ?? "complete"}`}>{investigationResult.approval_status === "pending" ? "Awaiting approval" : investigationResult.approval_status ?? "Completed"}</span></div><p>{investigationResult.answer}</p><StructuredFindings answer={investigationResult} /><EvidenceSources answer={investigationResult} />{investigationResult.approval_status === "pending" && <button className="primary-button" onClick={() => setActiveSection("approvals")} type="button">Review suggested actions</button>}</article>}
            </section>
          ) : (
            <section className="approval-workspace">
              {pendingInvestigations.length ? <div className="pending-list">{pendingInvestigations.map((item) => <article className="approval-card" key={item.workflow_id}><div className="result-heading"><div><p className="eyebrow">AWAITING YOUR DECISION</p><h2>{item.title}</h2><p className="muted-copy">Started {new Date(item.created_at).toLocaleString()}</p></div><span className="workflow-badge pending">Pending</span></div><p>{item.response.answer}</p><StructuredFindings answer={item.response} /><EvidenceSources answer={item.response} /><div className="approval-actions"><button className="secondary-button reject-button" disabled={approvalInProgressId === item.workflow_id} onClick={() => void handleApproval(item, false)} type="button">Reject plan</button><button className="primary-button" disabled={approvalInProgressId === item.workflow_id} onClick={() => void handleApproval(item, true)} type="button">{approvalInProgressId === item.workflow_id ? "Saving decision…" : "Approve and save plan"}</button></div></article>)}</div> : <div className="empty-documents-card"><h2>No pending approvals</h2><p className="muted-copy">When an investigation suggests next steps, you can review them here.</p><button className="primary-button" onClick={() => setActiveSection("investigations")} type="button">Start an investigation</button></div>}
              <div className="saved-plans"><div className="section-title-row"><div><p className="eyebrow">APPROVED BY YOU</p><h2>Saved action plans</h2></div><span className="document-count">{actionPlans.length} saved</span></div>{actionPlans.length ? actionPlans.map((plan) => <article className="saved-plan-card" key={plan.id}><div className="history-meta"><span>{new Date(plan.created_at).toLocaleString()}</span><span>Approved</span></div><h3>{plan.title}</h3><ol>{plan.actions.map((action, index) => <li key={`${index}-${action}`}>{action}</li>)}</ol></article>) : <p className="muted-copy">No action plans have been approved yet.</p>}</div>
            </section>
          )}
        </section>
      </main>
    </div>
  );
}
