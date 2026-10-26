import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GitLabPage } from '../pages/admin/GitLabPage'
import { ProgramPackagesPage } from '../pages/admin/ProgramPackagesPage'
import { ProgramPackagePage } from '../pages/admin/ProgramPackagePage'
import { GitLabReleasesPage } from '../pages/admin/GitLabReleasesPage'
import { decodeText, encodeText, type Manifest, type PackageDraft } from '../gitlab'
import { navigationContext } from '../components/navigation'

const json=(data:unknown,status=200)=>Promise.resolve(new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}}))
function view(page:React.ReactNode,path='/admin/gitlab'){
  const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/admin/programmpakete/:draftId" element={page}/><Route path="*" element={page}/></Routes></MemoryRouter></QueryClientProvider>)
}
const manifest:Manifest={schema_version:1,id:'demo',display_name:'Demo',profile_version:1,release:{default:'1.0.0',primary_image:'application',images:{}},database:{default_type:'none',types:{none:{provider_id:'none-v1',allowed_policies:['always_new'],compose:{none:'files/compose.yml'},configuration_files:[],connection_mapping:{}}}},datasets:{catalog:'testdata/catalog.yml',optional:true},secrets:{vault_profile:'demo',required:{}},readiness:[]}
const baseDraft:PackageDraft={id:'draft-1',package_id:'demo',name:'Demo',base_sha:'a'.repeat(40),base_branch:'main',version:1,status:'draft',connection_id:'c1',files:{'programs/demo/program.yml':encodeText('id: demo'),'programs/demo/testdata/catalog.yml':encodeText('datasets: {}')},manifest,dataset_catalog:{schema_version:1,datasets:{}},diff:[{path:'programs/demo/program.yml',action:'create',diff:'+ id: demo',sha256:null}],updated_at:'2026-10-26T10:00:00Z',created_at:'2026-10-26T10:00:00Z'}

beforeEach(()=>{vi.restoreAllMocks()})

