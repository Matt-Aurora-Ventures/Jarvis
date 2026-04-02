import React from 'react'
import { ChevronRight, Home } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

/**
 * Breadcrumbs - Navigation breadcrumb component
 * Automatically generates breadcrumbs from current route
 */
export function Breadcrumbs({ items, className = '' }) {
  const location = useLocation()

  // Auto-generate breadcrumbs from path if no items provided
  const breadcrumbs = items || generateBreadcrumbs(location.pathname)

  if (breadcrumbs.length <= 1) return null

  return (
    <nav className={`breadcrumbs ${className}`} aria-label="Breadcrumb">
      <ol className="breadcrumb-list">
        {breadcrumbs.map((crumb, index) => {
          const isLast = index === breadcrumbs.length - 1
          const Icon = crumb.icon

          return (
            <li key={crumb.path || index} className="breadcrumb-item">
              {index > 0 && (
                <ChevronRight size={14} className="breadcrumb-separator" />
              )}

              {isLast ? (
                <span className="breadcrumb-current" aria-current="page">
                  {Icon && <Icon size={14} />}
                  {crumb.label}
                </span>
              ) : (
                <Link to={crumb.path} className="breadcrumb-link">
                  {Icon && <Icon size={14} />}
                  {crumb.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>

      <style jsx>{`
        .breadcrumbs {
          padding: 12px 0;
        }

        .breadcrumb-list {
          display: flex;
          align-items: center;
          gap: 4px;
          list-style: none;
          margin: 0;
          padding: 0;
          font-size: 14px;
        }

        .breadcrumb-item {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .breadcrumb-separator {
          color: var(--text-tertiary);
          margin: 0 4px;
        }

        .breadcrumb-link {
          display: flex;
          align-items: center;
          gap: 6px;
          color: var(--text-secondary);
          text-decoration: none;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all 0.15s ease;
        }

        .breadcrumb-link:hover {
          color: var(--text-primary);
          background: var(--bg-secondary);
        }

        .breadcrumb-current {
          display: flex;
          align-items: center;
          gap: 6px;
          color: var(--text-primary);
          font-weight: 500;
          padding: 4px 8px;
        }
      `}</style>
    </nav>
  )
}

/**
 * Generate breadcrumbs from pathname
 */
function generateBreadcrumbs(pathname) {
  const pathMap = {
    '/': { label: 'Home', icon: Home },
    '/dashboard': { label: 'Dashboard' },
    '/trading': { label: 'Trading' },
    '/trading/positions': { label: 'Positions' },
    '/trading/history': { label: 'History' },
    '/research': { label: 'Research' },
    '/chat': { label: 'Chat' },
    '/voice': { label: 'Voice Control' },
    '/settings': { label: 'Settings' },
    '/settings/voice': { label: 'Voice Settings' },
    '/settings/trading': { label: 'Trading Settings' },
    '/settings/api': { label: 'API Keys' },
    '/roadmap': { label: 'Roadmap' },
  }

  const segments = pathname.split('/').filter(Boolean)
  const breadcrumbs = [{ label: 'Home', path: '/', icon: Home }]

  let currentPath = ''
  for (const segment of segments) {
    currentPath += `/${segment}`
    const mapped = pathMap[currentPath]

    if (mapped) {
      breadcrumbs.push({
        label: mapped.label,
        path: currentPath,
        icon: mapped.icon,
      })
    } else {
      // Use capitalized segment as label
      breadcrumbs.push({
        label: segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' '),
        path: currentPath,
      })
    }
  }

  return breadcrumbs
}

/**
 * PageHeader - Common page header with breadcrumbs and title
 */
export function PageHeader({ title, subtitle, actions, showBreadcrumbs = true }) {
  return (
    <div className="page-header">
      {showBreadcrumbs && <Breadcrumbs />}

      <div className="page-header-content">
        <div className="page-header-text">
          <h1 className="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>

        {actions && <div className="page-header-actions">{actions}</div>}
      </div>

      <style jsx>{`
        .page-header {
          margin-bottom: 24px;
        }

        .page-header-content {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
        }

        .page-header-text {
          flex: 1;
        }

        .page-title {
          margin: 0;
          font-size: 28px;
          font-weight: 700;
          color: var(--text-primary);
        }

        .page-subtitle {
          margin: 8px 0 0 0;
          font-size: 15px;
          color: var(--text-secondary);
        }

        .page-header-actions {
          display: flex;
          gap: 12px;
          flex-shrink: 0;
        }

        @media (max-width: 768px) {
          .page-header-content {
            flex-direction: column;
          }

          .page-header-actions {
            width: 100%;
          }
        }
      `}</style>
    </div>
  )
}

export default Breadcrumbs
