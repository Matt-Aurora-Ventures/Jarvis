import React, { useState, useCallback } from 'react'
import type {
  InvestmentDecision,
  AgentReport,
  DebateRound,
  RiskAssessment,
} from './useInvestmentData'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function actionColor(action: string): string {
  switch (action) {
    case 'REBALANCE':
      return 'text-green-400'
    case 'HOLD':
      return 'text-gray-400'
    case 'EMERGENCY_EXIT':
      return 'text-red-400'
    default:
      return 'text-gray-400'
  }
}

function actionBg(action: string): string {
  switch (action) {
    case 'REBALANCE':
      return 'bg-green-400/10 border-green-500/30'
    case 'HOLD':
      return 'bg-gray-400/10 border-gray-500/30'
    case 'EMERGENCY_EXIT':
      return 'bg-red-400/10 border-red-500/30'
    default:
      return 'bg-gray-400/10 border-gray-500/30'
  }
}

function formatUSD(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(2)}K`
  return `$${val.toFixed(2)}`
}

function confidenceBar(pct: number): string {
  if (pct >= 80) return 'bg-green-500'
  if (pct >= 60) return 'bg-yellow-500'
  return 'bg-red-500'
}

// ---------------------------------------------------------------------------
// Sub-components for expanded detail
// ---------------------------------------------------------------------------

const AGENT_ROLES: Record<string, string> = {
  Grok: 'Sentiment & X analysis',
  Claude: 'Risk assessment',
  ChatGPT: 'Macro & structure',
  Dexter: 'Fundamental validation',
}

function AgentReportCard({ report }: { report: AgentReport }) {
  const role = AGENT_ROLES[report.agent] ?? 'Analysis'
  return (
    <div className="bg-gray-800/60 rounded-lg p-3">
      <div className="flex items-center justify-between mb-0.5">
        <div>
          <span className="text-sm font-medium text-white">{report.agent}</span>
          <span className="text-xs text-gray-600 ml-2">{role}</span>
        </div>
        <span
          className={`text-xs font-medium px-2 py-0.5 rounded ${
            report.recommendation === 'REBALANCE'
              ? 'bg-green-500/20 text-green-400'
              : report.recommendation === 'HOLD'
              ? 'bg-gray-500/20 text-gray-300'
              : 'bg-red-500/20 text-red-400'
          }`}
        >
          {report.recommendation}
        </span>
      </div>
      <div className="flex items-center gap-2 mb-2 mt-1.5">
        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${confidenceBar(report.confidence)}`}
            style={{ width: `${report.confidence}%` }}
          />
        </div>
        <span className="text-xs text-gray-400">{report.confidence}%</span>
      </div>
      <p className="text-xs text-gray-400 leading-relaxed">{report.reasoning}</p>
    </div>
  )
}

function DebateRoundCard({ round }: { round: DebateRound }) {
  return (
    <div className="bg-gray-800/60 rounded-lg p-3">
      <div className="text-xs font-medium text-gray-500 mb-2">Round {round.round}</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-2">
        <div className="border-l-2 border-green-500 pl-3">
          <span className="text-xs font-medium text-green-400 block mb-1">Bull</span>
          <p className="text-xs text-gray-400 leading-relaxed">{round.bull_argument}</p>
        </div>
        <div className="border-l-2 border-red-500 pl-3">
          <span className="text-xs font-medium text-red-400 block mb-1">Bear</span>
          <p className="text-xs text-gray-400 leading-relaxed">{round.bear_argument}</p>
        </div>
      </div>
      <p className="text-xs text-gray-500 italic">{round.moderator_summary}</p>
    </div>
  )
}

