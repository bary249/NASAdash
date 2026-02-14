import { useState, FormEvent } from 'react';
import { AlertCircle, Loader2, Sparkles } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel — form */}
      <div className="w-full lg:w-[45%] flex flex-col justify-center items-center px-8 bg-white">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <p className="text-2xl font-light tracking-widest text-gray-400 mb-2" style={{ fontFamily: 'Georgia, serif' }}>
            venn
          </p>
          <h1 className="text-2xl font-semibold text-gray-900 mb-8">Welcome</h1>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Username */}
            <div>
              <label className="block text-sm text-gray-600 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-3 border border-gray-200 rounded-lg text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400 transition-all bg-white"
                placeholder="Enter username"
                autoFocus
                required
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm text-gray-600 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-200 rounded-lg text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400 transition-all bg-white"
                placeholder="Enter password"
                required
              />
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-600 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full py-3 bg-gray-900 hover:bg-gray-800 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-all flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Continue'
              )}
            </button>
          </form>

          <p className="text-center text-gray-400 text-xs mt-10">
            &copy; {new Date().getFullYear()} Venn Technologies
          </p>
        </div>
      </div>

      {/* Right panel — gradient with AI preview */}
      <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #e8dff5 0%, #f5d5c8 30%, #fce4c3 50%, #c9daf8 80%, #e0e7ff 100%)',
        }}
      >
        {/* Soft blurred orbs */}
        <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full opacity-60"
          style={{ background: 'radial-gradient(circle, #f9c89b 0%, transparent 70%)' }} />
        <div className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full opacity-50"
          style={{ background: 'radial-gradient(circle, #b8ccf0 0%, transparent 70%)' }} />
        <div className="absolute top-1/3 right-1/3 w-[300px] h-[300px] rounded-full opacity-40"
          style={{ background: 'radial-gradient(circle, #e4d0f8 0%, transparent 70%)' }} />

        {/* AI chat bubble */}
        <div className="relative z-10 bg-white/90 backdrop-blur-sm rounded-full px-6 py-3.5 shadow-lg flex items-center gap-3 max-w-md">
          <span className="text-gray-700 text-sm">How many move-outs are expected next week?</span>
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-gray-500" />
          </div>
        </div>
      </div>
    </div>
  );
}
