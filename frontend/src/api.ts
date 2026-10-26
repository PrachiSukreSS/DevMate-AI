export type Project = {
  id: string;
  name: string;
  description: string | null;
};

export type NewProject = {
  name: string;
  description: string | null;
};

export type ProjectDocument = {
  document_id: string;
  filename: string;
  chunks_created: number;
};

export type DocumentUploadResult = ProjectDocument & {
  project_id: string;
};

export type AnswerSource = {
  document_id: string;
  filename: string;
  chunk_index: number;
  excerpt: string;
};

export type StructuredProjectAnswer = {
  answer: string;
  suspected_cause: string | null;
  evidence_summary: string;
  confidence: "low" | "medium" | "high";
  suggested_next_steps: string[];
};

export type ProjectAnswer = {
  interaction_id: string;
  workflow_id: string | null;
  planner_query: string | null;
  approval_status: "pending" | "approved" | "rejected" | null;
  action_plan_id: string | null;
  answer: string;
  model: string;
  sources: AnswerSource[];
  structured_answer: StructuredProjectAnswer | null;
};

export type QuestionHistoryItem = ProjectAnswer & {
  question: string;
  created_at: string;
};

export type IssueReport = {
  title: string;
  description: string;
  traceback?: string;
};

export type ActionPlan = {
  id: string;
  workflow_id: string;
  title: string;
  actions: string[];
  created_at: string;
};

export type PendingInvestigation = {
  workflow_id: string;
  title: string;
  response: ProjectAnswer;
  created_at: string;
};

export type Health = {
  status: string;
  service: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error("Could not connect to DevMate API. Is the backend running?");
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? (payload as { detail?: unknown }).detail
        : null;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => {
            if (typeof item !== "object" || item === null) return "Invalid request.";
            const issue = item as { loc?: unknown[]; msg?: string };
            const field = issue.loc?.slice(1).join(".");
            return field ? `${field}: ${issue.msg ?? "Invalid value."}` : issue.msg ?? "Invalid request.";
          }).join(" ")
        : "The request failed.";
    throw new Error(message);
  }
  return payload as T;
}

export function fetchProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function createProject(project: NewProject): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(project),
  });
}

export function fetchProjectDocuments(projectId: string): Promise<ProjectDocument[]> {
  return request<ProjectDocument[]>(`/projects/${projectId}/documents`);
}

export function uploadProjectDocument(projectId: string, file: File): Promise<DocumentUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  return request<DocumentUploadResult>(`/projects/${projectId}/documents/upload`, {
    method: "POST",
    body: formData,
  });
}

export function deleteProjectDocument(projectId: string, documentId: string): Promise<void> {
  return request<void>(`/projects/${projectId}/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function fetchHealth(): Promise<Health> {
  return request<Health>("/health");
}

export function askProject(projectId: string, question: string): Promise<ProjectAnswer> {
  return request<ProjectAnswer>(`/projects/${projectId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export function fetchProjectHistory(projectId: string): Promise<QuestionHistoryItem[]> {
  return request<QuestionHistoryItem[]>(`/projects/${projectId}/history`);
}

export function investigateProject(projectId: string, issue: IssueReport): Promise<ProjectAnswer> {
  return request<ProjectAnswer>(`/projects/${projectId}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(issue),
  });
}

export function decideInvestigationApproval(
  projectId: string,
  workflowId: string,
  approved: boolean,
): Promise<ProjectAnswer> {
  return request<ProjectAnswer>(`/projects/${projectId}/investigations/${workflowId}/approval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
}

export function fetchProjectActionPlans(projectId: string): Promise<ActionPlan[]> {
  return request<ActionPlan[]>(`/projects/${projectId}/action-plans`);
}

export function fetchPendingInvestigations(projectId: string): Promise<PendingInvestigation[]> {
  return request<PendingInvestigation[]>(`/projects/${projectId}/investigations/pending`);
}
