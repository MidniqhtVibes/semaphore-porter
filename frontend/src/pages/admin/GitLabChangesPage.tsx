import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../../api'
import { Button, Card, Loading, Notice, PageHeader, StatusBadge } from '../../components/ui'
import type { PackageDraft } from '../../gitlab'

export function GitLabChangesPage({pipelinesOnly=false}:{pipelinesOnly?:boolean}){
  const query=useQuery({queryKey:['package-drafts'],queryFn:()=>api<PackageDraft[]>('/admin/program-packages')})
  const [busy,setBusy]=useState(''),[error,setError]=useState('')
  async function refresh(draft:PackageDraft){setBusy(draft.id);setError('');try{await api(`/admin/program-packages/${draft.id}/refresh`,{method:'POST'});await query.refetch()}catch(e){setError((e as Error).message)}finally{setBusy('')}}
  if(query.isLoading)return <Loading/>
  const rows=query.data?.filter(d=>d.branch)||[]
  return <><PageHeader title={pipelinesOnly?'Prüfungen':'Änderungen & Freigaben'} description={pipelinesOnly?'CI-Ergebnisse der gespeicherten Commit-SHA. Fehlende oder übersprungene Pipelines gelten nicht als erfolgreiche Prüfung.':'Vorbereitete Branches und Merge Requests. Review und Merge erfolgen in GitLab.'}/>
    {(error||query.error)&&<Notice type="error">{error||query.error?.message}</Notice>}
    {!rows.length&&<Card><p>Noch keine Übergaben vorhanden.</p><Link to="/admin/programmpakete">Programmpaket erstellen</Link></Card>}
    {rows.map(d=><Card key={d.id}><div className="card-heading"><div><h2><Link to={`/admin/programmpakete/${d.id}`}>{d.name}</Link></h2><p>{d.branch}</p></div><StatusBadge status={d.status}/></div>
      <p>Commit <code>{d.commit_sha?.slice(0,12)||'Ergebnis noch abzugleichen'}</code></p>{d.last_error&&<Notice type="error">{d.last_error}</Notice>}
      {d.remote_status?.web_url&&<a href={d.remote_status.web_url} target="_blank" rel="noreferrer">Merge Request #{d.merge_request_iid} in GitLab</a>}
      {pipelinesOnly&&(d.remote_status?.pipelines?.length?<div className="table-wrap"><table><thead><tr><th>Pipeline</th><th>Revision</th><th>Status</th></tr></thead><tbody>{d.remote_status.pipelines.map(p=><tr key={p.id}><td>{p.web_url?<a href={p.web_url} target="_blank" rel="noreferrer">#{p.id}</a>:p.id}</td><td><code>{p.sha.slice(0,12)}</code></td><td><StatusBadge status={p.status}/></td></tr>)}</tbody></table></div>:<p>Keine Pipeline-Ergebnisse gespeichert. Status aktualisieren.</p>)}
      <div className="button-row"><Button variant="secondary" disabled={!d.merge_request_iid||!!busy} loading={busy===d.id} onClick={()=>void refresh(d)}>Status aus GitLab aktualisieren</Button><Link to={`/admin/programmpakete/${d.id}`}>{d.merge_request_iid?'Entwurf und Diff':'Übergabe abgleichen'}</Link>{d.status==='merged'&&<Link to="/admin/uebernahme">Katalogübernahme vorbereiten</Link>}</div>
    </Card>)}
  </>
}
