/**
 * SearchBar - Top search bar with Classic Search / AI Assist toggle
 * Matches design: centered search bar with mode toggle buttons
 */
import { useState, useRef, useEffect } from 'react';
import { Search, Sparkles, X } from 'lucide-react';

interface SearchBarProps {
  onSearch: (query: string, isAI: boolean) => void;
  isAIMode: boolean;
  onModeChange: (isAI: boolean) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function SearchBar({ 
  onSearch, 
  isAIMode, 
  onModeChange, 
  isLoading = false,
  placeholder = "Search properties, metrics, or ask AI..."
}: SearchBarProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isAIMode && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isAIMode]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim(), isAIMode);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setQuery('');
      inputRef.current?.blur();
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form onSubmit={handleSubmit} className="relative">
        {/* Search Input Container */}
        <div className={`
          relative bg-white rounded-2xl shadow-lg border-2 transition-all duration-300
          ${isAIMode ? 'border-indigo-400 shadow-indigo-100' : 'border-slate-200'}
        `}>
          {/* Input */}
          <div className="flex items-center px-4 py-3">
            {isAIMode ? (
              <Sparkles className="w-5 h-5 text-indigo-500 mr-3 flex-shrink-0" />
            ) : (
              <Search className="w-5 h-5 text-slate-400 mr-3 flex-shrink-0" />
            )}
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isAIMode ? "Ask AI about your property data..." : placeholder}
              className="flex-1 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none bg-transparent"
              disabled={isLoading}
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="p-1 hover:bg-slate-100 rounded-full transition-colors"
              >
                <X className="w-4 h-4 text-slate-400" />
              </button>
            )}
          </div>

          {/* Mode Toggle Buttons - matching design: dark filled for Classic, white outlined for AI */}
          <div className="flex items-center gap-2 px-4 pb-3">
            <button
              type="button"
              onClick={() => onModeChange(false)}
              className={`
                px-4 py-1.5 text-xs font-medium rounded-full transition-all duration-200
                ${!isAIMode 
                  ? 'bg-slate-800 text-white' 
                  : 'bg-white text-slate-600 border border-slate-300 hover:bg-slate-50'
                }
              `}
            >
              Classic Search
            </button>
            <button
              type="button"
              onClick={() => onModeChange(true)}
              className={`
                px-4 py-1.5 text-xs font-medium rounded-full transition-all duration-200 flex items-center gap-1.5
                ${isAIMode 
                  ? 'bg-slate-800 text-white' 
                  : 'bg-white text-slate-600 border border-slate-300 hover:bg-slate-50'
                }
              `}
            >
              <Sparkles className="w-3 h-3" />
              AI Assist
            </button>
          </div>
        </div>

        {/* Loading indicator */}
        {isLoading && (
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2">
            <div className="flex items-center gap-2 text-xs text-indigo-600">
              <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span>AI is thinking...</span>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
