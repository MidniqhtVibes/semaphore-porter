import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { AuthProvider } from '../auth'

const admin = { id:'1', email:'admin@example.com', display_name:'Admin', is_active:true, must_change_password:false, roles:['system_admin'] }
const operator = { ...admin, id:'2', email:'operator@example.com', display_name:'Operator', roles:['operator'] }
const json = (value: unknown, status=200) => Promise.resolve(new Response(JSON.stringify(value), { status, headers:{'Content-Type':'application/json'} }))

function renderApp() {
  const client = new QueryClient({ defaultOptions:{ queries:{ retry:false }, mutations:{ retry:false } } })
  return render(<QueryClientProvider client={client}><BrowserRouter><AuthProvider><App/></AuthProvider></BrowserRouter></QueryClientProvider>)
}

beforeEach(() => { vi.restoreAllMocks(); window.history.replaceState({}, '', '/') })

describe('Portal-Flows', () => {
  it('meldet einen Administrator an und zeigt die Adminnavigation', async () => {
    let authenticated = false
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/auth/me')) return authenticated ? json(admin) : json({detail:'Anmeldung erforderlich'},401)
      if (url.endsWith('/api/auth/login')) { authenticated = true; return json({user:admin,csrf_token:'csrf'}) }
      if (url.endsWith('/api/admin/dashboard')) return json({tenant_count:0,active_user_count:1,project_count:0,running_task_count:0,failed_task_count:0,incomplete_tenant_count:0,semaphore:{configured:false,healthy:null,message:'Nicht konfiguriert'},recent_audit:[]})
      return json({csrf_token:'csrf'})
    }))
    renderApp()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('E-Mail-Adresse'), 'admin@example.com')
    await user.type(screen.getByLabelText('Passwort'), 'correct-horse-battery')
    await user.click(screen.getByRole('button', {name:'Sicher anmelden'}))
    expect(await screen.findByText('Admin Dashboard')).toBeInTheDocument()
    expect(screen.getAllByText('Tenants').length).toBeGreaterThan(0)
    expect(screen.getByText('Audit-Log')).toBeInTheDocument()
  })

  it('behält den Wizard im ersten Schritt, solange keine Vorlage gewählt ist', async () => {
    window.history.replaceState({}, '', '/admin/tenant-erstellen')
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url=String(input)
      if(url.endsWith('/api/auth/me')) return json(admin)
      if(url.endsWith('/api/auth/csrf')) return json({csrf_token:'csrf'})
      if(url.includes('/api/admin/project-templates')) return json([])
      if(url.includes('/api/admin/presets')) return json([])
      if(url.includes('/api/admin/users')) return json([admin])
      if(url.includes('/api/admin/groups')) return json([])
      return json({})
    }))
    renderApp()
    const user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:/Speichern & weiter/}))
    expect(await screen.findByText('Bitte zuerst eine Projektvorlage auswählen.')).toBeInTheDocument()
  })

  it('erzeugt ein dynamisches Taskformular aus der Policy', async () => {
    window.history.replaceState({}, '', '/portal/projekte/11111111-1111-1111-1111-111111111111/tasks/22222222-2222-2222-2222-222222222222')
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url=String(input)
      if(url.endsWith('/api/auth/me')) return json(operator)
      if(url.endsWith('/api/auth/csrf')) return json({csrf_token:'csrf'})
      if(url.includes('/form')) return json({task:{id:'2',name:'deploy-timed-demo',description:'Demo'},can_start:true,fields:[{name:'dataset_id',title:'Testdatensatz',help_text:'Freigegebene Daten',type:'enum',default:'none',allowed_values:['none','smoke-v1'],required:true},{name:'ttl_minutes',title:'Laufzeit',help_text:'Minuten',type:'integer_range',default:60,minimum:15,maximum:180,required:true}]})
      return json({})
    }))
    renderApp()
    expect(await screen.findByRole('combobox', {name:/Testdatensatz/})).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', {name:/Laufzeit/})).toHaveAttribute('min','15')
    expect(screen.queryByLabelText(/tenant_slug/)).not.toBeInTheDocument()
  })
})
