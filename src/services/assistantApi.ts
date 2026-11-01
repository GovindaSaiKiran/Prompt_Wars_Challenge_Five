/**
 * Centralized API Client for EventPrice GenAI Planning Assistant.
 *
 * Communicates exclusively with the FastAPI backend (/api/v1/assistant/*).
 * Never makes direct Gemini API requests or stores API keys in browser storage.
 */

import {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantStatusResponse,
  ConversationMemory,
  ConversationMemoryUpdateRequest,
  ConversationSessionResponse,
  GeneratedEventPlan,
  PlanApprovalRequest,
  PlanApprovalResponse,
  PlanGenerationRequest,
  PlanRefinementRequest,
} from '../types/planning';

const CLOUD_BACKEND_URL = 'https://prompt-wars-c5-api.onrender.com';

export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    const trimmed = envUrl.trim().replace(/\/+$/, '');
    if (
      typeof window !== 'undefined' &&
      window.location.hostname !== 'localhost' &&
      window.location.hostname !== '127.0.0.1'
    ) {
      if (trimmed.includes('localhost') || trimmed.includes('127.0.0.1')) {
        return CLOUD_BACKEND_URL;
      }
    }
    return trimmed;
  }
  if (
    typeof window !== 'undefined' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1'
  ) {
    return CLOUD_BACKEND_URL;
  }
  return '';
};

export type AssistantErrorCode =
  | 'BACKEND_UNAVAILABLE'
  | 'TIMEOUT'
  | 'VALIDATION_ERROR'
  | 'SERVER_ERROR'
  | 'PROVIDER_UNAVAILABLE'
  | 'UNKNOWN';

export class AssistantApiError extends Error {
  statusCode?: number;
  code: AssistantErrorCode;
  userMessage: string;
  details?: any;

  constructor(
    message: string,
    code: AssistantErrorCode = 'UNKNOWN',
    statusCode?: number,
    details?: any
  ) {
    super(message);
    this.name = 'AssistantApiError';
    this.code = code;
    this.statusCode = statusCode;
    this.userMessage = message;
    this.details = details;
  }
}

export type BackendConnectionState = 'connected' | 'connecting' | 'unavailable';

export interface BackendHealthInfo {
  state: BackendConnectionState;
  serviceStatus?: 'ready_live' | 'ready_fallback' | 'unavailable';
  configuredModel?: string;
  configuredProvider?: string;
  errorMessage?: string;
}

/**
 * Cleanly format error responses without exposing server internals or stack traces.
 */
function parseApiErrorResponse(res: Response, jsonBody: any): AssistantApiError {
  let userMessage = '';
  let code: AssistantErrorCode = 'SERVER_ERROR';

  if (res.status === 400 || res.status === 422) {
    code = 'VALIDATION_ERROR';
    if (jsonBody?.detail) {
      if (typeof jsonBody.detail === 'string') {
        userMessage = `Invalid event input: ${jsonBody.detail}`;
      } else if (Array.isArray(jsonBody.detail)) {
        const errorFields = jsonBody.detail
          .map((item: any) => {
            const loc = Array.isArray(item.loc)
              ? item.loc.filter((x: any) => x !== 'body').join('.')
              : '';
            return loc ? `${loc}: ${item.msg || 'invalid value'}` : item.msg;
          })
          .filter(Boolean);
        userMessage = `Invalid event parameters: ${errorFields.slice(0, 3).join(', ')}`;
      } else {
        userMessage = 'Invalid event parameters provided. Please check date, guest count, and budget.';
      }
    } else {
      userMessage = `Validation error (HTTP ${res.status}). Please check input parameters.`;
    }
  } else if (res.status === 503 || res.status === 502 || res.status === 504) {
    code = 'PROVIDER_UNAVAILABLE';
    userMessage = 'The AI planning engine is temporarily unavailable. Deterministic modeling will be used.';
  } else if (res.status >= 500) {
    code = 'SERVER_ERROR';
    userMessage = `The planning engine encountered a server error (HTTP ${res.status}). Please try again with different event criteria.`;
  } else {
    code = 'UNKNOWN';
    userMessage =
      jsonBody?.detail && typeof jsonBody.detail === 'string'
        ? jsonBody.detail
        : `Request failed with status ${res.status}`;
  }

  return new AssistantApiError(userMessage, code, res.status, jsonBody);
}

/**
 * Handle network exceptions and connection timeouts safely.
 */
function parseNetworkError(err: any, endpointName: string): AssistantApiError {
  if (err.name === 'AbortError') {
    return new AssistantApiError(
      `${endpointName} request timed out after 35 seconds. The planning engine took too long to respond. Please try again.`,
      'TIMEOUT',
      408
    );
  }
  return new AssistantApiError(
    `Backend unavailable. Unable to connect to the EventPrice planning engine. Please check that your FastAPI backend is running on http://127.0.0.1:8000.`,
    'BACKEND_UNAVAILABLE',
    503,
    err
  );
}

/**
 * Fetch wrapper that handles localhost / 127.0.0.1 IPv6 resolution fallbacks on Windows
 * and falls back to Vite dev proxy if primary direct connection fails.
 */
