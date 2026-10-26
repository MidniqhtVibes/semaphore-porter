import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Badge, Button, Card, Field, Loading, Notice, PageHeader, formatDate } from '../../components/ui'
import type { GitLabConfig } from '../../gitlab'

export function GitLabPage(){
  const qc=useQueryClient(),query=useQuery({queryKey:['gitlab-config'],queryFn:()=>api<GitLabConfig>('/admin/gitlab')})
  const [form,setForm]=useState({base_url:'',project_id:'',base_branch:'main',write_enabled:false,token:''})
  const [message,setMessage]=useState(''),[error,setError]=useState('')
  useEffect(()=>{if(query.data)setForm({base_url:query.data.base_url||'',project_id:String(query.data.project_id||''),base_branch:query.data.base_branch||'main',write_enabled:!!query.data.write_enabled,token:''})},[query.data])
  const save=useMutation({mutationFn:()=>api<GitLabConfig>('/admin/gitlab',{method:'PUT',body:JSON.stringify({...form,project_id:Number(form.project_id),token:form.token||null})}),onSuccess:data=>{
    qc.setQueryData(['gitlab-config'],data);void qc.invalidateQueries({queryKey:['gitlab-repository']});setForm(v=>({...v,token:''}));setError('');setMessage('GitLab-Verbindung geprüft und gespeichert.')
  },onError:(e:Error)=>{setError(e.message);setMessage('')}})
  const test=useMutation({mutationFn:()=>api<{message:string;sha:string;protected:boolean}>('/admin/gitlab/test',{method:'POST'}),onSuccess:data=>{setError('');setMessage(`${data.message} Basisbranch ${data.protected?'geschützt':'noch ungeschützt'} · ${data.sha.slice(0,12)}`)},onError:(e:Error)=>{setError(e.message);setMessage('')}})
  if(query.isLoading)return <Loading/>
  return <><PageHeader title="GitLab" description="Stack-Repository für Programmpakete, Reviews und freigegebene Katalogstände verbinden." actions={<Link className="button button-secondary" to="/admin/programmpakete">Programmpakete öffnen</Link>}/>
    {(error||query.error)&&<Notice type="error">{error||query.error?.message}</Notice>}{message&&<Notice type="success">{message}</Notice>}
    <Card><div className="card-heading"><h2>Verbindung</h2><Badge tone={query.data?.configured?'success':'neutral'}>{query.data?.configured?'Konfiguriert':'Noch nicht eingerichtet'}</Badge></div>
      {query.data?.project_name&&<p>{query.data.project_name} · zuletzt geprüft {formatDate(query.data.last_tested_at)}</p>}
      <form onSubmit={e=>{e.preventDefault();save.mutate()}}><div className="form-grid columns-2">
        <Field label="GitLab-URL" help="Zum Beispiel https://gitlab.firma.de; ein Installations-Unterpfad ist möglich."><input type="url" required value={form.base_url} onChange={e=>setForm(v=>({...v,base_url:e.target.value}))}/></Field>
        <Field label="Numerische Projekt-ID"><input type="number" min={1} required value={form.project_id} onChange={e=>setForm(v=>({...v,project_id:e.target.value}))}/></Field>
        <Field label="Geschützter Basisbranch"><input required value={form.base_branch} onChange={e=>setForm(v=>({...v,base_branch:e.target.value}))}/></Field>
        <Field label="Project Access Token" help={query.data?.token_present?'Token hinterlegt. Leer lassen zum Beibehalten bei unverändertem Projekt und Branch.':'Lesen: read_api. Branch-Commits und Merge Requests: api mit geeigneter Projektrolle.'}><input type="password" autoComplete="new-password" value={form.token} onChange={e=>setForm(v=>({...v,token:e.target.value}))}/></Field>
      </div><label className="toggle-row"><input type="checkbox" checked={form.write_enabled} onChange={e=>setForm(v=>({...v,write_enabled:e.target.checked}))}/><span>Branch- und Merge-Request-Übergabe in Semaporter erlauben</span></label>
      <p className="muted">Speichern prüft Projekt und Branch. Änderungen am Repository erfolgen erst mit „Branch und Merge Request erstellen“. Ein Wechsel von Instanz, Projekt oder Basisbranch benötigt einen neu eingetragenen Token.</p>
      <div className="button-row"><Button type="submit" loading={save.isPending}>Verbindung prüfen und speichern</Button><Button type="button" variant="secondary" loading={test.isPending} disabled={!query.data?.configured||save.isPending} onClick={()=>test.mutate()}>Gespeicherte Verbindung testen</Button></div></form>
    </Card>
    <Card><h2>Ablauf</h2><ol><li>Programmpaket entwerfen und lokal prüfen.</li><li>Diff ansehen und Branch mit Merge Request ausdrücklich erstellen.</li><li>CI und menschlichen Review in GitLab durchführen und dort mergen.</li><li>Unter „Versionen & Übernahme“ den geprüften Katalog zusammen mit einer neuen Projektvorlage aktivieren.</li></ol><p>Die Anwendung verwaltet weder GitLab-Benutzer noch Runner. Zugangswerte gehören in Vault; Programmpakete enthalten ausschließlich Referenzen.</p></Card>
  </>
}
