import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Brain, Database, RefreshCw, Cpu, Workflow, Shield, History, Mic, Library, BarChart3 } from 'lucide-react'

import { Card, Badge, Button } from '@/components/ui'

function statusVariant(status) {
  if (status === 'healthy' || status === 'ready') return 'success'
  if (status === 'degraded') return 'warning'
  if (status === 'disabled') return 'default'
  return 'danger'
}

function formatDate(value) {
  if (!value) return 'N/A'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return String(value)
  }
}

function ListItems({ items, emptyText = '(none)' }) {
  if (!Array.isArray(items) || items.length === 0) {
    return <p style={{ color: 'var(--text-secondary)' }}>{emptyText}</p>
  }
  return (
    <ul className="space-y-2">
      {items.map((item, idx) => (
        <li
          key={`${idx}-${String(item).slice(0, 20)}`}
          className="text-sm"
          style={{ color: 'var(--text-primary)' }}
        >
          - {String(item)}
        </li>
      ))}
    </ul>
  )
}

function PanelHeader({ icon: Icon, title, status, reason }) {
  return (
    <Card.Header
      actions={(
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(status)}>{status || 'unknown'}</Badge>
          {reason ? (
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {reason}
            </span>
          ) : null}
        </div>
      )}
    >
      <Card.Title icon={Icon}>{title}</Card.Title>
    </Card.Header>
  )
}