describe('GitLab-Oberfläche',()=>{
  it('ordnet Verbindung und Paketdetails den sichtbaren Menüzweigen zu',()=>{
    expect(navigationContext('admin','/admin/gitlab').groups.map(g=>g.label)).toEqual(['Einstellungen','Verbindungen'])
    expect(navigationContext('admin','/admin/programmpakete/draft-1').groups.map(g=>g.label)).toEqual(['Entwicklung'])
    expect(navigationContext('admin','/admin/programmpakete/draft-1').label).toBe('Programmpakete')
  })

  it('speichert einen neuen Token nur nach ausdrücklichem Speichern und leert das Feld danach',async()=>{
    const requests:Array<{method:string;body:Record<string,unknown>}> = []
    vi.stubGlobal('fetch',vi.fn((_input:RequestInfo|URL,options?:RequestInit)=>{
      if(options?.method==='PUT'){requests.push({method:'PUT',body:JSON.parse(String(options.body))});return json({configured:true,token_present:true,base_url:'https://gitlab.example',project_id:7,base_branch:'main',write_enabled:false})}
      return json({configured:false,token_present:false})
    }))
    view(<GitLabPage/>)
    await screen.findByRole('heading',{name:'GitLab',level:1})
    await userEvent.type(screen.getByLabelText(/^GitLab-URL/),'https://gitlab.example')
    await userEvent.type(screen.getByLabelText('Numerische Projekt-ID'),'7')
    await userEvent.type(screen.getByLabelText(/^Project Access Token/),'test-value')
    expect(requests).toHaveLength(0)
    await userEvent.click(screen.getByRole('button',{name:'Verbindung prüfen und speichern'}))
    await screen.findByText('GitLab-Verbindung geprüft und gespeichert.')
    expect(requests[0].body).toMatchObject({project_id:7,write_enabled:false,token:'test-value'})
    expect(screen.getByLabelText(/^Project Access Token/)).toHaveValue('')
  })

  it('zeigt bei fehlender Verbindung einen Einrichtungshinweis ohne Repository-Anfrage',async()=>{
    const fetch=vi.fn((input:RequestInfo|URL)=>String(input).endsWith('/gitlab')?json({configured:false}):json([]))
    vi.stubGlobal('fetch',fetch)
    view(<ProgramPackagesPage/>,'/admin/programmpakete')
    await screen.findByText('GitLab noch nicht verbunden')
    expect(screen.getByRole('button',{name:'Programmpaket erstellen'})).toBeDisabled()
    expect(fetch.mock.calls.some(([input])=>String(input).includes('/gitlab/repository'))).toBe(false)
  })

  it('behält Schritt und Entwurf beim Zurückgehen und fordert Prüfung sowie Übergabebestätigung',async()=>{
    let draft=structuredClone(baseDraft)
    const writes:string[]=[]
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const path=String(input)
      if(options?.method==='PUT'){
        writes.push('save');const body=JSON.parse(String(options.body));draft={...draft,manifest:body.manifest,name:body.manifest.display_name,files:body.files,version:2};return json(draft)
      }
      if(path.endsWith('/validate')){writes.push('validate');draft={...draft,status:'validated',validation:{valid:true,version:2,compiler:'test-contract',source_hash:'hash',checks:[],note:'CI follows'}};return json(draft)}
      if(path.endsWith('/publish')){writes.push('publish');return json({...draft,branch:'semaporter/programs/demo/draft-1',status:'submitted',merge_request_iid:42})}
      return json(draft)
    }))
    view(<ProgramPackagePage/>,'/admin/programmpakete/draft-1')
    await screen.findByLabelText('Anzeigename')
    await userEvent.clear(screen.getByLabelText('Anzeigename'));await userEvent.type(screen.getByLabelText('Anzeigename'),'Changed')
    await userEvent.click(screen.getByRole('button',{name:'Weiter'}))
    expect(screen.getByRole('button',{name:'2. Provider & Konfiguration'})).toHaveAttribute('aria-current','step')
    await userEvent.click(screen.getByRole('button',{name:'Zurück'}))
    expect(screen.getByLabelText('Anzeigename')).toHaveValue('Changed')
    await userEvent.click(screen.getByRole('button',{name:'4. Prüfen & Übergeben'}))
    expect(screen.getByRole('button',{name:'Gespeicherten Entwurf prüfen'})).toBeDisabled()
    await userEvent.click(screen.getByRole('button',{name:'Entwurf speichern'}))
    await waitFor(()=>expect(screen.getByRole('button',{name:'Gespeicherten Entwurf prüfen'})).toBeEnabled())
    await userEvent.click(screen.getByRole('button',{name:'Gespeicherten Entwurf prüfen'}))
    await waitFor(()=>expect(screen.getByRole('button',{name:'Branch und Merge Request erstellen'})).toBeEnabled())
    await userEvent.click(screen.getByRole('button',{name:'Branch und Merge Request erstellen'}))
    const modal=within(screen.getByRole('dialog',{name:'GitLab-Übergabe bestätigen'}))
    expect(modal.getByRole('button',{name:'Jetzt übergeben / abgleichen'})).toBeDisabled()
    expect(writes).toEqual(['save','validate'])
    await userEvent.click(modal.getByRole('checkbox'))
    await userEvent.click(modal.getByRole('button',{name:'Jetzt übergeben / abgleichen'}))
    await waitFor(()=>expect(writes).toEqual(['save','validate','publish']))
  })

  it('zeigt Konflikte vom Server und verwirft die lokalen Eingaben nicht',async()=>{
    vi.stubGlobal('fetch',vi.fn((_input:RequestInfo|URL,options?:RequestInit)=>options?.method==='PUT'?json({detail:'Entwurf wurde parallel geändert.'},409):json(baseDraft)))
    view(<ProgramPackagePage/>,'/admin/programmpakete/draft-1')
    await screen.findByLabelText('Anzeigename')
    fireEvent.change(screen.getByLabelText('Anzeigename'),{target:{value:'Lokal'}})
    await userEvent.click(screen.getByRole('button',{name:'Entwurf speichern'}))
    await screen.findByText('Entwurf wurde parallel geändert.')
    expect(screen.getByLabelText('Anzeigename')).toHaveValue('Lokal')
  })

  it('verlangt für eine Katalogaktivierung Vorlage, Repository und Reviewbestätigung',async()=>{
    const sha='a'.repeat(40),snapshot={id:'s1',source_sha:sha,source_hash:'hash',connection_id:'c1',active:false,created_at:'2026-10-26T10:00:00Z',project_name:'team/stack',catalog:{source_revision:sha,applications:{}},validation:{checks:[],compiler:'contract',note:'',valid:true,source_hash:'hash'},diff:{added:['demo'],removed:[],changed:[]}}
    const writes:string[]=[]
    vi.stubGlobal('fetch',vi.fn((input:RequestInfo|URL,options?:RequestInit)=>{
      const path=String(input)
      if(options?.method==='POST'){writes.push(path);return json({message:'Aktiviert'})}
      if(path.endsWith('/resources'))return json({repositories:[{name:'Stack',git_url:'https://gitlab.example/team/stack.git'}]})
      if(path.endsWith('/project-templates'))return json([{id:'base',name:'Base'}])
      return json({active_id:null,current_catalog:snapshot.catalog,snapshots:[snapshot]})
    }))
    view(<GitLabReleasesPage/>,'/admin/uebernahme')
    await screen.findByRole('button',{name:'Übernahme / Rücknahme vorbereiten'})
    await userEvent.click(screen.getByRole('button',{name:'Übernahme / Rücknahme vorbereiten'}))
    await userEvent.selectOptions(await screen.findByLabelText('Bestehende Projektvorlage als Grundlage'),'base')
    await screen.findByRole('option',{name:'Stack · https://gitlab.example/team/stack.git'})
    await userEvent.selectOptions(screen.getByLabelText(/^Repository des Stack-Projekts/),'Stack')
    expect(screen.getByRole('button',{name:'Katalog aktivieren und Vorlage erstellen'})).toBeDisabled()
    expect(writes).toHaveLength(0)
    await userEvent.click(screen.getByRole('checkbox',{name:/Ich habe den Review/}))
    await userEvent.click(screen.getByRole('button',{name:'Katalog aktivieren und Vorlage erstellen'}))
    await screen.findByText('Aktiviert')
    expect(writes).toEqual(['/api/admin/gitlab/snapshots/s1/activate'])
  })

  it('erhält UTF-8-Konfigurationen und behandelt Binärdaten als solche',()=>{
    expect(decodeText(encodeText('Mandant Müller 🧪'))).toBe('Mandant Müller 🧪')
    expect(decodeText(btoa('\0\xFF'))).toBeNull()
  })
})
