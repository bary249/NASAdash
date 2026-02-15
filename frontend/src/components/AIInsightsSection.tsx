/**
 * AI Insights Section - Owner Dashboard V2
 * Embedded chat interface at the top of the dashboard.
 * Auto-sends a request for top 3 interesting facts when property is selected.
 */
import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, Sparkles, RefreshCw, ChevronDown } from 'lucide-react';
import { api } from '../api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface AIInsightsSectionProps {
  propertyId: string;
  propertyName: string;
}

export function AIInsightsSection({ propertyId, propertyName }: AIInsightsSectionProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [chatAvailable, setChatAvailable] = useState<boolean | null>(null);
  const [, setHasAutoSent] = useState(false); // Disabled - was for auto-send
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('ai_insights_collapsed') === 'true'; } catch { return false; }
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const toggleCollapsed = () => {
    setCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('ai_insights_collapsed', String(next)); } catch {}
      return next;
    });
  };

  // Check chat availability on mount
  useEffect(() => {
    api.getChatStatus()
      .then(status => setChatAvailable(status.available))
      .catch(() => setChatAvailable(false));
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-send top 3 facts when property changes - DISABLED
  // useEffect(() => {
  //   if (!propertyId || !chatAvailable || hasAutoSent) return;
  //   
  //   // Reset and auto-send
  //   setMessages([]);
  //   setHasAutoSent(true);
  //   
  //   const autoMessage = "What are the top 3 most interesting or important facts about this property's current performance? Be concise and highlight anything that needs attention.";
  //   
  //   setMessages([{ role: 'user', content: autoMessage }]);
  //   setLoading(true);
  //   
  //   api.sendChatMessage(propertyId, autoMessage, [])
  //     .then(result => {
  //       setMessages(prev => [...prev, { role: 'assistant', content: result.response }]);
  //     })
  //     .catch(error => {
  //       setMessages(prev => [...prev, { 
  //         role: 'assistant', 
  //         content: `Unable to analyze property: ${error instanceof Error ? error.message : 'Unknown error'}` 
  //       }]);
  //     })
  //     .finally(() => setLoading(false));
  // }, [propertyId, chatAvailable, hasAutoSent]);

  // Reset hasAutoSent when property changes
  useEffect(() => {
    setHasAutoSent(false);
    setMessages([]);
  }, [propertyId]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      const result = await api.sendChatMessage(propertyId, userMessage, history);
      setMessages(prev => [...prev, { role: 'assistant', content: result.response }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}` 
      }]);
    } finally {
      setLoading(false);
    }
  };

  const refreshInsights = () => {
    setHasAutoSent(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (chatAvailable === false) {
    return (
      <div className="bg-gradient-to-r from-venn-purple/10 to-violet-50 rounded-venn-lg shadow-venn-card p-5 border border-venn-purple/20">
        <div className="flex items-center gap-3 text-venn-purple">
          <Bot className="w-5 h-5" />
          <span className="font-semibold">Venn Intelligence</span>
          <span className="text-sm text-slate-500">- Configure ANTHROPIC_API_KEY to enable</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-venn-lg shadow-venn-card border border-venn-sand/50 overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center justify-between px-6 py-5 bg-gradient-to-r from-venn-navy via-venn-slate to-venn-navy text-white relative overflow-hidden cursor-pointer select-none"
        onClick={toggleCollapsed}
      >
        {/* Warm glow effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-venn-amber/5 to-transparent pointer-events-none"></div>
        <div className="flex items-center gap-4 relative z-10">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-venn-amber to-venn-copper shadow-lg shadow-venn-amber/20">
            <Sparkles className="w-5 h-5 text-venn-navy" />
          </div>
          <div>
            <h3 className="font-bold text-lg">Venn Intelligence</h3>
            <p className="text-xs text-venn-amber">{propertyName}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 relative z-10">
          <button
            onClick={(e) => { e.stopPropagation(); refreshInsights(); }}
            disabled={loading}
            className="p-2.5 hover:bg-white/10 rounded-xl transition-colors disabled:opacity-50"
            title="Refresh insights"
          >
            <RefreshCw className={`w-4 h-4 text-venn-amber ${loading ? 'animate-spin' : ''}`} />
          </button>
          <ChevronDown className={`w-5 h-5 text-venn-amber transition-transform duration-200 ${collapsed ? '-rotate-90' : ''}`} />
        </div>
      </div>

      {/* Messages */}
      <div className={`overflow-hidden transition-all duration-300 ease-in-out ${collapsed ? 'max-h-0' : 'max-h-[500px]'}`}>
      <div className="max-h-64 overflow-y-auto p-5 space-y-4 bg-gradient-to-b from-venn-cream/30 to-white venn-scrollbar">
        {messages.length === 0 && !loading && (
          <div className="text-center text-slate-400 py-6 text-sm">
            Ask a question about this property's performance...
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-venn-amber/20 to-venn-gold/10 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-venn-copper" />
              </div>
            )}
            <div
              className={`max-w-[85%] px-4 py-3 rounded-venn text-sm ${
                msg.role === 'user'
                  ? 'bg-venn-navy text-white'
                  : 'bg-white text-slate-700 border border-venn-sand/60 shadow-sm'
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-xl bg-venn-cream flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-venn-charcoal" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-venn-amber/20 to-venn-gold/10 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4 text-venn-copper" />
            </div>
            <div className="bg-white px-4 py-3 rounded-venn border border-venn-sand/60 shadow-sm">
              <Loader2 className="w-4 h-4 animate-spin text-venn-amber" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-5 border-t border-venn-sand/40 bg-white">
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask follow-up questions..."
            disabled={loading}
            className="flex-1 px-4 py-3 border border-venn-sand rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-venn-amber/30 focus:border-venn-amber disabled:bg-slate-50 transition-all"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-5 py-3 bg-gradient-to-r from-venn-amber to-venn-copper text-venn-navy rounded-xl hover:from-venn-gold hover:to-venn-amber disabled:bg-slate-200 disabled:from-slate-200 disabled:to-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed transition-all flex items-center gap-2 font-semibold shadow-sm"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}
