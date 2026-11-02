import { useState, type CSSProperties, type ChangeEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Check, Download, MoreHorizontal, Palette, Pencil, RotateCcw, Trash2, Upload } from 'lucide-react'
import { Badge, Button, Card, Empty, Field, Notice, PageHeader } from '../components/ui'
import { useTheme } from '../designs/ThemeProvider'
import { ThemeLogo } from '../components/ThemeLogo'
import { exportThemeFile, FONT_STACKS, MAX_THEME_BYTES, type Theme } from '../designs/themes'

function ThemePreview({theme}:{theme:Theme}){
  const style=Object.fromEntries(Object.entries(theme.colors).map(([key,value])=>[`--${key}`,value])) as CSSProperties
  return <div className="theme-preview" style={{...style,'--font-family':FONT_STACKS[theme.font],'--radius':`${theme.radius}px`} as CSSProperties} aria-hidden="true">
    <div className="theme-preview-nav"><ThemeLogo theme={theme} size={18} className="theme-preview-mark"/><i/><i className="selected"/><i/></div>
    <div className="theme-preview-main"><div className="theme-preview-bar"><span>{theme.copy?.title||'Tenant Portal'}</span><span className="theme-preview-dot"/></div>
      <div className="theme-preview-body"><strong>Dein Arbeitsbereich</strong><span>Projekte verwalten</span>
        <div className="theme-preview-card"><span>Aktive Tenants</span><strong>12</strong><span className="theme-preview-status">Bereit</span></div>
        <span className="theme-preview-action">Tenant erstellen</span>
      </div>
    </div>
  </div>
}
function downloadTheme(theme:Theme){
  const blob=new Blob([JSON.stringify(exportThemeFile(theme),null,2)+'\n'],{type:'application/json'})
  const url=URL.createObjectURL(blob), link=document.createElement('a')
  link.href=url;link.download=`${theme.id.replace('custom:','')}.theme.json`
  document.body.append(link);link.click();link.remove()
  window.setTimeout(()=>URL.revokeObjectURL(url),1000)
}
export function DesignsPage(){
  const {themes,active,select,importTheme,remove,storageWarning,restoreDefaults,hasHiddenDefaults}=useTheme()
  const location=useLocation()
  const studio=`${location.pathname.replace(/\/$/,'')}/studio`
  const [message,setMessage]=useState<string>(()=>location.state?.designMessage||''), [error,setError]=useState('')
  const [collection,setCollection]=useState<'all'|'custom'|'builtin'>('all'),[mode,setMode]=useState<'all'|'light'|'dark'>('all'),[importOpen,setImportOpen]=useState(false)
  const customCount=themes.filter(theme=>theme.definition).length
  const filtered=themes.filter(theme=>(collection==='all'||Boolean(theme.definition)===(collection==='custom'))&&(mode==='all'||theme.mode===mode))
  const choose=(theme:Theme)=>{select(theme.id);setMessage(`${theme.name} ist jetzt aktiv.`);setError('')}
  const upload=async(event:ChangeEvent<HTMLInputElement>)=>{
    const file=event.target.files?.[0]
    event.target.value=''
    if(!file)return
    try{
      if(file.size>MAX_THEME_BYTES)throw new Error('Die Design-Datei darf maximal 1 MB enthalten.')
      let value:unknown
      try{value=JSON.parse(await file.text())}catch{throw new Error('Die Datei enthält kein gültiges JSON.')}
      const theme=importTheme(value)
      setMessage(`${theme.name} wurde importiert und aktiviert.`);setError('');setCollection('custom');setMode('all')
    }catch(reason){setError(reason instanceof Error?reason.message:'Das Design konnte nicht importiert werden.')}
  }
  const themeCard=(theme:Theme)=><Card role="article" aria-label={theme.name} className={`theme-card ${active.id===theme.id?'theme-card-active':''}`} key={theme.id}>
    <ThemePreview theme={theme}/>
    <div className="theme-card-content"><div className="theme-card-title"><h2>{theme.name}</h2>{active.id===theme.id&&<Badge tone="success"><Check size={12}/>Aktiv</Badge>}</div>
      <p>{theme.description}</p>
      <div className="theme-card-meta"><span>{theme.mode==='light'?'Hell':'Dunkel'}</span><span>{theme.definition?'Eigenes Design':'Standarddesign'}</span></div>
      <div className="theme-card-actions"><Button variant="secondary" aria-label={`${theme.name} ${active.id===theme.id?'ist aktiv':'verwenden'}`} aria-pressed={active.id===theme.id} disabled={active.id===theme.id} onClick={()=>choose(theme)}>{active.id===theme.id?<><Check size={15}/>Aktiv</>:'Anwenden'}</Button>
        <details className="design-card-menu" name="design-card-actions" onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget))event.currentTarget.removeAttribute('open')}} onKeyDown={event=>{if(event.key==='Escape'){event.preventDefault();event.currentTarget.removeAttribute('open');event.currentTarget.querySelector('summary')?.focus()}}}>
          <summary tabIndex={0} aria-label={`${theme.name} verwalten`} title="Weitere Aktionen"><MoreHorizontal size={20}/></summary>
          <div className="design-card-menu-items">
            <Link className="design-menu-item" to={`${studio}?${theme.definition?'design':'vorlage'}=${encodeURIComponent(theme.id)}`}><Pencil size={15}/>{theme.definition?'Bearbeiten':'Als Vorlage'}</Link>
            <Button variant="ghost" className="design-menu-item" onClick={event=>{downloadTheme(theme);event.currentTarget.closest('details')?.removeAttribute('open')}}><Download size={15}/>JSON exportieren</Button>
            <Button variant="ghost" className="design-menu-item design-menu-danger" disabled={themes.length===1} title={themes.length===1?'Mindestens ein Design bleibt erhalten.':undefined} aria-label={`${theme.name} entfernen`} onClick={()=>{remove(theme.id);setMessage(`${theme.name} wurde entfernt.`);setError('')}}><Trash2 size={15}/>Entfernen</Button>
          </div>
        </details>
      </div>
    </div>
  </Card>
  return <>
    <PageHeader title="Designs" description="Dein Erscheinungsbild für Portal und Anmeldung." actions={<><Button variant="secondary" aria-expanded={importOpen} aria-controls="design-import" onClick={()=>setImportOpen(value=>!value)}><Upload size={16}/>Design importieren</Button><Link className="button button-primary" to={studio}><Palette size={16}/>Design erstellen</Link></>}/>
    {message&&<div role="status"><Notice type="success">{message}</Notice></div>}
    {error&&<div role="alert"><Notice type="error">{error}</Notice></div>}
    {storageWarning&&<Notice type="info">{storageWarning}</Notice>}
    <Card className="design-active" role="region" aria-label="Aktives Design"><div className="design-active-summary"><span className="design-active-icon"><Check size={22}/></span><div><span className="design-active-label">Aktives Design</span><strong>{active.name}</strong><p>Nur in diesem Browser gespeichert · {active.mode==='light'?'Hell':'Dunkel'} · {active.font==='sora'?'Sora':'Systemschrift'}</p></div></div><div className="button-row"><Link className="button button-secondary" to={`${studio}?${active.definition?'design':'vorlage'}=${encodeURIComponent(active.id)}`}><Pencil size={15}/>{active.definition?'Bearbeiten':'Als Vorlage anpassen'}</Link><Button variant="ghost" onClick={()=>downloadTheme(active)}><Download size={15}/>Aktives Design exportieren</Button></div></Card>
    {importOpen&&<Card className="theme-import" id="design-import"><div className="card-heading"><div><h2><Upload size={18}/>JSON-Datei importieren</h2><p>Ein gespeichertes Design auswählen. Nach dem Import wird es in diesem Browser aktiviert.</p></div></div>
      <div className="theme-import-grid"><Field label="Design-Datei (.json)" help="Maximal 1 MB inklusive Bildern. Ein Import mit derselben Design-ID aktualisiert die vorhandene Variante."><input type="file" accept=".json,application/json" onChange={event=>void upload(event)}/></Field>
        <details className="design-import-help"><summary>Vorlage & Format</summary><div className="button-row"><a className="button button-secondary" href="/themes/example.theme.json" download><Download size={16}/>JSON-Vorlage</a><a className="row-link" href="/themes/theme.schema.json" download>Formatbeschreibung herunterladen</a></div></details>
      </div>
    </Card>}
    <section className="design-collection" aria-labelledby="design-collection-title"><div className="design-collection-heading"><h2 id="design-collection-title">Designauswahl</h2><span>{filtered.length} {filtered.length===1?'Design':'Designs'}</span></div>
      <div className="design-collection-toolbar"><div className="design-collection-tabs" role="group" aria-label="Designkategorie">{([['all','Alle',themes.length],['custom','Eigene',customCount],['builtin','Standard',themes.length-customCount]] as const).map(([value,label,count])=><button type="button" key={value} aria-pressed={collection===value} onClick={()=>setCollection(value)}>{label}<span>{count}</span></button>)}</div><Field label="Darstellung"><select value={mode} onChange={event=>setMode(event.target.value as typeof mode)}><option value="all">Hell & Dunkel</option><option value="light">Nur Hell</option><option value="dark">Nur Dunkel</option></select></Field></div>
      {filtered.length?<div className="cards-grid theme-grid">{filtered.map(themeCard)}</div>:<Empty title="Keine Designs in dieser Auswahl" text={collection==='custom'?'Ein Design erstellen oder eine JSON-Datei importieren.':'Kategorie oder Darstellung ändern.'}/>}
      {hasHiddenDefaults&&<div className="design-restore"><Button variant="ghost" onClick={()=>{restoreDefaults();setMessage('Standarddesigns wurden wiederhergestellt.');setError('')}}><RotateCcw size={15}/>Standarddesigns wiederherstellen</Button></div>}
    </section>
  </>
}
