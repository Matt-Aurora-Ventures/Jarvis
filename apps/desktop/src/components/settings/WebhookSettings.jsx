import React, { useState, useEffect } from 'react'
import {
  Webhook,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  Bell,
  AlertCircle,
  ExternalLink,
  Copy,
  RefreshCw
} from 'lucide-react'

const WEBHOOK_TYPES = [
  { value: 'discord', label: 'Discord', icon: '🎮', placeholder: 'https://discord.com/api/webhooks/...' },
  { value: 'slack', label: 'Slack', icon: '💼', placeholder: 'https://hooks.slack.com/services/...' },
  { value: 'telegram', label: 'Telegram', icon: '📱', placeholder: 'https://api.telegram.org/bot...' },
  { value: 'custom', label: 'Custom HTTP', icon: '🔗', placeholder: 'https://your-endpoint.com/webhook' },
]

const EVENT_TYPES = [
  { value: 'trade_executed', label: 'Trade Executed', description: 'When a trade is executed' },
  { value: 'trade_alert', label: 'Trade Alert', description: 'Trading signals and opportunities' },
  { value: 'price_alert', label: 'Price Alert', description: 'Price threshold notifications' },
  { value: 'sentiment_report', label: 'Sentiment Report', description: 'Market sentiment updates' },
  { value: 'system_status', label: 'System Status', description: 'System health updates' },
  { value: 'error', label: 'Errors', description: 'Error notifications' },
  { value: 'milestone', label: 'Milestones', description: 'Achievement notifications' },
  { value: 'daily_summary', label: 'Daily Summary', description: 'Daily activity summaries' },
]

