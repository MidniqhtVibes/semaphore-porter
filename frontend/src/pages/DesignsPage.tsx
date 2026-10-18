import { useState, type CSSProperties, type ChangeEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Check, Download, Palette, Trash2, Upload } from 'lucide-react'
import { Badge, Button, Card, Field, Notice, PageHeader } from '../components/ui'
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
      setMessage(`${theme.name} wurde importiert und aktiviert.`);setError('')
    }catch(reason){setError(reason instanceof Error?reason.message:'Das Design konnte nicht importiert werden.')}
  }
  const themeCard=(theme:Theme)=><Card className={`theme-card ${active.id===theme.id?'theme-card-active':''}`} key={theme.id}>
    <ThemePreview theme={theme}/>
    <div className="theme-card-content"><div className="theme-card-title"><h2>{theme.name}</h2>{active.id===theme.id&&<Badge tone="success"><Check size={12}/>Aktiv</Badge>}</div>
      <p>{theme.description}</p>
      <div className="theme-card-meta"><span>{theme.mode==='light'?'Hell':'Dunkel'}</span><span>{theme.font==='sora'?'Sora':'Systemschrift'}</span></div>
      <div className="theme-card-actions"><Button variant={active.id===theme.id?'secondary':'primary'} aria-pressed={active.id===theme.id} disabled={active.id===theme.id} onClick={()=>choose(theme)}>{theme.name} {active.id===theme.id?'ist aktiv':'verwenden'}</Button>
        <Link className="button button-secondary" to={`${studio}?${theme.definition?'design':'vorlage'}=${encodeURIComponent(theme.id)}`}>{theme.definition?'Bearbeiten':'Als Vorlage'}</Link>
        <Button variant="ghost" disabled={themes.length===1} title={themes.length===1?'Mindestens ein Design bleibt erhalten.':'Design entfernen'} aria-label={`${theme.name} entfernen`} onClick={()=>{remove(theme.id);setMessage(`${theme.name} wurde entfernt.`);setError('')}}><Trash2 size={16}/></Button>
      </div>
    </div>
  </Card>
  return <>
    <PageHeader title="Designs" description="Das Aussehen für Administration, Benutzerportal und Anmeldung wählen." actions={<Button variant="secondary" onClick={()=>downloadTheme(active)}><Download size={16}/>Aktives Design exportieren</Button>}/>
    <Card className="design-intro"><div className="design-intro-icon"><Palette size={25}/></div><div><h2>Deine Darstellung</h2><p>Aktuell: <strong>{active.name}</strong>. Die Auswahl gilt für diesen Browser und bleibt beim nächsten Besuch erhalten. Andere Browser oder Geräte werden dadurch nicht umgestellt.</p></div></Card>
    {message&&<div role="status"><Notice type="success">{message}</Notice></div>}
    {error&&<div role="alert"><Notice type="error">{error}</Notice></div>}
    {storageWarning&&<Notice type="info">{storageWarning}</Notice>}
    <Card className="creator-start"><div><h2>Dein eigenes Design</h2><p>Farben, Logo und Texte im eigenen Designstudio gestalten.</p></div><Link className="button button-primary" to={studio}><Palette size={16}/>Design erstellen</Link></Card>
    <div className="section-heading"><h2>Verfügbare Designs</h2><p>Standarddesigns und eigene Designs gemeinsam auswählen und verwalten.</p></div>
    <div className="cards-grid theme-grid">{themes.map(themeCard)}</div>
    {hasHiddenDefaults&&<div className="button-row"><Button variant="secondary" onClick={()=>{restoreDefaults();setMessage('Standarddesigns wurden wiederhergestellt.');setError('')}}>Standarddesigns wiederherstellen</Button></div>}
    <Card className="theme-import"><div className="card-heading"><div><h2><Upload size={18}/>Eigenes Design verwenden</h2><p>Ein exportiertes Design importieren oder eine JSON-Vorlage verwenden. Das Design wird nur in diesem Browser gespeichert.</p></div></div>
      <div className="theme-import-grid"><Field label="Design-Datei (.json)" help="Maximal 1 MB inklusive Bildern. Ein Import mit derselben Design-ID aktualisiert die vorhandene Variante."><input type="file" accept=".json,application/json" onChange={event=>void upload(event)}/></Field>
        <div className="button-row"><a className="button button-secondary" href="/themes/example.theme.json" download><Download size={16}/>JSON-Vorlage</a><a className="row-link" href="/themes/theme.schema.json" download>Formatbeschreibung herunterladen</a></div>
      </div>
    </Card>
  </>
}
