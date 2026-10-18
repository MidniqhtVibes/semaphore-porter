import { useEffect, useId, useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { navigationContext, navigationGroups, type NavigationItem, type NavigationMode } from './navigation'

export function GroupedNavigation({ mode, pathname, renderItem }: {
  mode: NavigationMode
  pathname: string
  renderItem: (item: NavigationItem) => ReactNode
}) {
  const uid = useId()
  const { group: active } = navigationContext(mode, pathname)
  const activeKey = `${mode}:${active.id}`
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setExpandedGroups(value => value[activeKey] ? value : { ...value, [activeKey]: true })
  }, [activeKey, pathname])

  return <nav className="grouped-navigation" aria-label="Hauptmenü">
    {navigationGroups(mode).map(group => {
      const key = `${mode}:${group.id}`
      const expanded = expandedGroups[key] ?? (mode === 'portal' || group.id === active.id)
      const Icon = group.icon
      const buttonId = `${uid}-${group.id}-toggle`
      const contentId = `${uid}-${group.id}-items`
      return <div className={`nav-group${group.id === active.id ? ' nav-group-current' : ''}`} key={key}>
        <button type="button" className="nav-group-toggle" id={buttonId} aria-expanded={expanded}
          aria-controls={contentId} onClick={() => setExpandedGroups(value => ({ ...value, [key]: !expanded }))}>
          <Icon size={15} aria-hidden="true"/><span>{group.label}</span><ChevronDown size={14} className="nav-group-chevron" aria-hidden="true"/>
        </button>
        <div className="nav-group-items" id={contentId} role="group" aria-labelledby={buttonId} hidden={!expanded}>
          {group.items.map(renderItem)}
        </div>
      </div>
    })}
  </nav>
}
