import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { Activity, ArrowLeft, ArrowRight, BookOpen, Boxes, Check, ChevronRight, CircleHelp, FileText, Search, ServerCog, ShieldCheck, Users, X, type LucideIcon } from 'lucide-react'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { helpBase, type HelpArticle, type HelpCatalog, type HelpSummary } from '../help'
import { Badge, Button, Card, Empty, Loading, Notice } from '../components/ui'
import { HelpMarkdown } from '../components/HelpMarkdown'

const icons:Record<string,LucideIcon>={grundlagen:BookOpen,tasks:ShieldCheck,tenants:Boxes,verbindungen:ServerCog,personen:Users,betrieb:Activity}
const date=(value:string)=>new Intl.DateTimeFormat('de-DE',{dateStyle:'medium'}).format(new Date(value+'T12:00:00'))

export default function HelpPage(){
  const {user,isAdmin}=useAuth(),{articleId}=useParams(),location=useLocation(),[params,setParams]=useSearchParams()
  const base=helpBase(location.pathname.startsWith('/admin/')?'admin':'portal')
  const [search,setSearch]=useState(params.get('q')||''),[debounced,setDebounced]=useState(search)
  const category=params.get('bereich')||''
  useEffect(()=>{setSearch(params.get('q')||'')},[params])
  useEffect(()=>{const timer=window.setTimeout(()=>setDebounced(search.trim()),200);return()=>window.clearTimeout(timer)},[search])
  const key=[user?.id,isAdmin]
  const catalog=useQuery({queryKey:['help-catalog',...key],queryFn:()=>api<HelpCatalog>('/help/catalog',{cache:'no-store'}),staleTime:0,gcTime:0,refetchOnWindowFocus:true})
  const results=useQuery({queryKey:['help-search',...key,debounced],queryFn:()=>api<HelpCatalog>('/help/catalog?q='+encodeURIComponent(debounced),{cache:'no-store'}),enabled:!articleId&&Boolean(debounced),staleTime:0,gcTime:0})
  const detail=useQuery({queryKey:['help-article',...key,articleId],queryFn:()=>api<HelpArticle>('/help/articles/'+encodeURIComponent(articleId!),{cache:'no-store'}),enabled:Boolean(articleId),staleTime:0,gcTime:0,retry:false,refetchOnWindowFocus:true})
  const data=catalog.data,article=detail.data
  const allowed=useMemo(()=>new Set(data?.articles.map(item=>item.id)||[]),[data])
  useEffect(()=>{
    if(article&&location.hash){let target:string;try{target=decodeURIComponent(location.hash.slice(1))}catch{return}document.getElementById(target)?.scrollIntoView?.({block:'start'})}
  },[article,location.hash])
  const changeSearch=(value:string)=>{setSearch(value);setParams(previous=>{const next=new URLSearchParams(previous);if(value.trim())next.set('q',value.slice(0,200));else next.delete('q');return next},{replace:true})}
  const setCategory=(value:string)=>setParams(previous=>{const next=new URLSearchParams(previous);if(value)next.set('bereich',value);else next.delete('bereich');return next},{replace:true})
  if(articleId){
    if(detail.isLoading)return <Loading label="Hilfeartikel wird geladen …"/>
    if(!article||detail.error instanceof ApiError&&[401,403,404].includes(detail.error.status))return <><Link className="help-back" to={base}><ArrowLeft size={16}/>Zur Dokumentationsübersicht</Link><Notice type="error">{detail.error?.message||'Dieser Hilfeartikel ist nicht verfügbar.'}</Notice></>
    const current=data?.categories.find(item=>item.id===article.category)
    return <div className="help-center"><Link className="help-back" to={base}><ArrowLeft size={16}/>Zur Dokumentationsübersicht</Link>
      {detail.isError&&<Notice type="error">Der Artikel konnte nicht erneut geprüft werden: {detail.error.message}</Notice>}
      <div className="help-article-layout"><aside className="help-chapters"><strong>{current?.title||'Dokumentation'}</strong><nav aria-label="Kapitel dieses Themenbereichs">{data?.articles.filter(item=>item.category===article.category).map(item=><Link key={item.id} to={`${base}/${item.id}`} aria-current={item.id===articleId?'page':undefined}>{item.title}<ChevronRight size={13}/></Link>)}</nav></aside>
        <article className="help-article"><div className="help-article-labels"><Badge>{current?.title||'Anleitung'}</Badge>{article.audience==='admin'&&<Badge tone="warning">Administration</Badge>}</div><h1 className="help-title">{article.title}</h1><p className="help-article-summary">{article.summary}</p><p className="help-content-version">Inhaltsstand: {date(article.content_version)}</p>
          <HelpMarkdown article={article} base={base} allowed={allowed}/>
          {article.related.length>0&&<section className="help-related"><h2>In diesem Themenbereich</h2>{article.related.map(item=><Link key={item.id} to={`${base}/${item.id}`}>{item.title}<ArrowRight size={15}/></Link>)}</section>}
          <p className="help-editorial-note">Diese Anleitung beschreibt den enthaltenen Funktionsstand. Die Einrichtung und Freigabe Ihrer Betriebsumgebung wird separat geprüft.</p>
        </article><aside className="help-toc"><strong>Auf dieser Seite</strong><nav aria-label="Inhaltsverzeichnis">{article.headings.map(item=><a key={item.id} className={item.level>2?'help-toc-nested':''} href={'#'+item.id}>{item.title}</a>)}</nav></aside>
      </div>
    </div>
  }
  if(catalog.isLoading)return <Loading label="Dokumentation wird geladen …"/>
  if(!data||catalog.error instanceof ApiError&&[401,403].includes(catalog.error.status))return <Notice type="error">{catalog.error?.message||'Die Dokumentation ist derzeit nicht verfügbar.'}</Notice>
  const source=debounced?results.data?.articles||[]:data.articles
  const rows=source.filter(item=>!category||item.category===category)
  const filtered=Boolean(debounced||category)
  const featured=['task-starten','tenant-erstellen','registry-profile','task-feed','mail-link','ssh-profile'].map(id=>data.articles.find(item=>item.id===id)).filter((item):item is HelpSummary=>Boolean(item))
  return <div className="help-center"><header className="help-hero"><div className="help-hero-icon"><BookOpen size={25}/></div><div><span className="help-eyebrow">WISSEN & UNTERSTÜTZUNG</span><h1>Hilfe & Dokumentation</h1><p>Anleitungen für den Arbeitsalltag, die Einrichtung und den Betrieb von Semaporter.</p></div></header>
    <div className="help-search-wrap"><label className="help-search"><Search size={21} aria-hidden="true"/><input type="search" maxLength={200} value={search} onChange={event=>changeSearch(event.target.value)} placeholder="Funktion, Begriff oder Fehlermeldung suchen …" aria-label="Dokumentation durchsuchen"/>{search&&<button type="button" aria-label="Suche zurücksetzen" onClick={()=>changeSearch('')}><X size={17}/></button>}</label><span className="help-search-hint">Durchsucht ausschließlich die für Ihr Konto verfügbaren Anleitungen.</span></div>
    <div className="help-shortcuts"><span>Direkt loslegen</span>{featured.slice(0,3).map(item=><Link key={item.id} to={`${base}/${item.id}`}>{item.title}<ArrowRight size={13}/></Link>)}</div>
    <section className="help-category-grid" aria-label="Themenbereiche">{data.categories.map(item=>{const Icon=icons[item.id]||BookOpen;return <button key={item.id} type="button" className={`help-category${category===item.id?' help-category-selected':''}`} aria-pressed={category===item.id} onClick={()=>setCategory(category===item.id?'':item.id)}><span className="help-category-icon"><Icon size={21}/></span><span><strong>{item.title}</strong><span>{item.summary}</span><small>{data.articles.filter(article=>article.category===item.id).length} Anleitungen{category===item.id&&<Check size={13}/>}</small></span></button>})}</section>
    <div className="help-section-heading"><div><h2>{filtered?'Passende Anleitungen':'Häufig benötigte Anleitungen'}</h2><p role="status">{filtered?`${rows.length} ${rows.length===1?'Anleitung':'Anleitungen'}${debounced?' zur Suche „'+debounced+'“':''}`:'Ein schneller Einstieg in zentrale Arbeitsabläufe.'}</p></div>{filtered&&<Button variant="ghost" onClick={()=>{setSearch('');setParams({}, {replace:true})}}>Alle Themen anzeigen</Button>}</div>
    {(catalog.isError||results.isError&&debounced)&&<Notice type="error">Die Dokumentation konnte nicht aktualisiert werden: {(debounced?results.error:catalog.error)?.message}</Notice>}
    {debounced&&results.isFetching?<Loading label="Anleitungen werden gesucht …"/>:rows.length?<Card className="help-results">{(filtered?rows:featured).map(item=><Link key={item.id} className="help-result" to={`${base}/${item.id}`}><FileText size={19}/><span><strong>{item.title}</strong><span>{item.summary}</span></span>{item.audience==='admin'&&<Badge>Admin</Badge>}<ArrowRight size={16}/></Link>)}</Card>:!results.isError&&<Empty title="Keine passende Anleitung gefunden" text="Versuchen Sie einen allgemeineren Begriff, einen Funktionsnamen oder einen Teil der Fehlermeldung."/>}
    {!filtered&&<section className="help-all-articles"><div className="help-section-heading"><div><h2>Alle Anleitungen</h2><p>Nach Themen gegliedert und passend zu Ihren Zugriffsrechten.</p></div></div><div className="help-directory">{data.categories.map(category=><section key={category.id}><h3>{category.title}</h3>{data.articles.filter(item=>item.category===category.id).map(item=><Link key={item.id} to={`${base}/${item.id}`}><ChevronRight size={13}/>{item.title}</Link>)}</section>)}</div></section>}
    <footer className="help-footer"><CircleHelp size={16}/><span>Fragezeichen an Formularen öffnen eine Kurzhilfe, ohne Ihre Eingaben zu verändern.</span><span>Inhaltsstand: {date(data.content_version)}</span></footer>
  </div>
}