function AIControlPlane() {
  const [snapshot, setSnapshot] = useState(null)
  const [coliseumSnapshot, setColiseumSnapshot] = useState(null)
  const [mirrorSnapshot, setMirrorSnapshot] = useState(null)
  const [signalSnapshot, setSignalSnapshot] = useState(null)
  const [regimeSnapshot, setRegimeSnapshot] = useState(null)
  const [voiceSnapshot, setVoiceSnapshot] = useState(null)
  const [knowledgeSnapshot, setKnowledgeSnapshot] = useState(null)
  const [mevSnapshot, setMevSnapshot] = useState(null)
  const [multiDexSnapshot, setMultiDexSnapshot] = useState(null)
  const [analyticsSnapshot, setAnalyticsSnapshot] = useState(null)
  const [perpsSnapshot, setPerpsSnapshot] = useState(null)
  const [runtimeSnapshot, setRuntimeSnapshot] = useState(null)
  const [themeSnapshot, setThemeSnapshot] = useState(null)
  const [onboardingSnapshot, setOnboardingSnapshot] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchSnapshot = useCallback(async () => {
    try {
      setError(null)
      const [
        controlRes,
        coliseumRes,
        mirrorRes,
        signalRes,
        regimeRes,
        voiceRes,
        knowledgeRes,
        mevRes,
        multiDexRes,
        analyticsRes,
        perpsRes,
        runtimeRes,
        themeRes,
        onboardingRes,
      ] = await Promise.all([
        fetch('/api/ai/control-plane', { method: 'GET' }),
        fetch('/api/sentinel/coliseum', { method: 'GET' }),
        fetch('/api/lifeos/mirror/status', { method: 'GET' }),
        fetch('/api/intel/signal-aggregator?limit=6', { method: 'GET' }),
        fetch('/api/intel/ml-regime?symbol=SOL', { method: 'GET' }),
        fetch('/api/lifeos/voice/status', { method: 'GET' }),
        fetch('/api/lifeos/knowledge/status', { method: 'GET' }),
        fetch('/api/advanced/mev?limit=6', { method: 'GET' }),
        fetch('/api/advanced/multi-dex?trading_pair=SOL-USDC&amount_usd=1000', { method: 'GET' }),
        fetch('/api/analytics/portfolio?range=7d', { method: 'GET' }),
        fetch('/api/advanced/perps/status', { method: 'GET' }),
        fetch('/api/runtime/capabilities', { method: 'GET' }),
        fetch('/api/polish/themes/status', { method: 'GET' }),
        fetch('/api/polish/onboarding/status', { method: 'GET' }),
      ])
      if (!controlRes.ok) {
        throw new Error(`HTTP ${controlRes.status}`)
      }
      const payload = await controlRes.json()
      setSnapshot(payload)

      if (coliseumRes.ok) {
        setColiseumSnapshot(await coliseumRes.json())
      } else {
        setColiseumSnapshot({ status: 'degraded', error: `HTTP ${coliseumRes.status}` })
      }

      if (mirrorRes.ok) {
        setMirrorSnapshot(await mirrorRes.json())
      } else {
        setMirrorSnapshot({ status: 'degraded', reason: `HTTP ${mirrorRes.status}` })
      }

      if (signalRes.ok) {
        setSignalSnapshot(await signalRes.json())
      } else {
        setSignalSnapshot({ source: 'degraded_fallback', summary: { opportunity_count: 0 }, opportunities: [] })
      }

      if (regimeRes.ok) {
        setRegimeSnapshot(await regimeRes.json())
      } else {
        setRegimeSnapshot({ source: 'degraded_fallback', status: 'degraded', regime: 'unknown', confidence: 0 })
      }

      if (voiceRes.ok) {
        setVoiceSnapshot(await voiceRes.json())
      } else {
        setVoiceSnapshot({ source: 'degraded_fallback', status: 'degraded', capabilities: {} })
      }

      if (knowledgeRes.ok) {
        setKnowledgeSnapshot(await knowledgeRes.json())
      } else {
        setKnowledgeSnapshot({ source: 'degraded_fallback', status: 'degraded', capabilities: {}, metrics: {} })
      }

      if (mevRes.ok) {
        setMevSnapshot(await mevRes.json())
      } else {
        setMevSnapshot({ source: 'degraded_fallback', summary: { event_count: 0 }, events: [] })
      }

      if (multiDexRes.ok) {
        setMultiDexSnapshot(await multiDexRes.json())
      } else {
        setMultiDexSnapshot({ source: 'degraded_fallback', quotes: [], best_route: {} })
      }

      if (analyticsRes.ok) {
        setAnalyticsSnapshot(await analyticsRes.json())
      } else {
        setAnalyticsSnapshot({ source: 'degraded_fallback', metrics: {}, pnl_distribution: {} })
      }

      if (perpsRes.ok) {
        setPerpsSnapshot(await perpsRes.json())
      } else {
        setPerpsSnapshot({ source: 'degraded_fallback', status: 'degraded', capabilities: {} })
      }

      if (runtimeRes.ok) {
        setRuntimeSnapshot(await runtimeRes.json())
      } else {
        setRuntimeSnapshot({ generated_at: null, components: {} })
      }

      if (themeRes.ok) {
        setThemeSnapshot(await themeRes.json())
      } else {
        setThemeSnapshot({ source: 'degraded_fallback', status: 'degraded', capabilities: {} })
      }

      if (onboardingRes.ok) {
        setOnboardingSnapshot(await onboardingRes.json())
      } else {
        setOnboardingSnapshot({ source: 'degraded_fallback', status: 'degraded', steps: [], capabilities: {} })
      }
    } catch (err) {
      setError(err.message || 'Failed to fetch control plane snapshot')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSnapshot()
    const id = setInterval(fetchSnapshot, 20000)
    return () => clearInterval(id)
  }, [fetchSnapshot])

  const panels = snapshot?.panels || {}
  const consensus = panels.consensus || {}
  const context = panels.context || {}
  const upgrade = panels.upgrade || {}
  const compute = panels.compute || {}
  const coliseumSummary = coliseumSnapshot?.summary || {}
  const mirrorLastRun = mirrorSnapshot?.last_run || null
  const signalSummary = signalSnapshot?.summary || {}
  const voiceCaps = voiceSnapshot?.capabilities || {}
  const knowledgeCaps = knowledgeSnapshot?.capabilities || {}
  const mevSummary = mevSnapshot?.summary || {}
  const bestRoute = multiDexSnapshot?.best_route || {}
  const analyticsMetrics = analyticsSnapshot?.metrics || {}
  const perpsCaps = perpsSnapshot?.capabilities || {}
  const runtimeComponents = runtimeSnapshot?.components || {}
  const themeCaps = themeSnapshot?.capabilities || {}
  const onboardingCaps = onboardingSnapshot?.capabilities || {}

  const panelCount = useMemo(
    () => Object.keys(panels || {}).length,
    [panels]
  )

  return (
    <div className="flex-1 p-8 overflow-y-auto" style={{ background: 'var(--bg-secondary)' }}>
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>
            AI Control Plane
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Unified status for consensus, context hooks, model upgrades, and compute routing.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={statusVariant(snapshot?.status)}>{snapshot?.status || 'loading'}</Badge>
          <Button onClick={fetchSnapshot} variant="secondary" className="inline-flex items-center gap-2">
            <RefreshCw size={16} />
            Refresh
          </Button>
        </div>
      </header>

      {loading ? (
        <Card><Card.Body>Loading control plane snapshot...</Card.Body></Card>
      ) : null}

      {error ? (
        <Card variant="bordered" className="mb-6">
          <Card.Body>
            <p style={{ color: 'var(--danger)' }}>Failed to load AI control plane: {error}</p>
          </Card.Body>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-6">
        <Card>
          <Card.Header><Card.Title icon={Brain}>Consensus</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              {Object.keys(consensus.panel_models || {}).length}
            </p>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              panel models
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Database}>Context</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              {(context.static_profile || []).length + (context.dynamic_profile || []).length}
            </p>
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              profile entries
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Workflow}>Upgrade</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {upgrade.active_local_model || 'Unknown model'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              last scan: {formatDate(upgrade.last_scan_at)}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Cpu}>Compute</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              protocol v{compute.mesh_protocol?.version || 'n/a'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              panels loaded: {panelCount}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Shield}>Coliseum</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              promoted: {coliseumSummary.promoted ?? 0} / {coliseumSummary.total_strategies ?? 0}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              latest backtest: {formatDate(coliseumSummary.latest_backtest_at)}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={History}>Mirror Test</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              runs 7d: {mirrorSnapshot?.runs_7d ?? 0}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              last score: {typeof mirrorLastRun?.score === 'number' ? mirrorLastRun.score.toFixed(3) : 'N/A'}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={BarChart3}>Signal Aggregator</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              opportunities: {signalSummary.opportunity_count ?? 0}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              avg score: {typeof signalSummary.avg_signal_score === 'number' ? signalSummary.avg_signal_score : 'N/A'}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Mic}>Voice</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              status: {voiceSnapshot?.status || 'unknown'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              mic/stt/tts: {voiceCaps.microphone ? '1' : '0'}/{voiceCaps.stt ? '1' : '0'}/{voiceCaps.tts ? '1' : '0'}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Library}>Knowledge</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              status: {knowledgeSnapshot?.status || 'unknown'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              profile entries: {knowledgeSnapshot?.metrics?.profile_entries ?? 0}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Shield}>Advanced</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              MEV events: {mevSummary.event_count ?? 0}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              best route: {bestRoute.venue || 'N/A'}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={BarChart3}>Analytics</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              total PnL: {typeof analyticsMetrics.total_pnl_pct === 'number' ? `${analyticsMetrics.total_pnl_pct.toFixed(2)}%` : 'N/A'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              win rate: {typeof analyticsMetrics.win_rate_pct === 'number' ? `${analyticsMetrics.win_rate_pct.toFixed(2)}%` : 'N/A'}
            </p>
          </Card.Body>
        </Card>
        <Card>
          <Card.Header><Card.Title icon={Cpu}>Polish</Card.Title></Card.Header>
          <Card.Body>
            <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              themes: {themeSnapshot?.status || 'unknown'} | onboarding: {onboardingSnapshot?.status || 'unknown'}
            </p>
            <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              runtime components: {Object.keys(runtimeComponents).length}
            </p>
          </Card.Body>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <PanelHeader
            icon={Brain}
            title="Consensus Panel"
            status={consensus.status}
            reason={consensus.reason}
          />
          <Card.Body className="space-y-4">
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Model Panel</p>
              <ListItems
                items={Object.entries(consensus.panel_models || {}).map(([alias, id]) => `${alias}: ${id}`)}
                emptyText="No models configured"
              />
            </div>
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Scoring Thresholds</p>
              <ListItems
                items={[
                  `strong >= ${consensus.thresholds?.strong ?? 'n/a'}`,
                  `moderate >= ${consensus.thresholds?.moderate ?? 'n/a'}`,
                ]}
              />
            </div>
            <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
              {consensus.explainability || 'No explainability data yet.'}
            </p>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={Database}
            title="Context Panel"
            status={context.status}
            reason={context.reason}
          />
          <Card.Body className="space-y-4">
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Static Profile</p>
              <ListItems items={context.static_profile} />
            </div>
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Dynamic Profile</p>
              <ListItems items={context.dynamic_profile} />
            </div>
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Recent Memory Injections</p>
              <ListItems items={context.recent_memory_injections} />
            </div>
            <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
              {context.explainability || 'No explainability data yet.'}
            </p>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={Workflow}
            title="Upgrade Panel"
            status={upgrade.status}
            reason={upgrade.reason}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `active model: ${upgrade.active_local_model || 'unknown'}`,
                `last scan: ${formatDate(upgrade.last_scan_at)}`,
                `restart command configured: ${upgrade.restart_command_configured ? 'yes' : 'no'}`,
                `last action: ${upgrade.last_result?.action || 'n/a'}`,
              ]}
            />
            <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
              {upgrade.explainability || 'No explainability data yet.'}
            </p>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={Cpu}
            title="Compute Panel"
            status={compute.status}
            reason={compute.reason}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `nosana configured: ${compute.nosana_runtime?.configured ? 'yes' : 'no'}`,
                `mesh sync status: ${compute.mesh_sync?.status || 'unknown'}`,
                `mesh attestation status: ${compute.mesh_attestation?.status || 'unknown'}`,
                `last job status: ${compute.nosana_runtime?.last_job_summary?.status || 'n/a'}`,
                `mesh protocol version: ${compute.mesh_protocol?.version || 'n/a'}`,
                `replay cache size: ${compute.nosana_runtime?.mesh_protocol?.replay_cache_size ?? 'n/a'}`,
              ]}
            />
            <p className="text-sm" style={{ color: 'var(--text-primary)' }}>
              {compute.explainability || 'No explainability data yet.'}
            </p>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={Shield}
            title="Sentinel Coliseum"
            status={coliseumSnapshot?.status || 'unknown'}
            reason={coliseumSnapshot?.error}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `total strategies: ${coliseumSummary.total_strategies ?? 0}`,
                `promoted: ${coliseumSummary.promoted ?? 0}`,
                `deleted: ${coliseumSummary.deleted ?? 0}`,
                `testing: ${coliseumSummary.testing ?? 0}`,
                `latest backtest: ${formatDate(coliseumSummary.latest_backtest_at)}`,
              ]}
            />
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Recent Strategies</p>
              <ListItems
                items={(coliseumSnapshot?.strategies || []).slice(0, 5).map((item) => (
                  `${item.strategy_name || 'unknown'} (${item.status || 'unknown'})`
                ))}
                emptyText="No strategy results available"
              />
            </div>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={History}
            title="Mirror Test"
            status={mirrorSnapshot?.status || 'unknown'}
            reason={mirrorSnapshot?.reason}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `runs (7d): ${mirrorSnapshot?.runs_7d ?? 0}`,
                `avg score (7d): ${typeof mirrorSnapshot?.avg_score_7d === 'number' ? mirrorSnapshot.avg_score_7d.toFixed(3) : 'N/A'}`,
                `auto-applied (7d): ${mirrorSnapshot?.auto_applied_7d ?? 0}`,
                `pending reviews: ${mirrorSnapshot?.pending_reviews ?? 0}`,
                `next scheduled run: ${formatDate(mirrorSnapshot?.next_scheduled_at)}`,
              ]}
            />
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Last Run</p>
              <ListItems
                items={mirrorLastRun ? [
                  `timestamp: ${formatDate(mirrorLastRun.timestamp)}`,
                  `score: ${typeof mirrorLastRun.score === 'number' ? mirrorLastRun.score.toFixed(3) : 'N/A'}`,
                  `auto-applied: ${mirrorLastRun.auto_applied ? 'yes' : 'no'}`,
                  `snapshot: ${mirrorLastRun.snapshot_id || 'n/a'}`,
                ] : []}
                emptyText="No mirror run logged yet"
              />
            </div>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={BarChart3}
            title="Signal + Regime"
            status={regimeSnapshot?.status || 'unknown'}
            reason={regimeSnapshot?.reason}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `signal opportunities: ${signalSummary.opportunity_count ?? 0}`,
                `bullish count: ${signalSummary.bullish_count ?? 0}`,
                `bearish count: ${signalSummary.bearish_count ?? 0}`,
                `avg signal score: ${typeof signalSummary.avg_signal_score === 'number' ? signalSummary.avg_signal_score : 'N/A'}`,
                `regime: ${regimeSnapshot?.regime || 'unknown'}`,
                `regime confidence: ${typeof regimeSnapshot?.confidence === 'number' ? regimeSnapshot.confidence.toFixed(3) : 'N/A'}`,
                `recommended strategy: ${regimeSnapshot?.recommended_strategy || 'unknown'}`,
              ]}
            />
            <div>
              <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Top Opportunities</p>
              <ListItems
                items={(signalSnapshot?.opportunities || []).slice(0, 5).map((item) => (
                  `${item.symbol || 'unknown'} (${item.signal || 'neutral'}) score=${item.signal_score ?? 0}`
                ))}
                emptyText="No signal opportunities available"
              />
            </div>
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={Library}
            title="Voice + Knowledge"
            status={voiceSnapshot?.status || knowledgeSnapshot?.status || 'unknown'}
            reason={voiceSnapshot?.reason || knowledgeSnapshot?.reason}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `voice microphone: ${voiceCaps.microphone ? 'ready' : 'not_ready'}`,
                `voice stt: ${voiceCaps.stt ? 'ready' : 'not_ready'}`,
                `voice tts: ${voiceCaps.tts ? 'ready' : 'not_ready'}`,
                `voice wake-word: ${voiceCaps.wake_word ? 'ready' : 'not_ready'}`,
                `knowledge hooks: ${knowledgeCaps.supermemory_hooks ? 'ready' : 'not_ready'}`,
                `knowledge graph: ${knowledgeCaps.knowledge_graph ? 'ready' : 'not_ready'}`,
                `research notebooks: ${knowledgeCaps.research_notebooks ? 'ready' : 'not_ready'}`,
                `facts extracted: ${knowledgeSnapshot?.metrics?.facts_extracted ?? 0}`,
              ]}
            />
          </Card.Body>
        </Card>

        <Card>
          <PanelHeader
            icon={Cpu}
            title="Advanced + Polish"
            status={perpsSnapshot?.status || themeSnapshot?.status || onboardingSnapshot?.status || 'unknown'}
            reason={null}
          />
          <Card.Body className="space-y-4">
            <ListItems
              items={[
                `mev events (24h): ${mevSummary.event_count ?? 0}`,
                `multi-dex best route: ${bestRoute.venue || 'unknown'}`,
                `perps mode: ${perpsSnapshot?.mode || 'unknown'}`,
                `perps runner api: ${perpsCaps.runner_api ? 'ready' : 'not_ready'}`,
                `analytics trades: ${analyticsMetrics.total_trades ?? 0}`,
                `runtime components tracked: ${Object.keys(runtimeComponents).length}`,
                `themes ready: ${themeCaps.theme_provider && themeCaps.theme_toggle ? 'yes' : 'no'}`,
                `onboarding wired: ${onboardingCaps.main_layout_wired ? 'yes' : 'no'}`,
              ]}
            />
          </Card.Body>
        </Card>
      </div>
    </div>
  )
}

export default AIControlPlane
