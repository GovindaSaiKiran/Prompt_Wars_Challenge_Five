/**
 * Backend Gemini AI Integration Service
 * 
 * Proxies all AI event-planning requests securely through the FastAPI backend
 * (/api/v1/ai/event-advice). No API keys or external Google endpoints are
 * touched by the browser client.
 */

export interface GeminiAdviceResult {
  advice: string;
  isLiveAi: boolean;
  provider: string;
  model?: string | null;
  status: string;
}

export async function queryGeminiForEventAdvice(params: {
  userPrompt: string;
  eventName: string;
  location: string;
  guestCount: number;
  targetBudgetInr: number;
  categoryBreakdownSummary: string;
}): Promise<GeminiAdviceResult | null> {
  const apiBase = import.meta.env.VITE_API_BASE_URL || '';
  const url = `${apiBase}/api/v1/ai/event-advice`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000); // 12s timeout for backend response

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: controller.signal,
      body: JSON.stringify({
        user_query: params.userPrompt,
        event_name: params.eventName,
        location: params.location,
        guest_count: params.guestCount,
        target_budget: params.targetBudgetInr,
        category_summary: params.categoryBreakdownSummary,
      }),
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      console.warn(`Backend AI endpoint returned status ${response.status}: ${response.statusText}`);
      return null;
    }

    const data = await response.json();
    return {
      advice: data.advice,
      isLiveAi: Boolean(data.success && data.provider === 'gemini'),
      provider: data.provider,
      model: data.model,
      status: data.status,
    };
  } catch (error) {
    console.warn('Backend AI endpoint call skipped or timed out, using deterministic response:', error);
    return null;
  }
}
