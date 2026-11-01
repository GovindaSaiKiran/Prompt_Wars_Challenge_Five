import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Search,
  Cpu,
  Calculator,
  ListCheck,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  ArrowRight,
  Printer,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  FileText,
  DollarSign,
  Layers,
} from 'lucide-react';
import { EventBrief, VendorPriceRecord } from '../types/intelligence';
import { ConversationMemory, GeneratedEventPlan } from '../types/planning';
import {
  BackendHealthInfo,
  checkBackendHealth,
  fetchConversationSession,
  generateEventPlanApi,
  refineEventPlanApi,
  sendAssistantChat,
} from '../services/assistantApi';
import { mapPlanToLedger } from '../utils/planMapper';
import { formatInr } from '../utils/ledgerMath';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  structuredPlan?: GeneratedEventPlan;
  suggestedPrompts?: string[];
  isError?: boolean;
}

interface AgentChatPanelProps {
  currentBrief: EventBrief | null;
  currentVendors: VendorPriceRecord[];
  currentStructuredPlan?: GeneratedEventPlan | null;
  onPlanGenerated: (result: {
    brief: EventBrief;
    vendors: VendorPriceRecord[];
    tasks: any[];
    approvals: any[];
  }) => void;
  onStructuredPlanGenerated?: (plan: GeneratedEventPlan) => void;
  onOpenTableView?: () => void;
  onOpenStructuredPlanView?: () => void;
  onExportPdf?: () => void;
}

const STARTER_PROMPTS = [
  {
    icon: '💍',
    title: 'Beach Wedding',
    prompt: 'Plan a 2-day beach wedding in Goa for 150 guests with ₹35 Lakhs budget.',
    tag: '150 pax • ₹35L',
    bg: 'bg-[#E0F2FE] hover:bg-[#BAE6FD]',
  },
  {
    icon: '🎂',
    title: 'Kids Birthday',
    prompt: 'Plan a fun 5th birthday party in Mumbai for 45 kids with magic show for ₹80k.',
    tag: '45 pax • ₹80k',
    bg: 'bg-[#FEF08A] hover:bg-[#FDE047]',
  },
  {
    icon: '🎪',
    title: 'Community Carnival',
    prompt: 'Plan a Diwali community carnival in Jaipur for 400 people with cultural evening.',
    tag: '400 pax • Cultural',
    bg: 'bg-[#EDE9FE] hover:bg-[#DDD6FE]',
  },
  {
    icon: '👶',
    title: 'Baby Shower',
    prompt: 'Plan a 60-guest pastel theme baby shower in Kolkata with high-tea buffet and decor for ₹1.2L.',
    tag: '60 pax • ₹1.2L',
    bg: 'bg-[#FCE7F3] hover:bg-[#FBCFE8]',
  },
  {
    icon: '🏡',
    title: 'Griha Pravesh',
    prompt: 'Traditional Griha Pravesh & housewarming in Bangalore for 45 relatives with ₹75k budget.',
    tag: '45 pax • ₹75k',
    bg: 'bg-[#FEF3C7] hover:bg-[#FDE68A]',
  },
  {
    icon: '💻',
    title: '24h Hackathon',
    prompt: 'Plan a 24-hour student hackathon in Delhi for 200 participants with ₹3L budget.',
    tag: '200 pax • ₹3L',
    bg: 'bg-[#DCFCE7] hover:bg-[#BBF7D0]',
  },
];