function RiskPanel({ risk }: { risk: RiskAssessment }) {
  const riskColor =
    risk.overall_risk === 'LOW'
      ? 'text-green-400'
      : risk.overall_risk === 'MEDIUM'
      ? 'text-yellow-400'
      : 'text-red-400'

  return (
    <div className="bg-gray-800/60 rounded-lg p-3">
      <div className="text-xs font-medium text-gray-500 mb-2">Risk Assessment</div>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-gray-500">Overall Risk</span>
          <div className={`font-semibold ${riskColor}`}>{risk.overall_risk}</div>
        </div>
        <div>
          <span className="text-gray-500">Max Drawdown</span>
          <div className="text-white font-semibold">{risk.max_drawdown_pct.toFixed(1)}%</div>
        </div>
        <div>
          <span className="text-gray-500">VaR (95%)</span>
          <div className="text-white font-semibold">{formatUSD(risk.var_95)}</div>
        </div>
        <div>
          <span className="text-gray-500">Concentration</span>
          <div className="text-white font-semibold">{risk.concentration_risk}</div>
        </div>
        <div className="col-span-2">
          <span className="text-gray-500">Liquidity</span>
          <div className="text-white font-semibold">{risk.liquidity_risk}</div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

interface AgentConsensusLogProps {
  decisions: InvestmentDecision[]
  loading: boolean
  onFetchDetail: (id: string) => Promise<InvestmentDecision>
}

export function AgentConsensusLog({
  decisions,
  loading,
  onFetchDetail,
}: AgentConsensusLogProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detailCache, setDetailCache] = useState<Record<string, InvestmentDecision>>({})
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null)

  const toggleExpand = useCallback(
    async (id: string) => {
      if (expandedId === id) {
        setExpandedId(null)
        return
      }

      setExpandedId(id)

      // Fetch full detail if not cached
      if (!detailCache[id]) {
        setLoadingDetail(id)
        try {
          const detail = await onFetchDetail(id)
          setDetailCache(prev => ({ ...prev, [id]: detail }))
        } catch (e) {
          console.error('Failed to fetch decision detail:', e)
        } finally {
          setLoadingDetail(null)
        }
      }
    },
    [expandedId, detailCache, onFetchDetail],
  )

  // Loading
  if (loading && decisions.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-52 mb-4" />
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Agent Consensus Log</h2>

      {decisions.length === 0 ? (
        <div className="text-sm text-gray-500 text-center py-8">
          No investment decisions recorded yet.
        </div>
      ) : (
        <div className="space-y-2">
          {decisions.map(decision => {
            const isExpanded = expandedId === decision.id
            const detail = detailCache[decision.id]
            const isDetailLoading = loadingDetail === decision.id

            return (
              <div key={decision.id}>
                {/* Row */}
                <button
                  onClick={() => toggleExpand(decision.id)}
                  className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                    isExpanded
                      ? actionBg(decision.action)
                      : 'bg-gray-800/40 border-gray-700/50 hover:bg-gray-800'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      {/* Expand chevron */}
                      <svg
                        className={`w-4 h-4 text-gray-500 flex-shrink-0 transition-transform ${
                          isExpanded ? 'rotate-90' : ''
                        }`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>

                      {/* Action badge */}
                      <span className={`text-xs font-bold ${actionColor(decision.action)}`}>
                        {decision.action}
                      </span>

                      {/* Summary */}
                      <span className="text-sm text-gray-300 truncate">{decision.summary}</span>
                    </div>

                    <div className="flex items-center gap-4 flex-shrink-0">
                      {/* Confidence */}
                      <div className="flex items-center gap-1.5">
                        <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${confidenceBar(decision.confidence)}`}
                            style={{ width: `${decision.confidence}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">{decision.confidence}%</span>
                      </div>

                      {/* NAV */}
                      <span className="text-xs text-gray-500">{formatUSD(decision.nav_at_decision)}</span>

                      {/* Date */}
                      <span className="text-xs text-gray-600 whitespace-nowrap">
                        {new Date(decision.timestamp).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </button>

                {/* Expanded detail */}
                {isExpanded && (
                  <div className="mt-1 ml-7 mr-1 mb-2 space-y-3">
                    {isDetailLoading ? (
                      <div className="flex items-center gap-2 text-sm text-gray-500 py-4">
                        <svg
                          className="w-4 h-4 animate-spin"
                          viewBox="0 0 24 24"
                          fill="none"
                        >
                          <circle
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="3"
                            strokeDasharray="32"
                            strokeLinecap="round"
                          />
                        </svg>
                        Loading detail...
                      </div>
                    ) : detail ? (
                      <>
                        {/* ── Step 1: Analyst Layer ── */}
                        {detail.agent_reports && detail.agent_reports.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1.5">
                              <span className="bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">1</span>
                              Analyst Layer
                            </h4>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                              {detail.agent_reports.map((report, idx) => (
                                <AgentReportCard key={idx} report={report} />
                              ))}
                            </div>
                          </div>
                        )}

                        {/* ── Step 2: Bull vs Bear Debate ── */}
                        {detail.debate_rounds && detail.debate_rounds.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1.5">
                              <span className="bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">2</span>
                              Bull vs Bear Debate
                            </h4>
                            <div className="space-y-2">
                              {detail.debate_rounds.map((round, idx) => (
                                <DebateRoundCard key={idx} round={round} />
                              ))}
                            </div>
                          </div>
                        )}

                        {/* ── Step 3: Risk Officer ── */}
                        {detail.risk_assessment && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1.5">
                              <span className="bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">3</span>
                              Risk Officer
                            </h4>
                            <RiskPanel risk={detail.risk_assessment} />
                          </div>
                        )}

                        {/* ── Step 4: Trader Decision ── */}
                        {detail.new_weights && Object.keys(detail.new_weights).length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1.5">
                              <span className="bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">4</span>
                              Trader Decision
                            </h4>
                            <div className="bg-gray-800/60 rounded-lg p-3">
                              <div className="text-xs font-medium text-gray-500 mb-2">New Weights</div>
                              <div className="flex flex-wrap gap-2">
                                {Object.entries(detail.new_weights).map(([token, weight]) => (
                                  <span
                                    key={token}
                                    className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded"
                                  >
                                    {token}: {(weight as number).toFixed(1)}%
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* ── Step 5: Reflection (post-trade, if available) ── */}
                        {(detail as Record<string, unknown>).reflection && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1.5">
                              <span className="bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">5</span>
                              Post-Trade Reflection
                            </h4>
                            <div className="bg-gray-800/60 rounded-lg p-3 space-y-2 text-xs text-gray-400">
                              {(() => {
                                const ref = (detail as Record<string, unknown>).reflection as Record<string, unknown>
                                return (
                                  <>
                                    {ref.accuracy_pct !== undefined && (
                                      <div>Accuracy: <span className="text-white font-medium">{Number(ref.accuracy_pct).toFixed(0)}%</span></div>
                                    )}
                                    {Array.isArray(ref.lessons) && ref.lessons.length > 0 && (
                                      <ul className="space-y-1">
                                        {(ref.lessons as string[]).map((l, i) => (
                                          <li key={i} className="flex gap-1.5">
                                            <span className="text-violet-500">›</span>{l}
                                          </li>
                                        ))}
                                      </ul>
                                    )}
                                  </>
                                )
                              })()}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      // Detail fetch failed -- show basic info from the summary row
                      <div className="text-xs text-gray-500">
                        Full detail unavailable. Summary: {decision.summary}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default AgentConsensusLog
