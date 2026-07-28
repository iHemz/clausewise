/**
 * The only bridge to the backend.
 *
 * Everything that talks to the API goes through `request`, so timeouts and
 * error shaping live in exactly one place. Components never call `fetch`.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const DEFAULT_TIMEOUT_MS = 30_000;
// Starting an analysis only extracts and segments, so it returns in seconds —
// but a large scanned PDF can be slow to read, hence more than the default.
const START_TIMEOUT_MS = 60_000;

/** An error carrying the HTTP status, so callers can branch on 404 vs 500. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOptions extends RequestInit {
  /** Abort after this many milliseconds. A hung request is worse than a failed one. */
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, headers, body, ...init } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  // FormData sets its own multipart boundary — forcing a JSON content-type
  // header onto it produces a request the server cannot parse.
  const isFormData = body instanceof FormData;

  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      body,
      signal: controller.signal,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(await readErrorMessage(response), response.status);
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(
        `The request timed out after ${Math.round(timeoutMs / 1000)}s. Very long contracts take longer — try a shorter document.`,
        408,
      );
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

/** Prefer the API's `detail` field; fall back to raw text, then the status line. */
async function readErrorMessage(response: Response): Promise<string> {
  const text = await response.text().catch(() => '');
  if (!text) return response.statusText || `Request failed with ${response.status}`;
  try {
    const parsed: unknown = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
      return String((parsed as { detail: unknown }).detail);
    }
  } catch {
    // Not JSON — the raw text is the best message available.
  }
  return text;
}

export type Severity = 'low' | 'medium' | 'high';

export type RiskCategory =
  | 'unlimited_liability'
  | 'auto_renewal'
  | 'unilateral_termination'
  | 'ip_assignment'
  | 'non_compete'
  | 'indemnity'
  | 'governing_law'
  | 'payment_terms'
  | 'confidentiality'
  | 'limitation_of_liability';

/**
 * Where the pipeline has got to. Reported rather than inferred: the UI names
 * the step it is on, and a name the client invented would eventually disagree
 * with what the server is actually doing.
 */
export type AnalysisStage = 'extracting' | 'segmenting' | 'analyzing' | 'judging' | 'done';

export interface Citation {
  /** Character offset into `ContractDocument.text` where the cited span begins. */
  start: number;
  end: number;
  page: number | null;
  quote: string;
}

export interface Clause {
  id: string;
  heading: string | null;
  text: string;
  start: number;
  end: number;
  page: number | null;
}

export interface Finding {
  clause_id: string;
  title: string;
  category: RiskCategory;
  severity: Severity;
  reason: string;
  suggested_rewrite: string;
  citation: Citation;
  /** Set only when the independent judge pass ran. */
  judge_severity: Severity | null;
  judge_note: string | null;
}

export interface ContractDocument {
  id: string;
  filename: string;
  text: string;
  clauses: Clause[];
  page_count: number | null;
}

export interface Analysis {
  id: string;
  document: ContractDocument;
  findings: Finding[];
  status: 'pending' | 'complete' | 'failed';
  stage: AnalysisStage;
  clauses_total: number;
  /** Clauses whose analysis call has returned — the progress counter. */
  clauses_done: number;
  /** Findings the model produced but could not ground in the source text. */
  dropped_ungrounded: number;
  /** Clauses whose analysis failed — the document was only partly reviewed. */
  clauses_failed: number;
  /**
   * Model providers that produced these findings. More than one means a
   * mid-run failover — worth showing, because severity calibration differs
   * between models.
   */
  providers_used: string[];
  error: string | null;
}

export const api = {
  health: () => request<{ status: string; environment: string }>('/health'),

  analyses: {
    /**
     * Extract, segment and queue the model passes. Returns immediately with a
     * pending analysis whose document text is already populated — that is what
     * lets the user read the contract while the review runs.
     */
    start: (file: File, options: { judge?: boolean } = {}) => {
      const form = new FormData();
      form.append('file', file);
      const query = options.judge === false ? '?judge=false' : '';
      return request<Analysis>(`/analyses/${query}`, {
        method: 'POST',
        body: form,
        timeoutMs: START_TIMEOUT_MS,
      });
    },
    get: (id: string) => request<Analysis>(`/analyses/${id}`),
  },
};