export const AgentChatPanel: React.FC<AgentChatPanelProps> = ({
  currentBrief,
  currentVendors,
  currentStructuredPlan,
  onPlanGenerated,
  onStructuredPlanGenerated,
  onOpenTableView,
  onOpenStructuredPlanView,
  onExportPdf,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-msg',
      sender: 'agent',
      text: `👋 **Hi there! I'm your AI Event Planning Concierge.**\n\nTell me what you're planning in plain words — for example:\n• Event type *(Wedding, Birthday, Community, Corporate, Anniversary)*\n• Destination / City\n• Number of Guests\n• Target Budget *(or ask me for market estimates)*\n\nI will synthesize an editable event brief, creative ideas, deterministic budget allocations, vendor procurement checklist, and a staged timeline!`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      suggestedPrompts: [
        'Beach wedding in Goa for 150 guests, ₹35L budget',
        'Kids 5th birthday in Mumbai for 40 guests, ₹75k',
        'Community cultural festival in Jaipur for 300 pax',
      ],
    },
  ]);

  const [sessionId, setSessionId] = useState<string | null>(() => {
    try {
      return localStorage.getItem('eventprice_concierge_session_id') || null;
    } catch {
      return null;
    }
  });
  const [memory, setMemory] = useState<ConversationMemory | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<string>('Consulting AI Planning Concierge...');
  const [healthInfo, setHealthInfo] = useState<BackendHealthInfo>({ state: 'connecting' });
  const [activePlan, setActivePlan] = useState<GeneratedEventPlan | null>(currentStructuredPlan || null);

  useEffect(() => {
    if (currentStructuredPlan) {
      setActivePlan(currentStructuredPlan);
    }
  }, [currentStructuredPlan]);

  // Restore persistent conversation session and structured memory across page refreshes
  useEffect(() => {
    const savedSessionId = localStorage.getItem('eventprice_concierge_session_id');
    if (savedSessionId) {
      fetchConversationSession(savedSessionId)
        .then((res) => {
          setSessionId(res.session_id);
          setMemory(res.memory);

          if (res.messages && res.messages.length > 0) {
            const mapped: ChatMessage[] = res.messages.map((m) => ({
              id: m.id,
              sender: m.sender === 'assistant' ? 'agent' : 'user',
              text: m.content,
              timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              structuredPlan: m.structured_plan || undefined,
              suggestedPrompts: m.suggested_prompts || [],
            }));
            setMessages(mapped);
          }

          // If session contains a generated plan, restore it into active views
          if (res.memory.plan_generated) {
            const lastPlanMsg = [...(res.messages || [])].reverse().find((m) => m.structured_plan);
            if (lastPlanMsg?.structured_plan) {
              setActivePlan(lastPlanMsg.structured_plan);
              if (onStructuredPlanGenerated) {
                onStructuredPlanGenerated(lastPlanMsg.structured_plan);
              }
              const mapped = mapPlanToLedger(lastPlanMsg.structured_plan);
              onPlanGenerated(mapped);
            }
          }
        })
        .catch((err) => {
          console.warn('Could not restore previous conversation session:', err);
          try {
            localStorage.removeItem('eventprice_concierge_session_id');
          } catch {}
        });
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    const probe = async () => {
      const res = await checkBackendHealth();
      if (isMounted) setHealthInfo(res);
    };
    probe();
    const interval = setInterval(probe, 15000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend?: string, requestPlanGeneration?: boolean) => {
    const queryText = (textToSend || input).trim();
    if (!queryText || isLoading) return;

    const userMsgId = `user-${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setIsLoading(true);

    const isRefining = memory?.plan_generated && (activePlan !== null || currentStructuredPlan !== null);
    setLoadingStep(
      requestPlanGeneration
        ? 'Synthesizing complete structured event plan with deterministic calculations...'
        : isRefining
          ? `Refining "${activePlan?.brief.event_name || 'event'}" in persistent memory...`
          : 'Consulting AI Planning Concierge & updating conversation memory...'
    );

    try {
      const chatRes = await sendAssistantChat({
        message: queryText,
        session_id: sessionId,
        request_plan_generation: requestPlanGeneration,
      });

      // Persist session ID
      setSessionId(chatRes.session_id);
      try {
        localStorage.setItem('eventprice_concierge_session_id', chatRes.session_id);
      } catch {}

      // Update structured memory
      setMemory(chatRes.memory);

      const agentMsgId = `agent-${Date.now()}`;
      const agentMsg: ChatMessage = {
        id: agentMsgId,
        sender: 'agent',
        text: chatRes.message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        structuredPlan: chatRes.structured_plan || undefined,
        suggestedPrompts: chatRes.suggested_prompts || [],
      };

      setMessages((prev) => [...prev, agentMsg]);

      // If a full structured plan was returned, update the active plan and ledger
      if (chatRes.structured_plan) {
        setActivePlan(chatRes.structured_plan);
        if (onStructuredPlanGenerated) {
          onStructuredPlanGenerated(chatRes.structured_plan);
        }
        const mapped = mapPlanToLedger(chatRes.structured_plan);
        onPlanGenerated(mapped);
      }
    } catch (err: any) {
      console.error('Chat generation error:', err);
      checkBackendHealth().then((h) => setHealthInfo(h)).catch(() => {});

      const userNotice =
        err.userMessage ||
        err.message ||
        'Unable to connect to the backend planning engine. Please check that the backend server is running.';

      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        text: `⚠️ **Planning Engine Notice:**\n${userNotice}\n\nYou can rephrase your request or choose one of the starter templates below.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isError: true,
        suggestedPrompts: [
          'Plan a 50-guest birthday party in Bengaluru with ₹60k budget',
          'Traditional wedding in Hyderabad for 200 guests with ₹15L budget',
        ],
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleResetChat = () => {
    if (window.confirm('Start a new event planning conversation? (Current session will be reset)')) {
      try {
        localStorage.removeItem('eventprice_concierge_session_id');
      } catch {}
      setSessionId(null);
      setMemory(null);
      setActivePlan(null);
      setMessages([
        {
          id: 'welcome-msg-reset',
          sender: 'agent',
          text: `👋 **Ready for a new event!**\n\nTell me what you'd like to plan (e.g. *"I want to organize a wedding"*, *"Planning a hackathon in Hyderabad"*, or *"Dinner party for friends"*).\n\nI'll guide you step-by-step and remember all your preferences!`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          suggestedPrompts: [
            'Plan a Get-Together with friends',
            'Plan a Birthday Party for 40 guests',
            'Plan a Wedding in Hyderabad',
            'Corporate Team Offsite',
          ],
        },
      ]);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] min-h-[580px] bg-white border-2 border-black rounded-2xl shadow-[4px_4px_0px_0px_#000] overflow-hidden w-full max-w-full">
      {/* Agent Header Bar */}
      <div className="bg-[#FFE600] border-b-2 border-black px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-white border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000] flex items-center justify-center text-base">
            🎪
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-black text-sm text-black font-heading tracking-tight uppercase">
                AI Planning Concierge
              </h2>
              {healthInfo.state === 'connected' ? (
                <span
                  className="text-[9px] px-2 py-0.5 rounded bg-[#86EFAC] text-black font-black uppercase border border-black flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]"
                  title={
                    healthInfo.serviceStatus === 'ready_live'
                      ? `FastAPI Connected • Live Gemini (${healthInfo.configuredModel})`
                      : 'FastAPI Connected • Deterministic Engine Active'
                  }
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A]" />
                  <span>Connected</span>
                </span>
              ) : healthInfo.state === 'connecting' ? (
                <span
                  className="text-[9px] px-2 py-0.5 rounded bg-[#FEF08A] text-black font-black uppercase border border-black flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]"
                  title="Checking backend connection..."
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#CA8A04] animate-pulse" />
                  <span>Connecting...</span>
                </span>
              ) : (
                <span
                  className="text-[9px] px-2 py-0.5 rounded bg-[#FECACA] text-[#991B1B] font-black uppercase border border-black flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]"
                  title="FastAPI backend offline. Start backend on http://127.0.0.1:8000."
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
                  <span>Backend Unavailable</span>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {currentStructuredPlan && onOpenStructuredPlanView && (
            <button
              onClick={onOpenStructuredPlanView}
              className="flex items-center gap-1.5 text-xs text-black bg-white hover:bg-slate-50 px-2.5 py-1 rounded-lg border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000] font-black transition-all"
              title="Open full interactive structured plan preview"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>View Full Plan</span>
              <ArrowRight className="w-3 h-3 stroke-[2.5]" />
            </button>
          )}

          <button
            onClick={handleResetChat}
            className="p-1.5 text-black bg-white hover:bg-red-50 border-2 border-black rounded-lg shadow-[1.5px_1.5px_0px_0px_#000] transition-all"
            title="Start new event consultation"
          >
            <RotateCcw className="w-3.5 h-3.5 stroke-[2.5]" />
          </button>
        </div>
      </div>

      {/* Structured Event Memory Snapshot Strip */}
      {memory && (memory.confirmed_fields.length > 0 || memory.last_question_asked) && (
        <div className="bg-[#FFFDF0] border-b-2 border-black px-3 py-2 text-xs flex flex-wrap items-center justify-between gap-2 shadow-[0px_1px_0px_0px_#000]">
          <div className="flex flex-wrap items-center gap-1.5 min-w-0">
            <span className="text-[10px] uppercase font-black text-slate-700 shrink-0">
              🧠 Context:
            </span>
            {memory.event_type && (
              <span className="px-2 py-0.5 rounded-full bg-[#FFE600] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>🎪</span>
                <span>{memory.event_type.replace('-', ' ').toUpperCase()}</span>
              </span>
            )}
            {memory.theme && (
              <span className="px-2 py-0.5 rounded-full bg-[#E0E7FF] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>🎯</span>
                <span>{memory.theme}</span>
              </span>
            )}
            {memory.scale && (
              <span className="px-2 py-0.5 rounded-full bg-[#FEF3C7] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>📏</span>
                <span>{memory.scale.toUpperCase()}</span>
              </span>
            )}
            {memory.occasion && (
              <span className="px-2 py-0.5 rounded-full bg-[#E0F2FE] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>👥</span>
                <span>{memory.occasion}</span>
              </span>
            )}
            {memory.expected_guest_count && (
              <span className="px-2 py-0.5 rounded-full bg-[#DCFCE7] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>🎟️</span>
                <span>{memory.expected_guest_count} pax</span>
              </span>
            )}
            {memory.location && (
              <span className="px-2 py-0.5 rounded-full bg-[#FCE7F3] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>📍</span>
                <span>{memory.location}</span>
              </span>
            )}
            {memory.target_budget && memory.budget_provenance === 'user_provided' ? (
              <span className="px-2 py-0.5 rounded-full bg-[#FEF08A] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>💰</span>
                <span>{formatInr(memory.target_budget)} (User Ceiling)</span>
              </span>
            ) : memory.budget_provenance === 'benchmark_estimate' ? (
              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-bold border border-black text-[11px] flex items-center gap-1">
                <span>💡</span>
                <span>Market Estimate Requested</span>
              </span>
            ) : null}
            {memory.event_date && (
              <span className="px-2 py-0.5 rounded-full bg-[#EDE9FE] text-black font-extrabold border border-black text-[11px] flex items-center gap-1 shadow-[1px_1px_0px_0px_#000]">
                <span>📅</span>
                <span>{memory.event_date}</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {memory.ready_for_plan && !memory.plan_generated && (
              <button
                onClick={() => handleSendMessage('Generate the complete structured event plan now', true)}
                className="px-2.5 py-1 rounded-lg bg-[#FFE600] hover:bg-[#FACC15] text-black font-black border-2 border-black text-[11px] shadow-[1.5px_1.5px_0px_0px_#000] flex items-center gap-1 transition-all active:translate-x-0.5 active:translate-y-0.5"
                title="Sufficient event details collected. Click to generate complete plan!"
              >
                <span>⚡</span>
                <span>Generate Plan Now</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 sm:p-4 space-y-4 bg-[#FDFCF7] w-full">
        {/* If only welcome message, display starter quick-launch cards */}
        {messages.length === 1 && (
          <div className="space-y-2 mb-2">
            <div className="text-[11px] font-black text-black uppercase tracking-wider flex items-center gap-1.5 px-0.5">
              <span>⚡ Popular Celebrations (1-Tap Plan)</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {STARTER_PROMPTS.map((sp, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(sp.prompt)}
                  className={`text-left p-2.5 rounded-xl border-2 border-black ${sp.bg} shadow-[2px_2px_0px_0px_#000] transition-all hover:translate-x-[0.5px] hover:translate-y-[0.5px] cursor-pointer`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1.5 text-xs font-black text-black">
                      <span>{sp.icon}</span>
                      <span>{sp.title}</span>
                    </div>
                    <span className="text-[9px] font-black px-1.5 py-0.2 rounded bg-black text-white">
                      {sp.tag}
                    </span>
                  </div>
                  <p className="text-[11px] font-bold text-black/80 line-clamp-1 leading-snug">
                    {sp.prompt}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'} w-full max-w-full`}
          >
            <div className={`flex items-start gap-2 w-full ${msg.sender === 'user' ? 'justify-end' : ''}`}>
              {msg.sender === 'agent' && (
                <div className="w-7 h-7 rounded-xl bg-[#FFE600] border-2 border-black text-black flex items-center justify-center shrink-0 mt-0.5 shadow-[1.5px_1.5px_0px_0px_#000] text-xs">
                  🎪
                </div>
              )}

              <div
                className={`rounded-2xl p-3 sm:p-4 text-xs sm:text-sm leading-relaxed border-2 border-black min-w-0 max-w-full break-words [word-break:break-word] ${msg.sender === 'user'
                    ? 'bg-[#FFE600] text-black rounded-tr-none shadow-[2px_2px_0px_0px_#000] max-w-[85%]'
                    : msg.isError
                      ? 'bg-[#FEE2E2] text-[#991B1B] rounded-tl-none shadow-[2px_2px_0px_0px_#000] flex-1'
                      : 'bg-white text-black rounded-tl-none shadow-[2px_2px_0px_0px_#000] flex-1'
                  }`}
              >
                {/* Provider Badge for Agent Responses */}
                {msg.structuredPlan && (
                  <div className="mb-2 pb-2 border-b border-black/10 flex items-center justify-between gap-2">
                    {msg.structuredPlan.is_live_ai ? (
                      <span className="flex items-center gap-1 text-[10px] font-black text-[#166534] bg-[#DCFCE7] px-2 py-0.5 rounded border border-black">
                        <Sparkles className="w-3 h-3 text-[#16a34a]" />
                        <span>Gemini Live ({msg.structuredPlan.model || 'gemini-3.1-flash-lite'})</span>
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] font-black text-[#854D0E] bg-[#FEF08A] px-2 py-0.5 rounded border border-black">
                        <span className="w-2 h-2 rounded-full bg-[#EAB308] border border-black" />
                        <span>Deterministic AI Fallback</span>
                      </span>
                    )}

                    <span className="text-[10px] font-bold text-slate-500">
                      Draft Preview (Non-Persistent)
                    </span>
                  </div>
                )}

                {/* Message Body */}
                <div className="whitespace-pre-wrap font-sans text-xs sm:text-sm text-black break-words [word-break:break-word] overflow-hidden">
                  {msg.text.split('\n\n').map((para, pIdx) => (
                    <p key={pIdx} className="mb-2 last:mb-0">
                      {para.split('**').map((chunk, cIdx) =>
                        cIdx % 2 === 1 ? (
                          <strong key={cIdx} className="font-black text-black">
                            {chunk}
                          </strong>
                        ) : (
                          chunk
                        )
                      )}
                    </p>
                  ))}
                </div>

                {/* Structured Event Plan Snapshot Ticket */}
                {msg.structuredPlan && (
                  <div className="mt-3 p-3.5 rounded-xl bg-[#FFFBEB] border-2 border-dashed border-black shadow-[1.5px_1.5px_0px_0px_#000] text-xs space-y-2.5">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pb-2 border-b border-black/10">
                      <div>
                        <div className="text-[10px] uppercase font-black text-slate-600">
                          {(() => {
                            const p = msg.structuredPlan.budget_proposal;
                            const prov = p.budget_provenance || msg.structuredPlan.brief.budget_provenance || 'unknown';
                            if (prov === 'unknown' || (!p.target_budget && p.total_allocated === 0)) return 'Budget Status';
                            if (prov === 'ai_suggested' || prov === 'benchmark_estimate') return 'AI Estimate';
                            return 'Total Allocated';
                          })()}
                        </div>
                        <div className="font-black text-black text-sm font-heading">
                          {(() => {
                            const p = msg.structuredPlan.budget_proposal;
                            const prov = p.budget_provenance || msg.structuredPlan.brief.budget_provenance || 'unknown';
                            if (prov === 'unknown' || (!p.target_budget && p.total_allocated === 0)) return 'Budget Not Provided';
                            if (prov === 'ai_suggested' || prov === 'benchmark_estimate') return `~${formatInr(p.target_budget || p.total_allocated)}`;
                            return formatInr(p.total_allocated);
                          })()}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase font-black text-slate-600">Attendees</div>
                        <div className="font-black text-black text-xs">
                          {msg.structuredPlan.brief.expected_guest_count || 'TBD'} pax
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase font-black text-slate-600">Location</div>
                        <div className="font-black text-black text-xs truncate">
                          {msg.structuredPlan.brief.location || 'Local'}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase font-black text-slate-600">Checklist Items</div>
                        <div className="font-black text-black text-xs">
                          {msg.structuredPlan.vendor_checklist.length} Categories
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 pt-0.5">
                      {onOpenStructuredPlanView && (
                        <button
                          onClick={onOpenStructuredPlanView}
                          className="text-[11px] font-black text-black bg-[#FFE600] hover:bg-[#FACC15] px-3 py-1.5 rounded-lg border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000] flex items-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 transition-all"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>Inspect & Edit Full Plan</span>
                          <ArrowRight className="w-3 h-3 stroke-[2.5]" />
                        </button>
                      )}

                      {onOpenTableView && (
                        <button
                          onClick={onOpenTableView}
                          className="text-[11px] font-black text-black bg-[#BAE6FD] hover:bg-[#7DD3FC] px-2.5 py-1.5 rounded-lg border-2 border-black shadow-[1px_1px_0px_0px_#000] flex items-center gap-1 active:translate-x-0.5 active:translate-y-0.5 transition-all"
                        >
                          <Layers className="w-3.5 h-3.5" />
                          <span>View Quotes Ledger</span>
                        </button>
                      )}
                    </div>
                  </div>
                )}

                {/* Suggested Prompts / Follow-ups */}
                {msg.suggestedPrompts && msg.suggestedPrompts.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t-2 border-black/10">
                    <div className="text-[10px] font-black text-black uppercase tracking-wider mb-1.5">
                      ✨ Suggested adjustments / follow-ups:
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.suggestedPrompts.map((sp, spIdx) => (
                        <button
                          key={spIdx}
                          onClick={() => handleSendMessage(sp)}
                          className="text-[11px] font-bold text-left px-2.5 py-0.5 rounded-full bg-white hover:bg-[#FFE600] text-black border border-black shadow-[1px_1px_0px_0px_#000] active:translate-x-0.5 active:translate-y-0.5 transition-all max-w-full break-words"
                        >
                          {sp}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <span className="text-[10px] text-slate-700 mt-1 px-1 font-bold">
              {msg.timestamp}
            </span>
          </div>
        ))}

        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex items-start gap-2 max-w-full">
            <div className="w-7 h-7 rounded-xl bg-[#FFE600] border-2 border-black text-black flex items-center justify-center shrink-0 mt-0.5 shadow-[1.5px_1.5px_0px_0px_#000] text-xs animate-bounce">
              🎪
            </div>

            <div className="rounded-2xl p-3 bg-white border-2 border-black text-xs text-black space-y-1 shadow-[2px_2px_0px_0px_#000] flex-1 min-w-0">
              <div className="flex items-center gap-2 font-black text-black uppercase">
                <span className="w-2 h-2 rounded-full bg-[#10B981] border border-black animate-ping" />
                <span>{loadingStep}</span>
              </div>
              <p className="text-[11px] font-bold text-slate-700 leading-relaxed">
                Calling FastAPI planning engine to generate structured brief, ideas, budget, checklist & timeline...
              </p>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Quick Refinement Shortcuts */}
      <div className="px-3 py-1.5 bg-[#F8F5EE] border-t-2 border-black flex flex-wrap items-center gap-1.5 text-[11px] overflow-hidden">
        <span className="font-black text-black text-[10px] uppercase">⚡ Quick Refine:</span>
        <button
          onClick={() => handleSendMessage('Reduce total budget by 15%')}
          className="px-2 py-0.5 rounded-md bg-white hover:bg-[#FFE600] text-black font-extrabold border border-black shadow-[1px_1px_0px_0px_#000] transition-all text-[11px]"
        >
          📉 -15% Budget
        </button>
        <button
          onClick={() => handleSendMessage('Add live acoustic music band and DJ')}
          className="px-2 py-0.5 rounded-md bg-[#FEF08A] hover:bg-[#FDE047] text-black font-extrabold border border-black shadow-[1px_1px_0px_0px_#000] transition-all text-[11px]"
        >
          🎸 + Live Band
        </button>
        <button
          onClick={() => handleSendMessage('Switch catering to regional South Indian buffet')}
          className="px-2 py-0.5 rounded-md bg-[#BAE6FD] hover:bg-[#7DD3FC] text-black font-extrabold border border-black shadow-[1px_1px_0px_0px_#000] transition-all text-[11px]"
        >
          🍲 Regional Menu
        </button>
        <button
          onClick={() => handleSendMessage('Focus on eco-friendly zero waste decor')}
          className="px-2 py-0.5 rounded-md bg-[#DCFCE7] hover:bg-[#BBF7D0] text-black font-extrabold border border-black shadow-[1px_1px_0px_0px_#000] transition-all text-[11px]"
        >
          🌱 Eco Decor
        </button>
      </div>

      {/* Chat Input Bar */}
      <div className="p-3 bg-white border-t-2 border-black">
        <div className="relative flex items-center gap-2 w-full">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={
              activePlan || currentStructuredPlan
                ? "Refine this plan (e.g. 'Allocate prizes for top 3 winners', 'Cut budget by 15%', 'Add live acoustic music')..."
                : "Describe your event (e.g. 'Hackathon for 100 students with ₹2L budget', 'Birthday in Goa')..."
            }
            className="w-full min-w-0 bg-[#F8F5EE] border-2 border-black rounded-xl px-3.5 py-2 text-xs sm:text-sm text-black placeholder:text-slate-500 font-bold focus:outline-none focus:bg-white shadow-[1.5px_1.5px_0px_0px_#000] resize-none max-h-32 min-h-[40px] leading-relaxed transition-all"
          />

          <button
            onClick={() => handleSendMessage()}
            disabled={!input.trim() || isLoading}
            className={`shrink-0 w-10 h-10 rounded-xl font-black text-xs transition-all flex items-center justify-center border-2 border-black ${input.trim() && !isLoading
                ? 'bg-[#FFE600] hover:bg-[#FACC15] text-black shadow-[2px_2px_0px_0px_#000] active:translate-x-[1px] active:translate-y-[1px] active:shadow-none cursor-pointer'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none'
              }`}
            title="Send prompt to agent"
          >
            <Send className="w-4 h-4 stroke-[3]" />
          </button>
        </div>
      </div>
    </div>
  );
};
