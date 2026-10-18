import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { AuthProvider } from '../auth'
import { ThemeProvider } from '../designs/ThemeProvider'
import { useDoomEasterEgg } from '../hooks/useDoomEasterEgg'

const admin = { id: '1', email: 'admin@example.com', display_name: 'Admin', is_active: true, must_change_password: false, roles: ['system_admin'] }
const operator = { ...admin, roles: ['operator'] }
const json = (value: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))

function renderApp(user: typeof admin | null = admin) {
  const fetch = vi.fn((input: RequestInfo | URL) => String(input).endsWith('/api/auth/me')
    ? json(user ?? { detail: 'Anmeldung erforderlich' }, user ? 200 : 401)
    : String(input).endsWith('/api/portal/dashboard') ? json({ project_count: 0, running_count: 0, recent_runs: [] }) : json({ csrf_token: 'csrf' }))
  vi.stubGlobal('fetch', fetch)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><BrowserRouter><ThemeProvider><AuthProvider><App/></AuthProvider></ThemeProvider></BrowserRouter></QueryClientProvider>)
  return fetch
}

function Trigger() {
  useDoomEasterEgg()
  return <><input aria-label="Passwort" type="password"/><div contentEditable role="textbox" aria-label="Texteditor"/><button>Portalfläche</button></>
}

function renderTrigger() {
  render(<MemoryRouter><Routes><Route path="/" element={<Trigger/>}/><Route path="/portal/iddqd" element={<p>Geöffnet</p>}/></Routes></MemoryRouter>)
}

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); window.history.replaceState({}, '', '/') })

describe('Doom Easter Egg', () => {
  it.runIf(__PORTAL_ARCADE__)('öffnet nur nach dem Geheimcode und kehrt zur vorherigen Portalseite zurück', async () => {
    window.history.replaceState({}, '', '/admin/designs?view=all')
    const fetch = renderApp()
    await screen.findByRole('link', { name: 'Design erstellen' })
    expect(screen.queryByTitle('Doom · E1M1 Hangar')).not.toBeInTheDocument()
    expect(fetch.mock.calls.every(([input]) => !String(input).includes('/arcade/'))).toBe(true)
    await userEvent.keyboard('IDDQD')
    const frame = await screen.findByTitle('Doom · E1M1 Hangar')
    expect(frame).toHaveAttribute('src', '/arcade/index.html')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Zurück zum Portal' })).toHaveAttribute('href', '/admin/designs?view=all')
    await userEvent.click(screen.getByRole('link', { name: 'Zurück zum Portal' }))
    expect(await screen.findByRole('link', { name: 'Design erstellen' })).toBeVisible()
    expect(screen.queryByTitle('Doom · E1M1 Hangar')).not.toBeInTheDocument()
  })

  it.runIf(__PORTAL_ARCADE__)('verlangt eine Anmeldung auch beim direkten Aufruf', async () => {
    window.history.replaceState({}, '', '/portal/iddqd')
    renderApp(null)
    expect(await screen.findByLabelText('Passwort')).toBeVisible()
    expect(window.location.pathname).toBe('/login')
    expect(screen.queryByTitle('Doom · E1M1 Hangar')).not.toBeInTheDocument()
  })

  it.runIf(__PORTAL_ARCADE__)('bietet normalen Benutzern einen sicheren Rückweg ohne Adminrechte', async () => {
    window.history.replaceState({ usr: { returnTo: '/admin/benutzer' }, key: 'test', idx: 0 }, '', '/portal/iddqd')
    renderApp(operator)
    expect(await screen.findByRole('link', { name: 'Zurück zum Portal' })).toHaveAttribute('href', '/portal')
  })

  it('ignoriert den Code in Passwortfeldern und Texteditoren', async () => {
    renderTrigger()
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Passwort'), 'iddqd')
    await user.click(screen.getByLabelText('Texteditor'))
    await user.keyboard('iddqd')
    expect(screen.queryByText('Geöffnet')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button'))
    await user.keyboard('iddqd')
    expect(await screen.findByText('Geöffnet')).toBeVisible()
  })

  it('verwirft unvollständige Codes nach Fokuswechsel oder langer Unterbrechung', async () => {
    renderTrigger()
    const clock = vi.spyOn(performance, 'now').mockReturnValue(100)
    const type = (keys: string) => { for (const key of keys) fireEvent.keyDown(document, { key }) }
    type('idd')
    clock.mockReturnValue(3000)
    type('qd')
    expect(screen.queryByText('Geöffnet')).not.toBeInTheDocument()
    type('idd')
    fireEvent.blur(window)
    type('qd')
    expect(screen.queryByText('Geöffnet')).not.toBeInTheDocument()
    type('iddqd')
    await waitFor(() => expect(screen.getByText('Geöffnet')).toBeVisible())
  })

  it('löst nicht durch Tastenkürzel oder automatische Tastenwiederholung aus', () => {
    renderTrigger()
    for (const key of 'iddqd') fireEvent.keyDown(document, { key, ctrlKey: true })
    for (const key of 'iddqd') fireEvent.keyDown(document, { key, repeat: true })
    expect(screen.queryByText('Geöffnet')).not.toBeInTheDocument()
  })

  it.skipIf(__PORTAL_ARCADE__)('reagiert im Standardbuild nicht auf den Geheimcode', async () => {
    window.history.replaceState({}, '', '/admin/designs')
    renderApp()
    await screen.findByRole('link', { name: 'Design erstellen' })
    await userEvent.keyboard('IDDQD')
    expect(window.location.pathname).toBe('/admin/designs')
    expect(screen.queryByTitle('Doom · E1M1 Hangar')).not.toBeInTheDocument()
  })

  it.skipIf(__PORTAL_ARCADE__)('stellt im Standardbuild keine Spielroute bereit', async () => {
    window.history.replaceState({}, '', '/portal/iddqd')
    renderApp(operator)
    expect(await screen.findByRole('heading', { name: 'Letzte Task-Ausführungen' })).toBeVisible()
    expect(window.location.pathname).toBe('/portal')
    expect(screen.queryByTitle('Doom · E1M1 Hangar')).not.toBeInTheDocument()
  })
})
