import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api'
import { Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader } from '../../components/ui'

type Project = {id:number;name:string;alert:boolean;alert_chat:string|null;max_parallel_tasks:number}
type Resource = {id:number;revision:string;values:Record<string,unknown>;secrets:Array<{id:number;name:string;type:string}>}
const kinds = {environment:'Variablengruppen',repositories:'Repositories',inventory:'Inventories',templates:'Task Templates',keys:'SSH & Zugangsdaten'} as const
type Kind = keyof typeof kinds
const defaultsName = (name:unknown) => ['semaphore-default','semaphore-defaults'].includes(String(name).toLowerCase())

export function ProjectsPage(){
  const [open,setOpen]=useState(false),[search,setSearch]=useState('')
  const query=useQuery({queryKey:['semaphore-projects'],queryFn:()=>api<Project[]>('/admin/semaphore/projects')})
  const qc=useQueryClient(),navigate=useNavigate()
  return <><PageHeader title="Semaphore-Projekte" description="Projekte direkt auf dem verbundenen Semaphore-Server verwalten." actions={<Button onClick={()=>setOpen(true)}>Projekt erstellen</Button>}/>
    {query.isError&&<Notice type="error">{query.error.message}</Notice>}
    {query.isLoading?<Loading/>:<Card><div className="toolbar"><input aria-label="Projekte suchen" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Projekte suchen …"/><Button variant="secondary" onClick={()=>void query.refetch()}>Aktualisieren</Button></div><div className="compact-list">{query.data?.filter(p=>p.name.toLowerCase().includes(search.toLowerCase())).map(p=><div key={p.id}><div><strong>{p.name}</strong><span>#{p.id}</span></div><Link className="button button-secondary" to={`/admin/projekte/${p.id}`}>Öffnen</Link></div>)}</div>{!query.data?.length&&<Empty title="Keine Projekte" text="Verbinden Sie Semaphore oder erstellen Sie ein Projekt."/>}</Card>}
    {open&&<NewProject onClose={()=>setOpen(false)} onCreated={p=>{void qc.invalidateQueries({queryKey:['semaphore-projects']});navigate(`/admin/projekte/${p.id}`)}}/>}
  </>
}

function NewProject({onClose,onCreated}:{onClose:()=>void;onCreated:(p:Project)=>void}){
  const [name,setName]=useState('')
  const mutation=useMutation({mutationFn:()=>api<Project>('/admin/semaphore/projects',{method:'POST',body:JSON.stringify({name})}),onSuccess:onCreated})
  return <Modal title="Leeres Semaphore-Projekt erstellen" onClose={onClose}><Field label="Projektname"><input value={name} onChange={e=>setName(e.target.value)}/></Field>{mutation.isError&&<Notice type="error">{mutation.error.message} Bei unklarem Ergebnis zuerst die Projektliste aktualisieren.</Notice>}<Button disabled={name.trim().length<2||mutation.isError} loading={mutation.isPending} onClick={()=>mutation.mutate()}>Projekt erstellen</Button></Modal>
}

export function ProjectEditorPage(){
  const {projectId}=useParams(),qc=useQueryClient(),navigate=useNavigate()
  const [kind,setKind]=useState<Kind>('environment'),[editing,setEditing]=useState<Resource|null|undefined>(),[confirm,setConfirm]=useState(''),[message,setMessage]=useState('')
  const base=`/admin/semaphore/projects/${projectId}`
  const query=useQuery({queryKey:['semaphore-project',projectId],queryFn:()=>api<{project:Project;revision:string}>(base)})
  const resources=useQuery({queryKey:['semaphore-resources',projectId,kind],queryFn:()=>api<Resource[]>(`${base}/resources/${kind}`)})
  const [name,setName]=useState('')
  useEffect(()=>{if(query.data)setName(query.data.project.name)},[query.data])
  const save=useMutation({mutationFn:()=>api(base,{method:'PUT',body:JSON.stringify({...query.data?.project,name,revision:query.data?.revision})}),onSuccess:()=>{setMessage('Projekt gespeichert.');void query.refetch();void qc.invalidateQueries({queryKey:['semaphore-projects']})}})
  const remove=useMutation({mutationFn:()=>api(base,{method:'DELETE',body:JSON.stringify({confirm_name:confirm,revision:query.data?.revision})}),onSuccess:()=>{void qc.invalidateQueries({queryKey:['semaphore-projects']});navigate('/admin/projekte')}})
  const clone=useMutation({mutationFn:()=>api<{id:string}>('/admin/project-templates/from-semaphore',{method:'POST',body:JSON.stringify({source_project_id:Number(projectId),name:`Kopie von ${query.data?.project.name}`})}),onSuccess:value=>navigate(`/admin/tenant-erstellen?template=${value.id}`)})
  if(query.isLoading)return <Loading/>
  if(!query.data)return <Notice type="error">{query.error?.message||'Projekt nicht gefunden.'}</Notice>
  return <><PageHeader title={query.data.project.name} description={`Semaphore-Projekt #${projectId}`} actions={<Button loading={clone.isPending} onClick={()=>clone.mutate()}>Als neuen Tenant duplizieren</Button>}/>
    {[save.error,remove.error,clone.error,resources.error].filter(Boolean).map((e,i)=><Notice type="error" key={i}>{e?.message}</Notice>)}{message&&<Notice type="success">{message}</Notice>}
    <Card><Field label="Projektname"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Button loading={save.isPending} onClick={()=>save.mutate()} disabled={name.trim().length<2}>Projekt speichern</Button></Card>
    <div className="button-row">{Object.entries(kinds).map(([key,label])=><Button key={key} variant={kind===key?'primary':'secondary'} onClick={()=>{setKind(key as Kind);setEditing(undefined)}}>{label}</Button>)}</div>
    <Card><div className="card-heading"><h2>{kinds[kind]}</h2><Button onClick={()=>setEditing(null)}>Hinzufügen</Button></div>{resources.isLoading?<Loading/>:<div className="compact-list">{resources.data?.map(item=><div key={item.id}><div><strong>{String(item.values.name)}</strong><span>#{item.id}{item.secrets.length?` · ${item.secrets.length} geschützte Werte`:''}</span></div><Button variant="secondary" onClick={()=>setEditing(item)}>Bearbeiten</Button></div>)}</div>}</Card>
    <Card><h2>Projekt in Semaphore löschen</h2><p>Dies löscht das Projekt und seine Konfiguration in Semaphore. Laufende Docker-Deployments bleiben bestehen. Zur Bestätigung den Projektnamen eingeben.</p><Field label="Projektname zur Löschbestätigung"><input value={confirm} onChange={e=>setConfirm(e.target.value)}/></Field><Button variant="danger" disabled={confirm!==query.data.project.name||remove.isError} loading={remove.isPending} onClick={()=>remove.mutate()}>Semaphore-Projekt endgültig löschen</Button></Card>
    {editing!==undefined&&<ResourceEditor key={`${kind}-${editing?.id||'new'}`} kind={kind} item={editing} base={base} onClose={()=>setEditing(undefined)} onSaved={()=>{setEditing(undefined);setMessage('Ressource in Semaphore gespeichert.');void resources.refetch()}}/>}
  </>
}

function ResourceEditor({kind,item,base,onClose,onSaved}:{kind:Kind;item:Resource|null;base:string;onClose:()=>void;onSaved:()=>void}){
  const initial:Record<string,unknown>=item?.values||({environment:{name:'Semaphore-Defaults',json:{},env:{}},repositories:{name:'Git',git_url:'',git_branch:'main',ssh_key_id:null},inventory:{name:'Zielhost',type:'static',inventory:'[docker_test]\nserver.example ansible_user=deploy',ssh_key_id:null,become_key_id:null},templates:{name:'Deployment',app:'ansible',playbook:'playbooks/deploy-temporary-program.yml',repository_id:0,inventory_id:0,environment_ids:[],survey_vars:[],arguments:'[]'},keys:{name:'SSH-Zugang',type:'ssh'}}[kind])
  const [name,setName]=useState(String(initial.name)),[text,setText]=useState(JSON.stringify(kind==='environment'&&defaultsName(initial.name)?Object.fromEntries(Object.entries(initial.json as Record<string,unknown>).filter(([key])=>!['tenant_slug','runtime_scope_id'].includes(key))):kind==='environment'?initial.json:initial,null,2)),[env,setEnv]=useState(JSON.stringify(initial.env||{},null,2)),[tenant,setTenant]=useState(String((initial.json as Record<string,unknown>|undefined)?.tenant_slug||'')),[scope,setScope]=useState(String((initial.json as Record<string,unknown>|undefined)?.runtime_scope_id||'')),[review,setReview]=useState<Record<string,unknown>|null>(null),[error,setError]=useState('')
  const [keyLogin,setKeyLogin]=useState(''),[keySecret,setKeySecret]=useState(''),[keyPassphrase,setKeyPassphrase]=useState('')
  const [secretName,setSecretName]=useState(''),[secretValue,setSecretValue]=useState(''),[secretType,setSecretType]=useState('env')
  const mutation=useMutation({mutationFn:()=>api(`${base}/resources/${kind}${item?`/${item.id}`:''}`,{method:item?'PUT':'POST',body:JSON.stringify({revision:item?.revision,values:review,key_login:keyLogin||undefined,key_secret:keySecret||undefined,key_passphrase:keyPassphrase||undefined,secrets:secretName?[{name:secretName,secret:secretValue,type:secretType,operation:item?.secrets.some(s=>s.name===secretName&&s.type===secretType)?'update':'create',id:item?.secrets.find(s=>s.name===secretName&&s.type===secretType)?.id}]:[]})}),onSuccess:()=>{setSecretValue('');onSaved()}})
  const prepare=()=>{try{const values=JSON.parse(text);if(!values||Array.isArray(values)||typeof values!=='object')throw new Error('Ein JSON-Objekt ist erforderlich.');if(kind==='environment'){const vars={...values};if(defaultsName(name)){vars.tenant_slug=tenant;vars.runtime_scope_id=scope}setReview({name,json:vars,env:JSON.parse(env)})}else setReview(values);setError('')}catch(e){setError(e instanceof Error?e.message:'Ungültiges JSON.')}}
  return <Modal title={`${kinds[kind]} ${item?'bearbeiten':'anlegen'}`} onClose={onClose}>{(error||mutation.error)&&<Notice type="error">{error||mutation.error?.message}</Notice>}
    {review?<><h3>Änderungen prüfen</h3><pre className="json-preview">{JSON.stringify(review,null,2)}</pre>{secretName&&<p>Geschützten Wert „{secretName}“ setzen. Der Inhalt wird nicht angezeigt.</p>}<div className="button-row"><Button variant="secondary" onClick={()=>setReview(null)}>Zurück</Button><Button loading={mutation.isPending} disabled={mutation.isError} onClick={()=>mutation.mutate()}>In Semaphore speichern</Button></div>{mutation.isError&&<Notice type="info">Bei unklarem Ergebnis schließen und die Ressourcen neu laden, bevor erneut geschrieben wird.</Notice>}</>:<>
    {kind==='environment'&&<><Field label="Gruppenname"><input value={name} onChange={e=>setName(e.target.value)}/></Field>{defaultsName(name)&&<div className="form-grid columns-2"><Field label="Tenant-ID (tenant_slug)"><input value={tenant} onChange={e=>setTenant(e.target.value)}/></Field><Field label="Runtime-Scope (runtime_scope_id)"><input value={scope} onChange={e=>setScope(e.target.value)}/></Field></div>}</>}
    {kind==='environment'&&defaultsName(name)&&<Notice type="info">Änderungen an Tenant oder Runtime-Scope benennen bestehende Deployments und Vault-Pfade nicht automatisch um.</Notice>}<Field label={kind==='environment'?'Extra Variables (JSON)':'Konfiguration (JSON)'} help={kind==='environment'?'Tenant und Scope werden bei Semaphore-Defaults aus den beiden Feldern übernommen. Bestehende geheime Werte bleiben erhalten.':'Ressourcen-IDs beziehen sich auf dieses Projekt. Vor dem Speichern Zuordnungen prüfen.'}><textarea className="code-editor" rows={16} value={text} onChange={e=>setText(e.target.value)}/></Field>
    {kind==='environment'&&<><Field label="Prozessvariablen (JSON)"><textarea className="code-editor" rows={5} value={env} onChange={e=>setEnv(e.target.value)}/></Field><h3>Geschützten Wert setzen</h3><p>{item?.secrets.map(s=>`${s.name} (${s.type})`).join(', ')||'Keine geschützten Werte gemeldet.'}</p><Field label="Secret-Name"><input value={secretName} onChange={e=>setSecretName(e.target.value)}/></Field><Field label="Secret-Typ"><select value={secretType} onChange={e=>setSecretType(e.target.value)}><option value="env">Prozessvariable, z. B. ANSIBLE_HASHI_VAULT_SECRET_ID</option><option value="var">Extra Variable</option></select></Field><Field label="Neuer geheimer Wert"><input type="password" autoComplete="new-password" value={secretValue} onChange={e=>setSecretValue(e.target.value)}/></Field></>}
    {kind==='keys'&&<><Field label="Login (optional)"><input value={keyLogin} onChange={e=>setKeyLogin(e.target.value)}/></Field><Field label="Neuer privater SSH-Schlüssel / Passwort" help="Leer lassen, um bestehende Zugangsdaten zu erhalten."><textarea rows={5} autoComplete="off" value={keySecret} onChange={e=>setKeySecret(e.target.value)}/></Field><Field label="SSH-Passphrase (optional)"><input type="password" autoComplete="new-password" value={keyPassphrase} onChange={e=>setKeyPassphrase(e.target.value)}/></Field></>}
    <Button disabled={Boolean(secretName)&&!secretValue} onClick={prepare}>Änderungen prüfen</Button></>}
  </Modal>
}
