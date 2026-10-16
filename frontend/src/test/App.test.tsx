import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { AuthProvider } from '../auth'
import { ThemeProvider, THEME_STORAGE_KEY } from '../designs/ThemeProvider'

const admin = { id:'1', email:'admin@example.com', display_name:'Admin', is_active:true, must_change_password:false, roles:['system_admin'] }
const operator = { ...admin, id:'2', email:'operator@example.com', display_name:'Operator', roles:['operator'] }
const json = (value: unknown, status=200) => Promise.resolve(new Response(JSON.stringify(value), { status, headers:{'Content-Type':'application/json'} }))

function renderApp() {
  const client = new QueryClient({ defaultOptions:{ queries:{ retry:false }, mutations:{ retry:false } } })
  return render(<QueryClientProvider client={client}><BrowserRouter><ThemeProvider><AuthProvider><App/></AuthProvider></ThemeProvider></BrowserRouter></QueryClientProvider>)
}

beforeEach(() => { vi.restoreAllMocks(); localStorage.clear(); window.history.replaceState({}, '', '/') })

describe('Portal-Flows', () => {
  it('speichert die Designwahl und übernimmt sie auch in die Benutzeransicht',async()=>{
    window.history.replaceState({}, '', '/admin/designs')
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
      if(String(input).endsWith('/api/auth/me'))return json(admin)
      if(String(input).endsWith('/api/auth/csrf'))return json({csrf_token:'csrf'})
      return json([])
    }))
    const view=renderApp(), user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:'SIT Hell verwenden'}))
    expect(document.documentElement).toHaveAttribute('data-theme','sit-light')
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(screen.getByRole('img',{name:'Südwestfalen-IT'})).toHaveAttribute('src','/branding/sit-logo.png')
    expect(JSON.parse(localStorage.getItem(THEME_STORAGE_KEY)! ).selected).toBe('sit-light')
    view.unmount()
    window.history.replaceState({}, '', '/portal/designs')
    renderApp()
    expect(await screen.findByRole('button',{name:'SIT Hell ist aktiv'})).toBeDisabled()
    expect(screen.getByRole('link',{name:'Designs'})).toHaveAttribute('href','/portal/designs')
    await user.click(screen.getByRole('button',{name:'GitHub Black verwenden'}))
    expect(document.documentElement).toHaveAttribute('data-theme','github-dark')
    expect(document.documentElement.style.getPropertyValue('--bg')).toBe('#0d1117')
    expect(screen.queryByRole('img',{name:'Südwestfalen-IT'})).not.toBeInTheDocument()
  })

  it('speichert das Website-Symbol unabhängig vom Design und aktualisiert alle Verknüpfungen',async()=>{
    window.history.replaceState({}, '', '/admin/designs')
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).endsWith('/api/auth/me')?json(admin):json({csrf_token:'csrf'})))
    const view=renderApp(), user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:/Mandanten-Verbund/}))
    expect(document.getElementById('portal-favicon')).toHaveAttribute('href','/icons/tenants.svg')
    expect(document.getElementById('portal-manifest')).toHaveAttribute('href','/manifests/tenants.webmanifest')
    await user.click(screen.getByRole('button',{name:'SIT Dunkel verwenden'}))
    expect(document.getElementById('portal-favicon')).toHaveAttribute('href','/icons/tenants.svg')
    expect(document.getElementById('portal-touch-icon')).toHaveAttribute('href','/icons/tenants-180.png')
    view.unmount()
    renderApp()
    expect(await screen.findByRole('button',{name:/Mandanten-Verbund/})).toHaveAttribute('aria-pressed','true')
    expect(document.documentElement).toHaveAttribute('data-theme','sit-dark')
  })

  it('importiert ein eigenes Design und behält bei fehlerhaftem Import die aktive Variante',async()=>{
    window.history.replaceState({}, '', '/admin/designs')
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>String(input).endsWith('/api/auth/me')?json(admin):json({csrf_token:'csrf'})))
    renderApp()
    const user=userEvent.setup()
    const input=await screen.findByLabelText(/Design-Datei/)
    const definition={schema_version:1,id:'firma-a',name:'Firma A',base:'github-dark',colors:{accent:'#b6a4ff'}}
    const file=new File([JSON.stringify(definition)],'firma.theme.json',{type:'application/json'})
    Object.defineProperty(file,'text',{value:async()=>JSON.stringify(definition)})
    await user.upload(input,file)
    expect(await screen.findByRole('button',{name:'Firma A ist aktiv'})).toBeDisabled()
    expect(document.documentElement).toHaveAttribute('data-theme','custom:firma-a')
    const bad={...definition,colors:{bg:'url(https://example.com/track)'}}
    const invalid=new File([JSON.stringify(bad)],'invalid.json',{type:'application/json'})
    Object.defineProperty(invalid,'text',{value:async()=>JSON.stringify(bad)})
    await user.upload(input,invalid)
    expect(await screen.findByRole('alert')).toHaveTextContent('Hex-Farbwert')
    expect(document.documentElement).toHaveAttribute('data-theme','custom:firma-a')
    await user.click(screen.getByRole('button',{name:'Firma A entfernen'}))
    expect(document.documentElement).toHaveAttribute('data-theme','github-dark')
    expect(screen.queryByRole('heading',{name:'Firma A'})).not.toBeInTheDocument()
  })

  it('behält besuchte Schritte und speichert mehrere Anwendungen, Provider und Datensätze',async()=>{
    window.history.replaceState({}, '', '/admin/tenant-erstellen')
    let saved:Record<string,unknown>|undefined
    const draft={project_name:'Multi',tenant_slug:'multi-a',runtime_scope_id:'multi-scope',display_name:'Multi',wizard_step:3,application_ids:['azubiorga'],database_types:['postgresql'],dataset_ids:['none'],task_template_names:['deploy'],environment_names:['Semaphore-Defaults']}
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const url=String(input)
      if(url.endsWith('/api/auth/me'))return json(admin)
      if(url.endsWith('/api/auth/csrf'))return json({csrf_token:'csrf'})
      if(url.endsWith('/project-templates'))return json([{id:'source',name:'Quelle',survey_catalog:{application_id:['azubiorga','wordpress'],database_type:['none','postgresql','mariadb','mysql'],dataset_id:['none','public-v1','mariadb-smoke-v1']},task_templates:['deploy'],environments:['Semaphore-Defaults']}])
      if(url.endsWith('/creation-jobs'))return json([{id:'job-multi',project_template_id:'source',status:'draft',draft_data:draft}])
      if(url.endsWith('/creation-jobs/job-multi')){saved=JSON.parse(String(options?.body)).draft_data as Record<string,unknown>;return json({id:'job-multi',project_template_id:'source',status:'draft',draft_data:saved})}
      if(url.endsWith('/resources'))return json({templates:[{name:'deploy'}],environments:[{name:'Semaphore-Defaults'}],repositories:[],inventories:[]})
      return json([])
    }))
    renderApp()
    const user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:'Fortsetzen'}))
    await screen.findByRole('heading',{name:'Task Templates und Ressourcen'})
    await user.click(screen.getByRole('button',{name:'Zurück'}))
    const nav=screen.getByLabelText('Wizard-Schritte')
    expect(within(nav).getByRole('button',{name:/3\. Anwendung/})).toHaveAttribute('aria-current','step')
    expect(within(nav).getByRole('button',{name:/4\. Ressourcen/})).toBeEnabled()
    expect(within(nav).getByRole('button',{name:/4\. Ressourcen/})).toHaveClass('visited')
    await user.click(within(screen.getByRole('region',{name:'Anwendungen'})).getByRole('checkbox',{name:'wordpress'}))
    await user.click(screen.getByRole('button',{name:'Alle Datenbankprovider auswählen'}))
    await user.click(screen.getByRole('button',{name:'Alle Testdatensätze auswählen'}))
    await user.click(screen.getByRole('button',{name:/Speichern & weiter/}))
    await waitFor(()=>expect(saved?.application_ids).toEqual(['azubiorga','wordpress']))
    expect(saved?.database_types).toEqual(['none','postgresql','mariadb','mysql'])
    expect(saved?.dataset_ids).toEqual(['none','public-v1','mariadb-smoke-v1'])
    expect(saved?.wizard_step).toBe(3)
  })

  it('beginnt nach einem Vorlagenwechsel einen neuen Creation Job', async()=>{
    window.history.replaceState({}, '', '/admin/tenant-erstellen')
    const created:string[]=[]
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const url=String(input)
      if(url.endsWith('/api/auth/me'))return json(admin)
      if(url.endsWith('/api/auth/csrf'))return json({csrf_token:'csrf'})
      if(url.endsWith('/project-templates'))return json(['A','B'].map(id=>({id,name:`Quelle ${id}`,description:'Vorlage',survey_catalog:{},task_templates:['deploy'],environments:['Semaphore-Defaults']})))
      if(url.endsWith('/creation-jobs')&&options?.method==='POST'){const body=JSON.parse(String(options.body)) as {project_template_id:string};created.push(body.project_template_id);return json({id:`job-${created.length}`,draft_data:{},status:'draft'})}
      if(url.includes('/creation-jobs/job-'))return json({id:`job-${created.length}`,draft_data:{},status:'draft'})
      return json([])
    }))
    renderApp()
    const user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:/Quelle A/}))
    await user.click(screen.getByRole('button',{name:/Speichern & weiter/}))
    await screen.findByLabelText('Semaphore-Projektname')
    await user.click(screen.getByRole('button',{name:'Zurück'}))
    await user.click(screen.getByRole('button',{name:/Quelle B/}))
    await user.click(screen.getByRole('button',{name:/Speichern & weiter/}))
    await waitFor(()=>expect(created).toEqual(['A','B']))
  })

  it('lädt Tenant und Runtime-Scope aus einem gespeicherten Entwurf',async()=>{
    window.history.replaceState({}, '', '/admin/tenant-erstellen')
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
      const url=String(input)
      if(url.endsWith('/api/auth/me'))return json(admin)
      if(url.endsWith('/api/auth/csrf'))return json({csrf_token:'csrf'})
      if(url.endsWith('/creation-jobs'))return json([{id:'job-a',project_template_id:'a',status:'draft',draft_data:{project_name:'Saved',tenant_slug:'saved-a',runtime_scope_id:'saved-scope',display_name:'Saved'}}])
      return json([])
    }))
    renderApp()
    await userEvent.click(await screen.findByRole('button',{name:'Fortsetzen'}))
    expect(screen.getByLabelText(/Technische Tenant-ID/)).toHaveValue('saved-a')
    expect(screen.getByLabelText(/Runtime-Scope/)).toHaveValue('saved-scope')
  })

  it('speichert beide Tenant-Kennungen gemeinsam in Semaphore-Defaults', async () => {
    window.history.replaceState({}, '', '/admin/projekte/7')
    let written:Record<string,unknown>|undefined
    vi.stubGlobal('fetch', vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const url=String(input)
      if(url.endsWith('/api/auth/me'))return json(admin)
      if(url.endsWith('/api/auth/csrf'))return json({csrf_token:'csrf'})
      if(url.endsWith('/resources/environment/3')){written=JSON.parse(String(options?.body)) as Record<string,unknown>;return json({message:'Gespeichert'})}
      if(url.endsWith('/resources/environment'))return json([{id:3,revision:'version-a',values:{name:'Semaphore-Defaults',json:{tenant_slug:'old-a',runtime_scope_id:'old-scope',custom:42},env:{}},secrets:[]}])
      if(url.endsWith('/projects/7'))return json({project:{id:7,name:'Kunde A',alert:false,max_parallel_tasks:0},revision:'project-a'})
      return json([])
    }))
    renderApp()
    const user=userEvent.setup()
    await user.click(await screen.findByRole('button',{name:'Bearbeiten'}))
    const tenant=screen.getByLabelText('Tenant-ID (tenant_slug)'),scope=screen.getByLabelText('Runtime-Scope (runtime_scope_id)')
    await user.clear(tenant);await user.type(tenant,'new-a')
    await user.clear(scope);await user.type(scope,'new-scope')
    await user.click(screen.getByRole('button',{name:'Änderungen prüfen'}))
    await user.click(screen.getByRole('button',{name:'In Semaphore speichern'}))
    await waitFor(()=>expect(written).toBeDefined())
    expect(written?.values).toEqual({name:'Semaphore-Defaults',json:{tenant_slug:'new-a',runtime_scope_id:'new-scope',custom:42},env:{}})
    expect(written?.revision).toBe('version-a')
  })

  it('fordert den exakten Projektnamen vor einer Remote-Löschung', async()=>{
    window.history.replaceState({}, '', '/admin/projekte/7')
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL)=>{
      const url=String(input)
      if(url.endsWith('/api/auth/me'))return json(admin)
      if(url.endsWith('/api/auth/csrf'))return json({csrf_token:'csrf'})
      if(url.endsWith('/projects/7'))return json({project:{id:7,name:'Kunde A'},revision:'a'})
      return json([])
    }))
    renderApp()
    const button=await screen.findByRole('button',{name:'Semaphore-Projekt endgültig löschen'})
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Projektname zur Löschbestätigung'),'Kunde A')
    expect(button).toBeEnabled()
  })
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