export default function WebhookSettings() {
  const [webhooks, setWebhooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [testResults, setTestResults] = useState({})

  // Form state
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    webhook_type: 'discord',
    url: '',
    enabled: true,
    events: [],
  })

  useEffect(() => {
    fetchWebhooks()
  }, [])

  const fetchWebhooks = async () => {
    try {
      const response = await fetch('/api/webhooks')
      if (response.ok) {
        const data = await response.json()
        setWebhooks(data.webhooks || [])
      }
    } catch (err) {
      console.error('Failed to fetch webhooks:', err)
      setError('Failed to load webhooks')
    } finally {
      setLoading(false)
    }
  }

  const saveWebhook = async () => {
    try {
      const method = editingId ? 'PUT' : 'POST'
      const response = await fetch('/api/webhooks', {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      })

      if (response.ok) {
        fetchWebhooks()
        resetForm()
      } else {
        const data = await response.json()
        setError(data.error || 'Failed to save webhook')
      }
    } catch (err) {
      setError('Failed to save webhook')
    }
  }

  const deleteWebhook = async (id) => {
    if (!confirm('Delete this webhook?')) return

    try {
      const response = await fetch(`/api/webhooks/${id}`, { method: 'DELETE' })
      if (response.ok) {
        fetchWebhooks()
      }
    } catch (err) {
      setError('Failed to delete webhook')
    }
  }

  const testWebhook = async (id) => {
    setTestResults(prev => ({ ...prev, [id]: 'testing' }))

    try {
      const response = await fetch(`/api/webhooks/${id}/test`, { method: 'POST' })
      const data = await response.json()

      setTestResults(prev => ({
        ...prev,
        [id]: data.success ? 'success' : 'failed'
      }))

      // Clear result after 3 seconds
      setTimeout(() => {
        setTestResults(prev => ({ ...prev, [id]: null }))
      }, 3000)
    } catch (err) {
      setTestResults(prev => ({ ...prev, [id]: 'failed' }))
    }
  }

  const toggleWebhook = async (id, enabled) => {
    try {
      await fetch(`/api/webhooks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      })
      fetchWebhooks()
    } catch (err) {
      setError('Failed to update webhook')
    }
  }

  const startEdit = (webhook) => {
    setFormData({
      id: webhook.id,
      name: webhook.name,
      webhook_type: webhook.webhook_type,
      url: webhook.url,
      enabled: webhook.enabled,
      events: webhook.events || [],
    })
    setEditingId(webhook.id)
    setShowAddForm(true)
  }

  const resetForm = () => {
    setFormData({
      id: '',
      name: '',
      webhook_type: 'discord',
      url: '',
      enabled: true,
      events: [],
    })
    setEditingId(null)
    setShowAddForm(false)
  }

  const toggleEvent = (eventValue) => {
    setFormData(prev => ({
      ...prev,
      events: prev.events.includes(eventValue)
        ? prev.events.filter(e => e !== eventValue)
        : [...prev.events, eventValue]
    }))
  }

  const getTypeInfo = (type) => {
    return WEBHOOK_TYPES.find(t => t.value === type) || WEBHOOK_TYPES[3]
  }

  if (loading) {
    return (
      <div className="webhook-settings loading">
        <RefreshCw size={24} className="animate-spin" />
        <span>Loading webhooks...</span>
      </div>
    )
  }

  return (
    <div className="webhook-settings">
      <div className="section-header">
        <div className="header-title">
          <Webhook size={24} />
          <h2>Webhook Integrations</h2>
        </div>
        <p className="header-description">
          Connect JARVIS to Discord, Slack, or custom endpoints for notifications.
        </p>
      </div>

      {error && (
        <div className="error-banner">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={() => setError(null)}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* Webhook List */}
      <div className="webhooks-list">
        {webhooks.length === 0 ? (
          <div className="empty-state">
            <Bell size={48} style={{ opacity: 0.3 }} />
            <p>No webhooks configured</p>
            <button className="btn btn-primary" onClick={() => setShowAddForm(true)}>
              <Plus size={18} />
              Add Webhook
            </button>
          </div>
        ) : (
          <>
            {webhooks.map(webhook => {
              const typeInfo = getTypeInfo(webhook.webhook_type)
              const testStatus = testResults[webhook.id]

              return (
                <div key={webhook.id} className={`webhook-card ${!webhook.enabled ? 'disabled' : ''}`}>
                  <div className="webhook-header">
                    <div className="webhook-icon">{typeInfo.icon}</div>
                    <div className="webhook-info">
                      <h3>{webhook.name}</h3>
                      <span className="webhook-type">{typeInfo.label}</span>
                    </div>
                    <div className="webhook-status">
                      <label className="toggle">
                        <input
                          type="checkbox"
                          checked={webhook.enabled}
                          onChange={(e) => toggleWebhook(webhook.id, e.target.checked)}
                        />
                        <span className="toggle-slider" />
                      </label>
                    </div>
                  </div>

                  <div className="webhook-url">
                    <code>{webhook.url?.slice(0, 50)}...</code>
                    <button
                      className="copy-btn"
                      onClick={() => navigator.clipboard.writeText(webhook.url)}
                      title="Copy URL"
                    >
                      <Copy size={14} />
                    </button>
                  </div>

                  <div className="webhook-events">
                    {(webhook.events || []).slice(0, 4).map(event => (
                      <span key={event} className="event-tag">{event.replace('_', ' ')}</span>
                    ))}
                    {(webhook.events || []).length > 4 && (
                      <span className="event-tag more">+{webhook.events.length - 4} more</span>
                    )}
                  </div>

                  <div className="webhook-actions">
                    <button
                      className={`action-btn test ${testStatus}`}
                      onClick={() => testWebhook(webhook.id)}
                      disabled={testStatus === 'testing'}
                    >
                      {testStatus === 'testing' ? (
                        <RefreshCw size={16} className="animate-spin" />
                      ) : testStatus === 'success' ? (
                        <Check size={16} />
                      ) : testStatus === 'failed' ? (
                        <X size={16} />
                      ) : (
                        <Bell size={16} />
                      )}
                      {testStatus === 'testing' ? 'Testing...' : testStatus === 'success' ? 'Sent!' : testStatus === 'failed' ? 'Failed' : 'Test'}
                    </button>
                    <button className="action-btn" onClick={() => startEdit(webhook)}>
                      <Edit2 size={16} />
                      Edit
                    </button>
                    <button className="action-btn danger" onClick={() => deleteWebhook(webhook.id)}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              )
            })}

            <button className="add-webhook-btn" onClick={() => setShowAddForm(true)}>
              <Plus size={20} />
              Add Webhook
            </button>
          </>
        )}
      </div>

      {/* Add/Edit Form Modal */}
      {showAddForm && (
        <div className="modal-overlay" onClick={resetForm}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingId ? 'Edit Webhook' : 'Add Webhook'}</h3>
              <button className="close-btn" onClick={resetForm}>
                <X size={20} />
              </button>
            </div>

            <div className="form-group">
              <label>Name</label>
              <input
                type="text"
                className="input"
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
                placeholder="My Discord Alerts"
              />
            </div>

            <div className="form-group">
              <label>Type</label>
              <div className="type-selector">
                {WEBHOOK_TYPES.map(type => (
                  <button
                    key={type.value}
                    className={`type-option ${formData.webhook_type === type.value ? 'selected' : ''}`}
                    onClick={() => setFormData({ ...formData, webhook_type: type.value })}
                  >
                    <span className="type-icon">{type.icon}</span>
                    <span>{type.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label>Webhook URL</label>
              <input
                type="url"
                className="input"
                value={formData.url}
                onChange={e => setFormData({ ...formData, url: e.target.value })}
                placeholder={getTypeInfo(formData.webhook_type).placeholder}
              />
              <a
                href={formData.webhook_type === 'discord' ? 'https://support.discord.com/hc/en-us/articles/228383668' : '#'}
                target="_blank"
                rel="noopener noreferrer"
                className="help-link"
              >
                <ExternalLink size={14} />
                How to get webhook URL
              </a>
            </div>

            <div className="form-group">
              <label>Events to Send</label>
              <div className="events-grid">
                {EVENT_TYPES.map(event => (
                  <label key={event.value} className="event-checkbox">
                    <input
                      type="checkbox"
                      checked={formData.events.includes(event.value)}
                      onChange={() => toggleEvent(event.value)}
                    />
                    <div className="event-label">
                      <span className="event-name">{event.label}</span>
                      <span className="event-desc">{event.description}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={resetForm}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={saveWebhook}
                disabled={!formData.name || !formData.url}
              >
                <Check size={18} />
                {editingId ? 'Save Changes' : 'Add Webhook'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .webhook-settings {
          padding: var(--space-lg);
        }

        .webhook-settings.loading {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-md);
          min-height: 200px;
          color: var(--text-secondary);
        }

        .section-header {
          margin-bottom: var(--space-xl);
        }

        .header-title {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          color: var(--text-primary);
          margin-bottom: var(--space-xs);
        }

        .header-title h2 {
          font-size: 1.5rem;
          font-weight: 600;
          margin: 0;
        }

        .header-description {
          color: var(--text-secondary);
          font-size: 0.875rem;
        }

        .error-banner {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-md);
          background: rgba(var(--error-rgb), 0.1);
          border: 1px solid var(--error);
          border-radius: var(--radius-md);
          color: var(--error);
          margin-bottom: var(--space-lg);
        }

        .error-banner span { flex: 1; }
        .error-banner button {
          background: none;
          border: none;
          color: inherit;
          cursor: pointer;
          padding: 4px;
        }

        .webhooks-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
        }

        .empty-state {
          text-align: center;
          padding: var(--space-3xl);
          background: var(--bg-secondary);
          border-radius: var(--radius-lg);
        }

        .empty-state p {
          color: var(--text-secondary);
          margin: var(--space-md) 0;
        }

        .webhook-card {
          background: var(--bg-secondary);
          border: 1px solid var(--border-primary);
          border-radius: var(--radius-lg);
          padding: var(--space-lg);
          transition: all 0.2s ease;
        }

        .webhook-card.disabled {
          opacity: 0.6;
        }

        .webhook-header {
          display: flex;
          align-items: center;
          gap: var(--space-md);
          margin-bottom: var(--space-md);
        }

        .webhook-icon {
          font-size: 2rem;
          width: 48px;
          height: 48px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-tertiary);
          border-radius: var(--radius-md);
        }

        .webhook-info {
          flex: 1;
        }

        .webhook-info h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 4px 0;
        }

        .webhook-type {
          font-size: 0.813rem;
          color: var(--text-secondary);
        }

        .toggle {
          position: relative;
          width: 44px;
          height: 24px;
        }

        .toggle input {
          opacity: 0;
          width: 0;
          height: 0;
        }

        .toggle-slider {
          position: absolute;
          cursor: pointer;
          inset: 0;
          background: var(--bg-tertiary);
          border-radius: 24px;
          transition: 0.3s;
        }

        .toggle-slider::before {
          position: absolute;
          content: "";
          height: 18px;
          width: 18px;
          left: 3px;
          bottom: 3px;
          background: white;
          border-radius: 50%;
          transition: 0.3s;
        }

        .toggle input:checked + .toggle-slider {
          background: var(--primary);
        }

        .toggle input:checked + .toggle-slider::before {
          transform: translateX(20px);
        }

        .webhook-url {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-sm) var(--space-md);
          background: var(--bg-tertiary);
          border-radius: var(--radius-sm);
          margin-bottom: var(--space-md);
        }

        .webhook-url code {
          flex: 1;
          font-size: 0.75rem;
          color: var(--text-secondary);
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .copy-btn {
          background: none;
          border: none;
          color: var(--text-tertiary);
          cursor: pointer;
          padding: 4px;
        }

        .copy-btn:hover {
          color: var(--primary);
        }

        .webhook-events {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-xs);
          margin-bottom: var(--space-md);
        }

        .event-tag {
          padding: 4px 10px;
          background: var(--bg-tertiary);
          border-radius: 12px;
          font-size: 0.75rem;
          color: var(--text-secondary);
          text-transform: capitalize;
        }

        .event-tag.more {
          background: rgba(var(--primary-rgb), 0.1);
          color: var(--primary);
        }

        .webhook-actions {
          display: flex;
          gap: var(--space-sm);
          padding-top: var(--space-md);
          border-top: 1px solid var(--border-secondary);
        }

        .action-btn {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          padding: 8px 12px;
          background: var(--bg-tertiary);
          border: none;
          border-radius: var(--radius-sm);
          color: var(--text-secondary);
          font-size: 0.813rem;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .action-btn:hover {
          background: var(--primary);
          color: white;
        }

        .action-btn.danger:hover {
          background: var(--error);
        }

        .action-btn.test.success {
          background: var(--success);
          color: white;
        }

        .action-btn.test.failed {
          background: var(--error);
          color: white;
        }

        .add-webhook-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
          padding: var(--space-lg);
          background: transparent;
          border: 2px dashed var(--border-secondary);
          border-radius: var(--radius-lg);
          color: var(--text-secondary);
          font-size: 0.875rem;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .add-webhook-btn:hover {
          border-color: var(--primary);
          color: var(--primary);
        }

        /* Modal styles */
        .modal-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          animation: fadeIn 0.2s ease;
        }

        .modal-content {
          background: var(--bg-primary);
          border-radius: var(--radius-xl);
          width: 100%;
          max-width: 560px;
          max-height: 90vh;
          overflow-y: auto;
          padding: var(--space-xl);
          animation: slideUp 0.3s ease;
        }

        .modal-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: var(--space-xl);
        }

        .modal-header h3 {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0;
        }

        .close-btn {
          background: none;
          border: none;
          color: var(--text-tertiary);
          cursor: pointer;
          padding: 4px;
        }

        .close-btn:hover {
          color: var(--text-primary);
        }

        .form-group {
          margin-bottom: var(--space-lg);
        }

        .form-group label {
          display: block;
          font-size: 0.875rem;
          font-weight: 500;
          color: var(--text-secondary);
          margin-bottom: var(--space-sm);
        }

        .input {
          width: 100%;
          padding: var(--space-md);
          background: var(--bg-secondary);
          border: 1px solid var(--border-secondary);
          border-radius: var(--radius-md);
          color: var(--text-primary);
          font-size: 0.875rem;
        }

        .input:focus {
          outline: none;
          border-color: var(--primary);
        }

        .type-selector {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: var(--space-sm);
        }

        .type-option {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-md);
          background: var(--bg-secondary);
          border: 2px solid var(--border-secondary);
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .type-option:hover {
          border-color: var(--primary);
        }

        .type-option.selected {
          border-color: var(--primary);
          background: rgba(var(--primary-rgb), 0.1);
        }

        .type-icon {
          font-size: 1.5rem;
        }

        .type-option span:last-child {
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .help-link {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 0.75rem;
          color: var(--primary);
          margin-top: var(--space-xs);
          text-decoration: none;
        }

        .help-link:hover {
          text-decoration: underline;
        }

        .events-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--space-sm);
        }

        .event-checkbox {
          display: flex;
          align-items: flex-start;
          gap: var(--space-sm);
          padding: var(--space-md);
          background: var(--bg-secondary);
          border-radius: var(--radius-md);
          cursor: pointer;
          transition: background 0.2s ease;
        }

        .event-checkbox:hover {
          background: var(--bg-tertiary);
        }

        .event-checkbox input {
          margin-top: 2px;
        }

        .event-label {
          display: flex;
          flex-direction: column;
        }

        .event-name {
          font-size: 0.875rem;
          font-weight: 500;
          color: var(--text-primary);
        }

        .event-desc {
          font-size: 0.75rem;
          color: var(--text-tertiary);
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          gap: var(--space-md);
          margin-top: var(--space-xl);
          padding-top: var(--space-lg);
          border-top: 1px solid var(--border-secondary);
        }

        .btn {
          display: flex;
          align-items: center;
          gap: var(--space-xs);
          padding: var(--space-sm) var(--space-lg);
          border-radius: var(--radius-md);
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .btn-primary {
          background: var(--primary);
          border: none;
          color: white;
        }

        .btn-primary:hover:not(:disabled) {
          opacity: 0.9;
        }

        .btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-secondary {
          background: var(--bg-secondary);
          border: 1px solid var(--border-secondary);
          color: var(--text-secondary);
        }

        .btn-secondary:hover {
          border-color: var(--text-tertiary);
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 640px) {
          .type-selector {
            grid-template-columns: repeat(2, 1fr);
          }

          .events-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  )
}
