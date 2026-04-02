import React, { useEffect } from 'react'
import { X, Command } from 'lucide-react'

/**
 * KeyboardShortcuts - Modal showing all available keyboard shortcuts
 */
export function KeyboardShortcuts({ isOpen, onClose }) {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
  const mod = isMac ? '⌘' : 'Ctrl'

  const shortcuts = [
    {
      category: 'Navigation',
      items: [
        { keys: [`${mod}`, 'K'], description: 'Open search' },
        { keys: [`${mod}`, '/'], description: 'Show shortcuts' },
        { keys: [`${mod}`, '1'], description: 'Go to Dashboard' },
        { keys: [`${mod}`, '2'], description: 'Go to Trading' },
        { keys: [`${mod}`, '3'], description: 'Go to Research' },
      ]
    },
    {
      category: 'Voice',
      items: [
        { keys: [`${mod}`, 'Shift', 'V'], description: 'Toggle voice mode' },
        { keys: ['Space'], description: 'Push-to-talk (when focused)' },
        { keys: ['Escape'], description: 'Stop speaking' },
      ]
    },
    {
      category: 'Chat',
      items: [
        { keys: [`${mod}`, 'Enter'], description: 'Send message' },
        { keys: [`${mod}`, 'Shift', 'N'], description: 'New chat' },
        { keys: ['↑'], description: 'Edit last message' },
      ]
    },
    {
      category: 'Trading',
      items: [
        { keys: [`${mod}`, 'B'], description: 'Buy (when in trading)' },
        { keys: [`${mod}`, 'S'], description: 'Sell (when in trading)' },
        { keys: ['Escape'], description: 'Cancel order' },
      ]
    },
    {
      category: 'General',
      items: [
        { keys: [`${mod}`, 'Shift', 'T'], description: 'Toggle theme' },
        { keys: [`${mod}`, ','], description: 'Open settings' },
        { keys: ['?'], description: 'Show help' },
      ]
    },
  ]

  return (
    <div
      className="shortcuts-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="shortcuts-modal">
        <div className="shortcuts-header">
          <h2>Keyboard Shortcuts</h2>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="shortcuts-content">
          {shortcuts.map((section) => (
            <div key={section.category} className="shortcuts-section">
              <h3>{section.category}</h3>
              <div className="shortcuts-list">
                {section.items.map((shortcut, idx) => (
                  <div key={idx} className="shortcut-item">
                    <span className="shortcut-description">
                      {shortcut.description}
                    </span>
                    <span className="shortcut-keys">
                      {shortcut.keys.map((key, kidx) => (
                        <React.Fragment key={kidx}>
                          <kbd>{key}</kbd>
                          {kidx < shortcut.keys.length - 1 && ' + '}
                        </React.Fragment>
                      ))}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="shortcuts-footer">
          <span className="text-secondary">
            Press <kbd>Esc</kbd> to close
          </span>
        </div>
      </div>

      <style jsx>{`
        .shortcuts-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(4px);
        }

        .shortcuts-modal {
          background: var(--bg-primary);
          border-radius: 12px;
          border: 1px solid var(--border-primary);
          max-width: 600px;
          width: 90%;
          max-height: 80vh;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        }

        .shortcuts-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 20px;
          border-bottom: 1px solid var(--border-primary);
        }

        .shortcuts-header h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }

        .shortcuts-content {
          padding: 20px;
          overflow-y: auto;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 24px;
        }

        .shortcuts-section h3 {
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--text-secondary);
          margin: 0 0 12px 0;
        }

        .shortcuts-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .shortcut-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 0;
        }

        .shortcut-description {
          font-size: 14px;
          color: var(--text-primary);
        }

        .shortcut-keys {
          display: flex;
          align-items: center;
          gap: 4px;
          flex-shrink: 0;
        }

        .shortcut-keys kbd {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 24px;
          padding: 0 6px;
          font-family: inherit;
          font-size: 12px;
          font-weight: 500;
          background: var(--bg-secondary);
          border: 1px solid var(--border-secondary);
          border-radius: 4px;
          color: var(--text-secondary);
        }

        .shortcuts-footer {
          padding: 12px 20px;
          border-top: 1px solid var(--border-primary);
          text-align: center;
        }

        .shortcuts-footer kbd {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 20px;
          padding: 0 6px;
          font-family: inherit;
          font-size: 11px;
          font-weight: 500;
          background: var(--bg-secondary);
          border: 1px solid var(--border-secondary);
          border-radius: 4px;
          color: var(--text-secondary);
        }

        .text-secondary {
          color: var(--text-secondary);
          font-size: 13px;
        }
      `}</style>
    </div>
  )
}

/**
 * useKeyboardShortcuts - Hook to register global keyboard shortcuts
 */
export function useKeyboardShortcuts(shortcuts) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
      const mod = isMac ? e.metaKey : e.ctrlKey

      for (const shortcut of shortcuts) {
        const modMatch = shortcut.mod ? mod : !mod
        const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey
        const keyMatch = e.key.toLowerCase() === shortcut.key.toLowerCase()

        if (modMatch && shiftMatch && keyMatch) {
          e.preventDefault()
          shortcut.action()
          return
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [shortcuts])
}

export default KeyboardShortcuts
