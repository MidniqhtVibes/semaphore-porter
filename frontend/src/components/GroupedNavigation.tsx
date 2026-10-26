import { useEffect, useId, useState, type KeyboardEvent, type ReactNode } from 'react'
import { ChevronRight, ChevronsDownUp, ChevronsUpDown } from 'lucide-react'
import { navigationContext, navigationGroups, type NavigationGroup, type NavigationItem, type NavigationMode } from './navigation'

export const NAVIGATION_STORAGE_KEY = 'semaporter.navigation.v1'
const LEGACY_NAVIGATION_STORAGE_KEY = 'semaphore-porter.navigation.v1'
type ExpandedGroups = Record<string, boolean>

function branchKeys(mode: NavigationMode, groups: readonly NavigationGroup[] = navigationGroups(mode), parent = ''): string[] {
  return groups.flatMap(group => {
    const path = parent ? `${parent}/${group.id}` : group.id
    return [`${mode}:${path}`, ...branchKeys(mode, group.children || [], path)]
  })
}

function readExpanded(): ExpandedGroups {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(NAVIGATION_STORAGE_KEY) ?? localStorage.getItem(LEGACY_NAVIGATION_STORAGE_KEY) ?? 'null')
    if (!stored || typeof stored !== 'object' || Array.isArray(stored)) return {}
    const values = stored as Record<string, unknown>
    return Object.fromEntries([...branchKeys('admin'), ...branchKeys('portal')]
      .filter(key => typeof values[key] === 'boolean').map(key => [key, values[key]])) as ExpandedGroups
  } catch { return {} }
}

const controlSelector = '.nav-group-toggle, .nav-tree-leaf > a, .nav-tree-leaf > button'
const visibleControls = (element: HTMLElement) => [...element.querySelectorAll<HTMLElement>(controlSelector)]
  .filter(control => !control.closest('[hidden]') && !control.hasAttribute('disabled'))

function navigateByKeyboard(event: KeyboardEvent<HTMLElement>) {
  if (event.altKey || event.ctrlKey || event.metaKey || !(event.target instanceof HTMLElement)) return
  const control = event.target.closest<HTMLElement>(controlSelector)
  if (!control) return
  const group = control.closest<HTMLElement>('.nav-group')
  const toggle = group?.querySelector<HTMLButtonElement>(':scope > .nav-group-toggle')
  const isToggle = control === toggle
  if (event.key === 'ArrowRight' && isToggle && toggle) {
    event.preventDefault()
    if (toggle.getAttribute('aria-expanded') === 'false') toggle.click()
    else {
      const content = document.getElementById(toggle.getAttribute('aria-controls') || '')
      if (content) visibleControls(content)[0]?.focus()
    }
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    if (isToggle && toggle && toggle.getAttribute('aria-expanded') === 'true') toggle.click()
    else if (!isToggle) toggle?.focus()
    else group?.parentElement?.closest('.nav-group')?.querySelector<HTMLButtonElement>(':scope > .nav-group-toggle')?.focus()
  } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    const controls = visibleControls(event.currentTarget)
    const index = controls.indexOf(control)
    if (index < 0) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? controls.length - 1
      : Math.max(0, Math.min(controls.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))
    controls[next]?.focus()
  }
}

export function GroupedNavigation({ mode, pathname, renderItem, persistState = true }: {
  mode: NavigationMode
  pathname: string
  renderItem: (item: NavigationItem) => ReactNode
  persistState?: boolean
}) {
  const uid = useId()
  const active = navigationContext(mode, pathname).groups
  const activeKeys = active.map((_, index) => `${mode}:${active.slice(0, index + 1).map(group => group.id).join('/')}`)
  const [expandedGroups, setExpandedGroups] = useState<ExpandedGroups>(() => ({
    ...(persistState ? readExpanded() : {}), ...Object.fromEntries(activeKeys.map(key => [key, true])),
  }))

  useEffect(() => {
    setExpandedGroups(value => activeKeys.every(key => value[key]) ? value
      : { ...value, ...Object.fromEntries(activeKeys.map(key => [key, true])) })
  }, [mode, pathname])

  useEffect(() => {
    if (persistState) {
      try { localStorage.setItem(NAVIGATION_STORAGE_KEY, JSON.stringify(expandedGroups)) }
      catch { /* Navigation continues to work when browser storage is unavailable. */ }
    }
  }, [expandedGroups, persistState])

  const setAll = (expanded: boolean) => setExpandedGroups(value => ({
    ...value, ...Object.fromEntries(branchKeys(mode).map(key => [key, expanded])),
  }))

  const renderGroup = (group: NavigationGroup, parent = '', level = 0): ReactNode => {
    const path = parent ? `${parent}/${group.id}` : group.id
    const key = `${mode}:${path}`
    const expanded = expandedGroups[key] ?? (activeKeys.includes(key) || mode === 'portal' && level === 0)
    const Icon = group.icon
    const buttonId = `${uid}-${mode}-${path.replaceAll('/', '-')}-toggle`
    const contentId = `${buttonId}-items`
    return <li className={`nav-group${activeKeys.includes(key) ? ' nav-group-current' : ''}`} key={key}>
      <button type="button" className="nav-group-toggle" id={buttonId} aria-expanded={expanded}
        aria-controls={contentId} onClick={() => setExpandedGroups(value => ({ ...value, [key]: !expanded }))}>
        <ChevronRight size={14} className="nav-group-chevron" aria-hidden="true"/>
        <Icon size={16} aria-hidden="true"/><span>{group.label}</span>
      </button>
      <ul className="nav-group-items" id={contentId} role="group" aria-labelledby={buttonId} hidden={!expanded}>
        {group.children?.map(child => renderGroup(child, path, level + 1))}
        {group.items.map(item => <li className="nav-tree-leaf" key={item[0]}>{renderItem(item)}</li>)}
      </ul>
    </li>
  }

  return <nav className="grouped-navigation" aria-label="Hauptmenü" onKeyDown={navigateByKeyboard}>
    <div className="nav-tree-toolbar"><span>Navigation</span>
      <button type="button" className="nav-tree-action" aria-label="Alle Kategorien aufklappen" title="Alle Kategorien aufklappen" onClick={() => setAll(true)}><ChevronsUpDown size={15} aria-hidden="true"/></button>
      <button type="button" className="nav-tree-action" aria-label="Alle Kategorien einklappen" title="Alle Kategorien einklappen" onClick={() => setAll(false)}><ChevronsDownUp size={15} aria-hidden="true"/></button>
    </div>
    <ul className="nav-tree-root">{navigationGroups(mode).map(group => renderGroup(group))}</ul>
  </nav>
}
