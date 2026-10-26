import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GroupedNavigation, NAVIGATION_STORAGE_KEY } from '../components/GroupedNavigation'
import { navigationContext, type NavigationItem, type NavigationMode } from '../components/navigation'

const renderItem = ([path, label]: NavigationItem) => <a key={path} href={path}>{label}</a>
const menu = (mode: NavigationMode, pathname: string) => <GroupedNavigation mode={mode} pathname={pathname} renderItem={renderItem}/>

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear() })

describe('Gruppiertes Hauptmenü', () => {
  it('übernimmt bisherige Browser-Einstellungen unter den neuen Produktnamen', () => {
    localStorage.setItem('semaphore-porter.navigation.v1',JSON.stringify({'admin:catalog':true,'portal:personal':false}))
    const view=render(menu('admin','/admin/tenants'))
    expect(screen.getByRole('button',{name:'Katalog'})).toHaveAttribute('aria-expanded','true')
    expect(JSON.parse(localStorage.getItem(NAVIGATION_STORAGE_KEY)!)).toMatchObject({'admin:catalog':true,'portal:personal':false})
    view.rerender(menu('portal','/portal'))
    expect(screen.getByRole('button',{name:'Persönlich'})).toHaveAttribute('aria-expanded','false')
  })
  it('öffnet den aktiven Bereich und macht eingeklappte Einträge erst nach dem Öffnen erreichbar', () => {
    const view = render(menu('admin', '/admin/vault'))
    expect(screen.getByRole('button', { name: 'Einstellungen' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Vault' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Zugriff' })).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: 'Benutzer & Gruppen' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Zugriff' }))
    expect(screen.getByRole('link', { name: 'Benutzer & Gruppen' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Zugriff' }))
    view.rerender(menu('admin', '/admin/berechtigungen'))
    expect(screen.getByRole('button', { name: 'Zugriff' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Berechtigungen' })).toBeVisible()
  })

  it('ordnet die Tenant-Anlage und Detailseiten dem Arbeitsbereich zu', () => {
    render(menu('admin', '/admin/tenant-erstellen'))
    expect(screen.getByRole('button', { name: 'Arbeitsbereich' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.queryByRole('link', { name: 'Tenant erstellen', hidden: true })).not.toBeInTheDocument()
    expect(navigationContext('admin', '/admin/tenant-erstellen').label).toBe('Tenant erstellen')
    expect(navigationContext('admin', '/admin/tenants/123').group.id).toBe('workspace')
    expect(navigationContext('admin', '/admin/tenants/123').label).toBe('Tenants')
  })

  it('zeigt im Benutzerportal beide übersichtlichen Gruppen und keine Adminfunktionen', () => {
    render(menu('portal', '/portal/projekte/123'))
    const navigation = within(screen.getByRole('navigation', { name: 'Hauptmenü' }))
    expect(navigation.getByRole('button', { name: 'Arbeitsbereich' })).toHaveAttribute('aria-expanded', 'true')
    expect(navigation.getByRole('button', { name: 'Persönlich' })).toHaveAttribute('aria-expanded', 'true')
    expect(navigation.getAllByRole('link')).toHaveLength(6)
    expect(navigation.getByRole('link', { name: 'Mein Konto' })).toBeVisible()
    expect(navigation.queryByRole('link', { name: 'Vault' })).not.toBeInTheDocument()
  })

  it('ordnet Verbindungen einem verschachtelten Zweig und dem vollständigen Seitenpfad zu', () => {
    render(menu('admin', '/admin/vault'))
    expect(navigationContext('admin', '/admin/vault').groups.map(group => group.label)).toEqual(['Einstellungen', 'Verbindungen'])
    const connections = screen.getByRole('group', { name: 'Verbindungen' })
    expect(within(connections).getByRole('link', { name: 'Vault' })).toBeVisible()
    expect(within(connections).getByRole('link', { name: 'Semaphore-Verbindung' })).toBeVisible()
    expect(within(connections).queryByRole('link', { name: 'Designs' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Verbindungen' }))
    expect(screen.queryByRole('link', { name: 'Vault' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Designs' })).toBeVisible()
  })

  it('merkt geöffnete Kategorien und öffnet beim Seitenwechsel alle aktiven Vorfahren wieder', () => {
    const first = render(menu('admin', '/admin/tenants'))
    fireEvent.click(screen.getByRole('button', { name: 'Katalog' }))
    fireEvent.click(screen.getByRole('button', { name: 'Einstellungen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Verbindungen' }))
    fireEvent.click(screen.getByRole('button', { name: 'Einstellungen' }))
    first.unmount()
    const second = render(menu('admin', '/admin/tenants'))
    expect(screen.getByRole('button', { name: 'Katalog' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Einstellungen' })).toHaveAttribute('aria-expanded', 'false')
    second.rerender(menu('admin', '/admin/vault'))
    expect(screen.getByRole('button', { name: 'Einstellungen' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Verbindungen' })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Vault' })).toBeVisible()
  })

  it('klappt den gesamten Baum auf und zu, ohne die Benutzerportal-Gruppen mitzuschalten', () => {
    const first = render(menu('admin', '/admin/tenants'))
    fireEvent.click(screen.getByRole('button', { name: 'Alle Kategorien aufklappen' }))
    expect(screen.getByRole('link', { name: 'Vault' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Benutzer & Gruppen' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Alle Kategorien einklappen' }))
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    first.unmount()
    render(menu('portal', '/portal/projekte'))
    expect(screen.getAllByRole('link')).toHaveLength(6)
  })

  it('bedient Zweige und sichtbare Einträge über Pfeiltasten sowie Anfang und Ende', () => {
    render(menu('admin', '/admin/vault'))
    const settings = screen.getByRole('button', { name: 'Einstellungen' })
    const connections = screen.getByRole('button', { name: 'Verbindungen' })
    settings.focus()
    fireEvent.keyDown(settings, { key: 'ArrowRight' })
    expect(connections).toHaveFocus()
    fireEvent.keyDown(connections, { key: 'ArrowRight' })
    const semaphore = screen.getByRole('link', { name: 'Semaphore-Verbindung' })
    expect(semaphore).toHaveFocus()
    fireEvent.keyDown(semaphore, { key: 'ArrowDown' })
    const vault = screen.getByRole('link', { name: 'Vault' })
    expect(vault).toHaveFocus()
    fireEvent.keyDown(vault, { key: 'ArrowLeft' })
    expect(connections).toHaveFocus()
    fireEvent.keyDown(connections, { key: 'ArrowLeft' })
    expect(connections).toHaveAttribute('aria-expanded', 'false')
    fireEvent.keyDown(connections, { key: 'ArrowLeft' })
    expect(settings).toHaveFocus()
    fireEvent.keyDown(settings, { key: 'Home' })
    expect(screen.getByRole('button', { name: 'Arbeitsbereich' })).toHaveFocus()
    fireEvent.keyDown(document.activeElement!, { key: 'End' })
    expect(screen.getByRole('link', { name: 'Designs' })).toHaveFocus()
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' })
    expect(connections).toHaveFocus()
  })

  it('öffnet nach einem Neuladen die aktive Seite trotz vorher eingeklapptem Zweig', () => {
    localStorage.setItem(NAVIGATION_STORAGE_KEY, JSON.stringify({ 'admin:settings': false, 'admin:settings/connections': false }))
    render(menu('admin', '/admin/vault'))
    expect(screen.getByRole('link', { name: 'Vault' })).toBeVisible()
  })

  it('ignoriert ungültige gespeicherte Kategorien und arbeitet ohne Browser-Speicher weiter', () => {
    localStorage.setItem(NAVIGATION_STORAGE_KEY, JSON.stringify({ 'admin:catalog': 'false', unknown: true }))
    const first = render(menu('admin', '/admin/tenants'))
    expect(screen.getByRole('button', { name: 'Katalog' })).toHaveAttribute('aria-expanded', 'false')
    expect(JSON.parse(localStorage.getItem(NAVIGATION_STORAGE_KEY)!)).not.toHaveProperty('unknown')
    first.unmount()
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new DOMException('Blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Blocked') })
    render(menu('admin', '/admin/tenants'))
    fireEvent.click(screen.getByRole('button', { name: 'Katalog' }))
    expect(screen.getByRole('link', { name: 'Projektvorlagen' })).toBeVisible()
  })

  it('ändert beim Ausprobieren in der Designvorschau keine gespeicherten Navigationszustände', () => {
    const saved = JSON.stringify({ 'admin:catalog': false })
    localStorage.setItem(NAVIGATION_STORAGE_KEY, saved)
    render(<GroupedNavigation mode="admin" pathname="/admin/tenants" persistState={false} renderItem={renderItem}/>)
    fireEvent.click(screen.getByRole('button', { name: 'Katalog' }))
    expect(screen.getByRole('link', { name: 'Anwendungen' })).toBeVisible()
    expect(localStorage.getItem(NAVIGATION_STORAGE_KEY)).toBe(saved)
  })
})
