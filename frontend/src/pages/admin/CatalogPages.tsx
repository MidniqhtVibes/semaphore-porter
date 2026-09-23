import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AppWindow, FileJson, PackageOpen, Plus, Upload } from 'lucide-react'
import { api } from '../../api'
import { Badge, Button, Card, Empty, Field, Loading, Modal, Notice, PageHeader, formatDate } from '../../components/ui'

type ProjectTemplate={id:string;name:string;description:string;source_type:string;source_project_id?:number|null;survey_catalog:Record<string,unknown[]>;task_templates:string[];environments:string[];updated_at:string}
type Project={id:number;name:string}
type Preset={id:string;name:string;category:string;description:string;current_version:number;is_builtin:boolean;values:Record<string,unknown>}

export function ProjectTemplatesPage(){
  const qc=useQueryClient(),[importOpen,setImportOpen]=useState(false),[uploadOpen,setUploadOpen]=useState(false)
  const query=useQuery({queryKey:['project-templates'],queryFn:()=>api<ProjectTemplate[]>('/admin/project-templates')})
  const refresh=()=>void qc.invalidateQueries({queryKey:['project-templates']})
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Projektvorlagen" description="Gespeicherte Semaphore-Backups bilden die unveränderte Quelle für neue Tenant-Projekte." actions={<><Button variant="secondary" onClick={()=>setUploadOpen(true)}><Upload size={16}/>JSON hochladen</Button><Button onClick={()=>setImportOpen(true)}><Plus size={16}/>Aus Semaphore</Button></>}/>
    <div className="cards-grid">{query.data?.map(item=><Card key={item.id}><div className="card-heading"><div className="name-cell"><div className="square-icon"><PackageOpen size={18}/></div><div><strong>{item.name}</strong><span>{item.description}</span></div></div><Badge tone={item.source_type==='semaphore'?'info':'neutral'}>{item.source_type}</Badge></div><div className="template-metrics"><span><strong>{item.task_templates.length}</strong> Tasks</span><span><strong>{item.environments.length}</strong> Gruppen</span><span><strong>{Object.keys(item.survey_catalog).length}</strong> Survey-Typen</span></div><p className="muted">Geändert {formatDate(item.updated_at)}</p></Card>)}</div>{!query.data?.length&&<Empty title="Keine Projektvorlagen" text="Importieren Sie ein vorhandenes Semaphore-Projekt oder laden Sie ein Backup hoch."/>}
    {importOpen&&<ImportModal onClose={()=>setImportOpen(false)} onSaved={()=>{setImportOpen(false);refresh()}}/>}{uploadOpen&&<UploadModal onClose={()=>setUploadOpen(false)} onSaved={()=>{setUploadOpen(false);refresh()}}/>}
  </>
}

function ImportModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const projects=useQuery({queryKey:['semaphore-projects'],queryFn:()=>api<Project[]>('/admin/semaphore/projects')})
  const [projectId,setProjectId]=useState(''),[name,setName]=useState(''),[description,setDescription]=useState(''),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api('/admin/project-templates/from-semaphore',{method:'POST',body:JSON.stringify({source_project_id:Number(projectId),name,description}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  return <Modal title="Semaphore-Projekt importieren" onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}{projects.isLoading?<Loading/>:<div className="form-grid"><Field label="Quellprojekt"><select value={projectId} onChange={e=>{setProjectId(e.target.value);setName(projects.data?.find(p=>p.id===Number(e.target.value))?.name||'')}}><option value="">Bitte wählen …</option>{projects.data?.map(p=><option key={p.id} value={p.id}>{p.name} (#{p.id})</option>)}</select></Field><Field label="Vorlagenname"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Beschreibung"><textarea value={description} onChange={e=>setDescription(e.target.value)}/></Field></div>}<div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button disabled={!projectId||!name} loading={mutation.isPending} onClick={()=>mutation.mutate()}>Backup importieren</Button></div></Modal>
}

function UploadModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const [file,setFile]=useState<File|null>(null),[name,setName]=useState(''),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>{const body=new FormData();if(file)body.append('file',file);return api(`/admin/project-templates/upload?name=${encodeURIComponent(name)}`,{method:'POST',body})},onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  return <Modal title="Projektbackup hochladen" onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<Field label="Vorlagenname"><input value={name} onChange={e=>setName(e.target.value)}/></Field><label className="upload-zone"><FileJson size={28}/><strong>{file?.name||'JSON-Backupdatei auswählen'}</strong><span>Maximal 10 MB</span><input type="file" accept="application/json,.json,.backup" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button disabled={!file||name.length<2} loading={mutation.isPending} onClick={()=>mutation.mutate()}>Hochladen</Button></div></Modal>
}

export function ApplicationsPage(){
  const query=useQuery({queryKey:['project-templates'],queryFn:()=>api<ProjectTemplate[]>('/admin/project-templates')})
  const apps=useMemo(()=>{const result=new Map<string,{sources:Set<string>;databases:Set<unknown>;datasets:Set<unknown>}>();for(const template of query.data||[]){for(const value of template.survey_catalog.application_id||[]){const key=String(value);const row=result.get(key)||{sources:new Set(),databases:new Set(),datasets:new Set()};row.sources.add(template.name);(template.survey_catalog.database_type||[]).forEach(v=>row.databases.add(v));(template.survey_catalog.dataset_id||[]).forEach(v=>row.datasets.add(v));result.set(key,row)}}return [...result.entries()]},[query.data])
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Anwendungskatalog" description="Aktuell ausschließlich aus real vorhandenen Semaphore-Survey-Werten gelesen; eine GitLab-Anbindung ist modular vorbereitet, aber nicht fingiert."/>{apps.length?<div className="cards-grid">{apps.map(([id,row])=><Card key={id}><div className="card-heading"><div className="name-cell"><div className="square-icon"><AppWindow/></div><div><strong>{id}</strong><span>{[...row.sources].join(', ')}</span></div></div></div><div className="tag-section"><span>Datenbanken</span><div className="badge-row">{[...row.databases].map(v=><Badge key={String(v)}>{String(v)}</Badge>)}</div></div><div className="tag-section"><span>Testdaten</span><div className="badge-row">{[...row.datasets].map(v=><Badge key={String(v)}>{String(v)}</Badge>)}</div></div></Card>)}</div>:<Empty title="Keine Anwendungen erkannt" text="Importierte Vorlagen enthalten noch keine application_id-Survey-Werte."/>}</>
}

export function PresetsPage(){
  const qc=useQueryClient(),query=useQuery({queryKey:['presets'],queryFn:()=>api<Preset[]>('/admin/presets')}),[open,setOpen]=useState(false)
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="Presets" description="Versionierte, wiederverwendbare Variablengruppen ohne Klartext-Zugangsdaten." actions={<Button onClick={()=>setOpen(true)}><Plus size={16}/>Eigenes Preset</Button>}/><div className="cards-grid">{query.data?.map(item=><Card key={item.id}><div className="card-heading"><div><h3>{item.name}</h3><p>{item.description}</p></div><Badge tone={item.is_builtin?'info':'neutral'}>{item.is_builtin?'Standard':'Eigene'} · v{item.current_version}</Badge></div><pre className="json-preview">{JSON.stringify(item.values,null,2)}</pre></Card>)}</div>{open&&<PresetModal onClose={()=>setOpen(false)} onSaved={()=>{setOpen(false);void qc.invalidateQueries({queryKey:['presets']})}}/>}</>
}

function PresetModal({onClose,onSaved}:{onClose:()=>void;onSaved:()=>void}){
  const [name,setName]=useState(''),[category,setCategory]=useState('application'),[description,setDescription]=useState(''),[values,setValues]=useState('{}'),[error,setError]=useState('')
  const mutation=useMutation({mutationFn:()=>api('/admin/presets',{method:'POST',body:JSON.stringify({name,category,description,values:JSON.parse(values)}),headers:{'Content-Type':'application/json'}}),onSuccess:onSaved,onError:(e:Error)=>setError(e.message)})
  return <Modal title="Preset erstellen" onClose={onClose}>{error&&<Notice type="error">{error}</Notice>}<div className="form-grid columns-2"><Field label="Name"><input value={name} onChange={e=>setName(e.target.value)}/></Field><Field label="Kategorie"><select value={category} onChange={e=>setCategory(e.target.value)}>{['deployment','registry','postgresql','mariadb','mysql','vault','smtp','application'].map(v=><option key={v}>{v}</option>)}</select></Field><Field label="Beschreibung"><input value={description} onChange={e=>setDescription(e.target.value)}/></Field></div><Field label="Werte (JSON)" help="Secret-verdächtige Schlüsselnamen werden serverseitig abgelehnt."><textarea className="code-editor" rows={12} value={values} onChange={e=>setValues(e.target.value)}/></Field><div className="modal-actions"><Button variant="secondary" onClick={onClose}>Abbrechen</Button><Button loading={mutation.isPending} onClick={()=>{try{JSON.parse(values);mutation.mutate()}catch{setError('Ungültiges JSON.')}}}>Speichern</Button></div></Modal>
}

