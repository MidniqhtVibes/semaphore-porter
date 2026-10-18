import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GroupedNavigation } from '../components/GroupedNavigation'
import { navigationContext, type NavigationItem, type NavigationMode } from '../components/navigation'

const renderItem = ([path, label]: NavigationItem) => <a key={path} href={path}>{label}</a>
const menu = (mode: NavigationMode, pathname: string) => <GroupedNavigation mode={mode} pathname={pathname} renderItem={renderItem}/>

describe('Gruppiertes Hauptmenü', () => {
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
})
