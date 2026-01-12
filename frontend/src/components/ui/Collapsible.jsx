import React, { useState, useRef, useEffect } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

/**
 * Collapsible - Expandable section component
 */
export function Collapsible({
  title,
  children,
  defaultOpen = false,
  icon: Icon,
  badge,
  className = '',
  onToggle,
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const contentRef = useRef(null)
  const [contentHeight, setContentHeight] = useState(defaultOpen ? 'auto' : 0)

  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(isOpen ? contentRef.current.scrollHeight : 0)
    }
  }, [isOpen, children])

  const toggle = () => {
    const newState = !isOpen
    setIsOpen(newState)
    onToggle?.(newState)
  }

  return (
    <div className={`collapsible ${isOpen ? 'is-open' : ''} ${className}`}>
      <button
        className="collapsible-header"
        onClick={toggle}
        aria-expanded={isOpen}
      >
        <span className="collapsible-chevron">
          {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        </span>

        {Icon && (
          <span className="collapsible-icon">
            <Icon size={20} />
          </span>
        )}

        <span className="collapsible-title">{title}</span>

        {badge && <span className="collapsible-badge">{badge}</span>}
      </button>

      <div
        className="collapsible-content-wrapper"
        style={{ height: isOpen ? contentHeight : 0 }}
      >
        <div ref={contentRef} className="collapsible-content">
          {children}
        </div>
      </div>

      <style jsx>{`
        .collapsible {
          border: 1px solid var(--border-primary);
          border-radius: 12px;
          background: var(--bg-primary);
          overflow: hidden;
        }

        .collapsible-header {
          display: flex;
          align-items: center;
          gap: 12px;
          width: 100%;
          padding: 16px 20px;
          background: transparent;
          border: none;
          cursor: pointer;
          text-align: left;
          transition: background 0.15s ease;
        }

        .collapsible-header:hover {
          background: var(--bg-secondary);
        }

        .collapsible-chevron {
          display: flex;
          align-items: center;
          color: var(--text-tertiary);
          transition: transform 0.2s ease;
        }

        .is-open .collapsible-chevron {
          color: var(--accent-primary);
        }

        .collapsible-icon {
          display: flex;
          align-items: center;
          color: var(--text-secondary);
        }

        .collapsible-title {
          flex: 1;
          font-size: 16px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .collapsible-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 24px;
          height: 24px;
          padding: 0 8px;
          font-size: 12px;
          font-weight: 600;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          border-radius: 12px;
        }

        .collapsible-content-wrapper {
          overflow: hidden;
          transition: height 0.25s ease;
        }

        .collapsible-content {
          padding: 0 20px 20px;
          border-top: 1px solid var(--border-primary);
        }

        .is-open .collapsible-content {
          padding-top: 16px;
        }
      `}</style>
    </div>
  )
}

/**
 * CollapsibleGroup - Group of collapsible sections (accordion behavior optional)
 */
export function CollapsibleGroup({
  children,
  accordion = false, // Only one open at a time
  className = '',
}) {
  const [openIndex, setOpenIndex] = useState(null)

  const handleToggle = (index, isOpen) => {
    if (accordion) {
      setOpenIndex(isOpen ? index : null)
    }
  }

  return (
    <div className={`collapsible-group ${className}`}>
      {React.Children.map(children, (child, index) => {
        if (!React.isValidElement(child)) return child

        return React.cloneElement(child, {
          defaultOpen: accordion ? openIndex === index : child.props.defaultOpen,
          onToggle: (isOpen) => {
            handleToggle(index, isOpen)
            child.props.onToggle?.(isOpen)
          },
        })
      })}

      <style jsx>{`
        .collapsible-group {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
      `}</style>
    </div>
  )
}

/**
 * SettingsSection - Styled collapsible for settings pages
 */
export function SettingsSection({
  title,
  description,
  icon: Icon,
  children,
  defaultOpen = true,
  status,
}) {
  return (
    <div className="settings-section">
      <Collapsible
        title={title}
        icon={Icon}
        defaultOpen={defaultOpen}
        badge={status}
      >
        {description && (
          <p className="settings-description">{description}</p>
        )}
        <div className="settings-content">
          {children}
        </div>
      </Collapsible>

      <style jsx>{`
        .settings-section {
          margin-bottom: 16px;
        }

        .settings-description {
          margin: 0 0 16px 0;
          font-size: 14px;
          color: var(--text-secondary);
          line-height: 1.5;
        }

        .settings-content {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
      `}</style>
    </div>
  )
}

export default Collapsible