async function robustFetch(
  endpointPath: string,
  options: RequestInit = {}
): Promise<Response> {
  const baseUrl = getApiBaseUrl();
  const primaryUrl = `${baseUrl}${endpointPath}`;

  try {
    return await fetch(primaryUrl, options);
  } catch (err: any) {
    // If baseUrl is http://localhost:8000 and failed with network error, attempt http://127.0.0.1:8000
    if (baseUrl.includes('localhost:8000')) {
      const ipv4Url = primaryUrl.replace('localhost:8000', '127.0.0.1:8000');
      try {
        return await fetch(ipv4Url, options);
      } catch {
        // Fall back to relative endpoint via Vite proxy
        try {
          return await fetch(endpointPath, options);
        } catch {
          throw err;
        }
      }
    } else if (baseUrl) {
      try {
        return await fetch(endpointPath, options);
      } catch {
        throw err;
      }
    }
    throw err;
  }
}

/**
 * Check backend health and operational status.
 * Tests /api/v1/assistant/status and falls back to /health if needed.
 */
export async function checkBackendHealth(signal?: AbortSignal): Promise<BackendHealthInfo> {
  try {
    const res = await robustFetch('/api/v1/assistant/status', {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });

    if (res.ok) {
      const data: AssistantStatusResponse = await res.json();
      return {
        state: 'connected',
        serviceStatus: data.service_status as any,
        configuredModel: data.configured_model,
        configuredProvider: data.configured_provider,
      };
    }

    // Fall back to /health endpoint
    const healthRes = await robustFetch('/health', {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });

    if (healthRes.ok) {
      return {
        state: 'connected',
        serviceStatus: 'ready_fallback',
      };
    }

    return {
      state: 'unavailable',
      errorMessage: `Backend returned HTTP ${res.status}`,
    };
  } catch (err: any) {
    return {
      state: 'unavailable',
      errorMessage: err.message || 'Connection refused',
    };
  }
}

/**
 * Fetch assistant operational status, model info, and provider readiness.
 */
export async function fetchAssistantStatus(signal?: AbortSignal): Promise<AssistantStatusResponse> {
  try {
    const res = await robustFetch('/api/v1/assistant/status', {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal,
    });

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Assistant status');
  }
}

/**
 * Generate a complete structured event plan draft from natural language prompt or guided brief.
 */
export async function generateEventPlanApi(
  payload: PlanGenerationRequest,
  signal?: AbortSignal
): Promise<GeneratedEventPlan> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 35000); // 35s timeout
  const effectiveSignal = signal || controller.signal;

  try {
    const res = await robustFetch('/api/v1/assistant/plan/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: effectiveSignal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Plan generation');
  }
}

/**
 * Refine an existing event plan draft based on conversational user adjustments.
 */
export async function refineEventPlanApi(
  payload: PlanRefinementRequest,
  signal?: AbortSignal
): Promise<GeneratedEventPlan> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 35000);
  const effectiveSignal = signal || controller.signal;

  try {
    const res = await robustFetch('/api/v1/assistant/plan/refine', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: effectiveSignal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Plan refinement');
  }
}

/**
 * Commit and approve a structured event plan into persistent database records.
 * Atomically creates Event, EventRequirement, EventBudget, BudgetLineItem, EventTask, TaskDependency, TaskActivity.
 */
export async function approveEventPlanApi(
  payload: PlanApprovalRequest,
  signal?: AbortSignal
): Promise<PlanApprovalResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);
  const effectiveSignal = signal || controller.signal;

  try {
    const res = await robustFetch('/api/v1/assistant/plan/approve', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: effectiveSignal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Plan approval');
  }
}

/**
 * Send a multi-turn conversational discovery turn to the planning assistant.
 * Maintains persistent memory, gates plan generation, and extracts structured facts.
 */
export async function sendAssistantChat(
  payload: AssistantChatRequest,
  signal?: AbortSignal
): Promise<AssistantChatResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);
  const effectiveSignal = signal || controller.signal;

  try {
    const res = await robustFetch('/api/v1/assistant/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: effectiveSignal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Assistant chat');
  }
}

/**
 * Restores conversation messages and structured memory for a session across page reloads.
 */
export async function fetchConversationSession(
  sessionId: string,
  signal?: AbortSignal
): Promise<ConversationSessionResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  const effectiveSignal = signal || controller.signal;

  try {
    const res = await robustFetch(`/api/v1/assistant/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal: effectiveSignal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Restore conversation session');
  }
}

/**
 * Updates structured event memory directly in the persistent database.
 */
export async function updateSessionMemory(
  sessionId: string,
  payload: ConversationMemoryUpdateRequest,
  signal?: AbortSignal
): Promise<ConversationMemory> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  const effectiveSignal = signal || controller.signal;

  try {
    const res = await robustFetch(`/api/v1/assistant/sessions/${encodeURIComponent(sessionId)}/memory/update`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: effectiveSignal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errorJson: any = null;
      try {
        errorJson = await res.json();
      } catch {
        // ignored
      }
      throw parseApiErrorResponse(res, errorJson);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err instanceof AssistantApiError) {
      throw err;
    }
    throw parseNetworkError(err, 'Update conversation memory');
  }
}

