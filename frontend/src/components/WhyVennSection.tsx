/**
 * Why Venn Owner Dashboard - Competitive differentiation section
 * 
 * Expandable section explaining why Venn's Owner Dashboard is superior
 * to EliseAI's Portfolio Summary Dashboard for property owners/investors.
 */
import { useState } from 'react';
import { ChevronDown, ChevronUp, Shield, Database, DollarSign, Eye, Zap, Building2, Check, X } from 'lucide-react';

export function WhyVennSection() {
  const [expanded, setExpanded] = useState(false);

  const advantages = [
    {
      icon: Building2,
      title: 'Built for Owners, Not Operators',
      description: 'EliseAI\'s dashboard is designed for leasing teams and regional managers. Venn is built for property owners and asset managers who need investment-grade insights, not just operational metrics.',
      venn: true,
      elise: false,
    },
    {
      icon: Database,
      title: 'Direct PMS Integration',
      description: 'We pull data directly from your Yardi (or RealPage, Entrata) PMS via SOAP/API. No CRM lock-in. Your data stays yours, and you can use any leasing platform you want.',
      venn: true,
      elise: false,
    },
    {
      icon: Eye,
      title: 'Drill-Through to Raw Data',
      description: 'Click any metric to see the exact units, residents, or prospects behind it. Full audit trail. EliseAI shows aggregated KPIs but doesn\'t let you verify the underlying data.',
      venn: true,
      elise: false,
    },
    {
      icon: DollarSign,
      title: 'Market Comps & Positioning',
      description: 'See how your property compares to competitors in real-time. Rent positioning, occupancy benchmarks, market context. EliseAI focuses on internal operations, not market intelligence.',
      venn: true,
      elise: false,
    },
    {
      icon: Zap,
      title: 'Real-Time, Not Cached',
      description: 'Every metric is calculated live from your PMS data. No overnight batch jobs, no stale data. What you see is what\'s actually in your system right now.',
      venn: true,
      elise: false,
    },
    {
      icon: Shield,
      title: 'READ-ONLY by Design',
      description: 'We never write to your PMS. Zero risk of data corruption or accidental changes. Pure read-only visibility into your asset performance.',
      venn: true,
      elise: false,
    },
  ];

  const comparisonTable = [
    { feature: 'Target User', venn: 'Owners & Asset Managers', elise: 'Operators & Leasing Teams' },
    { feature: 'Data Source', venn: 'Direct PMS (Yardi, RealPage, Entrata)', elise: 'EliseCRM only (proprietary lock-in)' },
    { feature: 'Drill-Through', venn: 'Full raw data access', elise: 'Aggregated KPIs only' },
    { feature: 'Market Comps', venn: '✓ Built-in', elise: '✗ Not available' },
    { feature: 'Metric Definitions', venn: '✓ Hover tooltips', elise: '✓ Click definitions' },
    { feature: 'Health Scoring', venn: '✓ Customizable thresholds', elise: '✓ Traffic light system' },
    { feature: 'Portfolio View', venn: '✓ All properties at once', elise: '✓ Portfolio aggregation' },
    { feature: 'Financials (NOI, Revenue)', venn: 'Coming Q1 2026', elise: 'Collections only' },
    { feature: 'Investment Metrics', venn: 'Coming (Cap Rate, DSCR)', elise: '✗ Not available' },
    { feature: 'Multi-PMS Support', venn: 'Yardi now, more coming', elise: 'EliseCRM only' },
  ];

  return (
    <div className="bg-gradient-to-r from-venn-amber/5 via-venn-gold/5 to-venn-amber/5 rounded-venn-lg border border-venn-amber/20 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-6 py-5 flex items-center justify-between hover:bg-venn-amber/10 transition-colors"
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center justify-center w-11 h-11 rounded-venn-lg bg-gradient-to-br from-venn-amber to-venn-copper shadow-md shadow-venn-amber/10">
            <Shield className="w-5 h-5 text-venn-navy" />
          </div>
          <div className="text-left">
            <h2 className="text-lg font-bold text-venn-navy">Why Venn Owner Dashboard?</h2>
            <p className="text-sm text-slate-600">How we compare to EliseAI's Portfolio Summary Dashboard</p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-venn-amber" /> : <ChevronDown className="w-5 h-5 text-venn-amber" />}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-6 pb-6 space-y-6">
          {/* Key Advantages */}
          <div>
            <h3 className="text-sm font-bold text-slate-600 uppercase tracking-wider mb-4">Key Advantages</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {advantages.map((adv, idx) => (
                <div key={idx} className="bg-white rounded-venn p-5 shadow-sm border border-venn-sand/50 hover:shadow-venn hover:border-venn-amber/30 transition-all duration-300">
                  <div className="flex items-start gap-3">
                    <div className="p-2.5 bg-venn-amber/10 rounded-xl shrink-0">
                      <adv.icon className="w-4 h-4 text-venn-copper" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-venn-navy text-sm">{adv.title}</h4>
                      <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">{adv.description}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Comparison Table */}
          <div>
            <h3 className="text-sm font-bold text-slate-600 uppercase tracking-wider mb-4">Feature Comparison</h3>
            <div className="bg-white rounded-venn-lg shadow-sm border border-venn-sand/50 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gradient-to-r from-slate-50 to-venn-cream/30">
                  <tr>
                    <th className="px-5 py-4 text-left font-bold text-slate-500 uppercase text-xs tracking-wider">Feature</th>
                    <th className="px-5 py-4 text-center font-bold text-venn-copper uppercase text-xs tracking-wider">Venn Owner Dashboard</th>
                    <th className="px-5 py-4 text-center font-bold text-slate-400 uppercase text-xs tracking-wider">EliseAI Portfolio Dashboard</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-venn-sand/30">
                  {comparisonTable.map((row, idx) => (
                    <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-venn-cream/20'}>
                      <td className="px-5 py-3 text-venn-navy font-medium">{row.feature}</td>
                      <td className="px-5 py-3 text-center">
                        {row.venn.startsWith('✓') ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <Check className="w-4 h-4" />
                            {row.venn.replace('✓ ', '')}
                          </span>
                        ) : row.venn.startsWith('✗') ? (
                          <span className="inline-flex items-center gap-1 text-rose-600">
                            <X className="w-4 h-4" />
                            {row.venn.replace('✗ ', '')}
                          </span>
                        ) : (
                          <span className="text-slate-700">{row.venn}</span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-center">
                        {row.elise.startsWith('✓') ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <Check className="w-4 h-4" />
                            {row.elise.replace('✓ ', '')}
                          </span>
                        ) : row.elise.startsWith('✗') ? (
                          <span className="inline-flex items-center gap-1 text-rose-600">
                            <X className="w-4 h-4" />
                            {row.elise.replace('✗ ', '')}
                          </span>
                        ) : (
                          <span className="text-slate-500">{row.elise}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bottom Line */}
          <div className="bg-gradient-to-r from-venn-navy via-venn-slate to-venn-navy text-white rounded-venn-lg p-6 relative overflow-hidden">
            {/* Warm glow effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-venn-amber/5 to-transparent pointer-events-none"></div>
            <h4 className="font-bold mb-3 text-venn-amber relative z-10">The Bottom Line</h4>
            <p className="text-sm text-slate-300 leading-relaxed relative z-10">
              EliseAI built their dashboard for <strong className="text-white">operators</strong> who already use EliseCRM. 
              We built ours for <strong className="text-white">owners and investors</strong> who want direct PMS access, 
              market intelligence, and investment-grade visibility—without CRM lock-in. 
              Every metric is verifiable with drill-through to raw data.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
