import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { ArrowRight, Check, CheckCircle2, ChevronDown, ChevronRight, CircleAlert, ClipboardList, Folder, Maximize2, Menu, Monitor, PanelLeftClose, Play, Plus, Search, ShieldCheck, Smartphone, X } from 'lucide-react'
import { LegalContent } from '../components/LegalContent'
import { ThemeLogo } from '../components/ThemeLogo'
import { navigationContext, type NavigationMode } from '../components/navigation'
import { GroupedNavigation } from '../components/GroupedNavigation'
import { DEFAULT_COPY, DEFAULT_LEGAL, FONT_STACKS, type Theme } from './themes'

export const PREVIEW_PAGES = {login:'Anmeldung',workspace:'Portal',components:'Elemente',imprint:'Impressum',privacy:'Datenschutz'}
export type PreviewPage = keyof typeof PREVIEW_PAGES

export function DesignLivePreview({theme,original,page,onPageChange,fullPage=false,initialMode='admin'}:{theme:Theme;original:Theme;page:PreviewPage;onPageChange:(page:PreviewPage)=>void;fullPage?:boolean;initialMode?:NavigationMode}) {
  const [device,setDevice]=useState<'desktop'|'mobile'>('desktop')
  const [expanded,setExpanded]=useState(false), [comparing,setComparing]=useState(false)
  const [demoForm,setDemoForm]=useState(false), [toast,setToast]=useState('')
  const [mode,setMode]=useState<NavigationMode>(initialMode), [menuOpen,setMenuOpen]=useState(false)
  const [selectedPath,setSelectedPath]=useState<string>(`/${initialMode}`)
  const dialog=useRef<HTMLDialogElement>(null)
  const surface=useRef<HTMLDivElement>(null)
  const uid=useId()
  useEffect(()=>{setComparing(false)},[theme])
  useEffect(()=>{
    if(expanded)dialog.current?.showModal()
  },[expanded])
  useEffect(()=>{
    if(surface.current)surface.current.scrollTop=0
  },[page,device,expanded])
  useEffect(()=>{setDemoForm(false);setToast('')},[page])
  useEffect(()=>{setMenuOpen(false)},[page,device])
  useEffect(()=>{
    if(!toast)return
    const timeout=window.setTimeout(()=>setToast(''),3000)
    return ()=>window.clearTimeout(timeout)
  },[toast])
  const current=comparing?original:theme
  const copy={...DEFAULT_COPY,...current.copy}, legal={...DEFAULT_LEGAL,...current.legal}
  const style={...Object.fromEntries(Object.entries(current.colors).map(([key,value])=>[`--${key}`,value])),
    '--font-family':FONT_STACKS[current.font],'--radius':`${current.radius}px`,colorScheme:current.mode} as CSSProperties
  const brand=<div className="preview-brand">
    <ThemeLogo theme={current} size={22} className="preview-brand-symbol" preview/>
    <div><strong>{copy.title}</strong><span>{copy.subtitle}</span></div>
  </div>
  const footer=<footer className="preview-footer"><span>{legal.footer}</span><div>
    {legal.imprint.trim()&&<button type="button" onClick={()=>onPageChange('imprint')}>Impressum</button>}
    {legal.privacy.trim()&&<button type="button" onClick={()=>onPageChange('privacy')}>Datenschutz</button>}
  </div></footer>
  const sampleAction=(label:string)=>setToast(label)
  const context=navigationContext(mode,selectedPath)
  const changeMode=(next:NavigationMode)=>{setMode(next);setSelectedPath(`/${next}`);setMenuOpen(false)}
  const tools=<div className="preview-tools"><button type="button" className="preview-tool" aria-pressed={comparing} onClick={()=>setComparing(!comparing)}>Vergleichen</button>
    <button type="button" className="preview-tool" aria-label={expanded?'Große Vorschau schließen':'Vorschau vergrößern'} onClick={()=>setExpanded(!expanded)}>{expanded?<X size={17}/>:<Maximize2 size={17}/>}</button></div>
  const content=<>
    {!fullPage&&<div className="preview-heading"><div><span className="creator-eyebrow"><i/>LIVE-VORSCHAU</span><strong>{comparing?'Ausgangsdesign':theme.name||'Dein Design'}</strong></div>{tools}</div>}
    <div className="preview-toolbar">
      <div className="preview-tabs" role="tablist" aria-label="Vorschauseite">{Object.entries(PREVIEW_PAGES).map(([id,label],index)=><button key={id} id={`${uid}-${id}`} role="tab" type="button" aria-selected={page===id} aria-controls={`${uid}-panel`} tabIndex={page===id?0:-1} onClick={()=>onPageChange(id as PreviewPage)} onKeyDown={event=>{
        const pages=Object.keys(PREVIEW_PAGES) as PreviewPage[]
        const next=event.key==='ArrowRight'?(index+1)%pages.length:event.key==='ArrowLeft'?(index+pages.length-1)%pages.length:event.key==='Home'?0:event.key==='End'?pages.length-1:-1
        if(next<0)return
        event.preventDefault();onPageChange(pages[next]);document.getElementById(`${uid}-${pages[next]}`)?.focus()
      }}>{label}</button>)}</div>
      <div className="preview-device" role="group" aria-label="Vorschaugröße"><button type="button" className="preview-tool" aria-label="Desktop-Vorschau" aria-pressed={device==='desktop'} onClick={()=>setDevice('desktop')}><Monitor size={17}/></button><button type="button" className="preview-tool" aria-label="Mobil-Vorschau" aria-pressed={device==='mobile'} onClick={()=>setDevice('mobile')}><Smartphone size={17}/></button></div>
      {(page==='workspace'||page==='components')&&<select className="preview-menu-mode" aria-label="Menüvorschau" value={mode} onChange={event=>changeMode(event.target.value as NavigationMode)}><option value="admin">Administration</option><option value="portal">Benutzerportal</option></select>}
      {fullPage&&tools}
    </div>
    <div className={`preview-stage preview-stage-${device}`}>
      <div className="preview-browser"><span/><span/><span/><div>{copy.title} / {PREVIEW_PAGES[page]}</div><ShieldCheck size={12}/></div>
      <div ref={surface} id={`${uid}-panel`} className="preview-surface" style={style} data-theme-mode={current.mode} data-testid="design-live-preview" role="tabpanel" aria-labelledby={`${uid}-${page}`} tabIndex={0} onKeyDown={event=>{if(event.key==='Escape')setMenuOpen(false)}}>
        {page==='login'?<div className={`preview-login ${current.loginBackground?'preview-login-image':''}`} style={current.loginBackground?{backgroundImage:`linear-gradient(var(--overlay), var(--overlay)), url("${current.loginBackground}")`}:undefined}>
          {brand}<div className="preview-login-copy"><h3>{copy.headline}<br/><em>{copy.emphasis}</em></h3><p>{copy.intro}</p></div>
          <div className="preview-panel preview-login-form"><h4>{copy.welcome}</h4><p>{copy.loginHint}</p>
            <label><span>Benutzername oder E-Mail-Adresse</span><input placeholder="name@unternehmen.de" aria-label="Benutzername in der Vorschau" autoComplete="off"/></label>
            <label><span>Passwort</span><input type="password" placeholder="••••••••••••" aria-label="Passwort in der Vorschau" autoComplete="off"/></label>
            <button type="button" className="preview-primary" onClick={()=>onPageChange('workspace')}>Sicher anmelden<ArrowRight size={14}/></button>
          </div>{footer}
        </div>:page==='imprint'||page==='privacy'?<div className="preview-legal"><header>{brand}<button type="button" className="preview-link" onClick={()=>onPageChange('login')}>Zur Anmeldung<ArrowRight size={14}/></button></header>
          <LegalContent page={page} text={legal[page]}/>{footer}
        </div>:<div className={`preview-portal ${menuOpen?'preview-menu-open':''}`}>
          <aside id={`${uid}-menu`} className="preview-sidebar" aria-label="Hauptmenü-Vorschau"><div className="preview-sidebar-brand">{brand}<button type="button" className="preview-menu-close" aria-label="Hauptmenü schließen" onClick={()=>setMenuOpen(false)}><X size={17}/></button></div>
            <span className="preview-mode-label">{mode==='admin'?'ADMINPORTAL':'BENUTZERPORTAL'}</span>
            <GroupedNavigation mode={mode} pathname={selectedPath} renderItem={([to,label,Icon])=><button key={to} type="button" aria-label={label} className={`nav-item${selectedPath===to?' selected':''}`} onClick={()=>{setSelectedPath(to);setMenuOpen(false);sampleAction(`${label} · Vorschau`)}}><Icon size={18}/><span>{label}</span></button>}/>
            <div className="preview-sidebar-bottom"><button type="button" onClick={()=>changeMode(mode==='admin'?'portal':'admin')}>{mode==='admin'?<PanelLeftClose size={18}/>:<ShieldCheck size={18}/>}<span>{mode==='admin'?'Benutzeransicht':'Administration'}</span></button></div>
          </aside>
          {menuOpen&&<button type="button" className="preview-menu-scrim" aria-label="Menühintergrund schließen" onClick={()=>setMenuOpen(false)}/>}
          <div className="preview-application"><header className="preview-topbar"><div><button type="button" className="preview-menu-trigger" aria-label="Hauptmenü öffnen" aria-expanded={menuOpen} aria-controls={`${uid}-menu`} onClick={()=>setMenuOpen(true)}><Menu size={18}/></button><ClipboardList size={16}/><span>{mode==='admin'?'Administration':'Portal'}</span><span className="preview-breadcrumb"><ChevronRight size={12}/>{context.group.label}<ChevronRight size={12}/><span>{context.label}</span></span></div><div className="preview-profile"><span className="preview-avatar">DU</span><div><strong>Dein Name</strong><span>vorschau@portal.local</span></div><ChevronDown size={14}/></div></header>
          <div className="preview-workspace">{page==='workspace'?<>
            <div className="preview-page-title"><div><span className="preview-kicker">DEIN PORTAL</span><h3>Alles im Blick.</h3><p>Ein guter Tag für neue Projekte.</p></div><button type="button" className="preview-primary" onClick={()=>setDemoForm(true)}><Plus size={14}/>Projekt erstellen</button></div>
            <div className="preview-stats"><div className="preview-panel"><span>Aktive Projekte</span><strong>12</strong><small className="preview-success">+2 diese Woche</small></div><div className="preview-panel"><span>Tasks ausgeführt</span><strong>148</strong><small>In diesem Monat</small></div></div>
            <div className="preview-panel preview-projects"><div><h4>Deine Projekte</h4><Search size={15}/></div>{['Kundenportal','Entwicklungsumgebung','Website'].map((name,index)=><div className="preview-project" key={name}><span className="preview-project-icon"><Folder size={16}/></span><div><strong>{name}</strong><small>Zuletzt vor {index+1} Stunden aktualisiert</small></div><span className={`preview-status ${index===1?'warning':'success'}`}>{index===1?'In Arbeit':'Bereit'}</span></div>)}</div>
            <div className="preview-tip"><ShieldCheck size={17}/><div><strong>Dein Arbeitsbereich ist bereit.</strong><p>Farben, Texte und Logo passen sich deinem Design an.</p></div></div>
          </>:<>
            <div className="preview-page-title"><div><span className="preview-kicker">DESIGN IM DETAIL</span><h3>Wie fühlt es sich an?</h3><p>Fokus, Hover und Zustände direkt ausprobieren.</p></div></div>
            <div className="preview-panel preview-elements"><h4>Aktionen</h4><div className="preview-button-row"><button type="button" className="preview-primary" onClick={()=>sampleAction('Aktion erfolgreich ausgeführt.')}><Play size={14}/>Task starten</button><button type="button" className="preview-secondary" onClick={()=>sampleAction('Auswahl gespeichert.')}><Check size={14}/>Speichern</button><button type="button" className="preview-danger" onClick={()=>sampleAction('Dies ist nur eine Vorschau. Es wird nichts gelöscht.')}>Entfernen</button><button type="button" className="preview-secondary" disabled>Deaktiviert</button></div>
              <label><span>Projektname</span><input placeholder="Mein neues Projekt" aria-label="Projektname in der Elementvorschau"/></label>
              <label className="preview-checkbox"><input type="checkbox" defaultChecked/>Benachrichtigungen aktivieren</label>
              <div className="preview-button-row"><span className="preview-status success">Erfolgreich</span><span className="preview-status warning">Wartet</span><span className="preview-status danger">Fehlgeschlagen</span></div>
            </div>
            <div className="preview-alert success"><CheckCircle2 size={16}/><span>Alle Änderungen wurden gespeichert.</span></div><div className="preview-alert warning"><CircleAlert size={16}/><span>Bitte prüfe die Angaben vor dem Start.</span></div><div className="preview-alert danger"><CircleAlert size={16}/><span>Ein Pflichtfeld ist noch nicht ausgefüllt.</span></div>
          </>}{footer}</div></div>
        </div>}
        {demoForm&&page==='workspace'&&<div className="preview-demo-overlay"><div className="preview-panel preview-demo-dialog" role="group" aria-label="Beispielprojekt erstellen"><div><h4>Neues Projekt</h4><button type="button" className="preview-icon-button" aria-label="Beispielprojekt schließen" onClick={()=>setDemoForm(false)}><X size={16}/></button></div><p>So sehen Dialoge in deinem Design aus.</p><label><span>Projektname</span><input placeholder="Mein Projekt" aria-label="Name des Beispielprojekts"/></label><button type="button" className="preview-primary" onClick={()=>{setDemoForm(false);sampleAction('Beispielprojekt erstellt.')}}>Projekt erstellen</button></div></div>}
        {toast&&<div className="preview-toast" role="status"><CheckCircle2 size={16}/>{toast}</div>}
      </div>
    </div>
    <p className="preview-caption">{device==='mobile'?'Kompakte Mobilansicht':'Flexible Desktopansicht'} · Änderungen erscheinen sofort. Vorschauaktionen verwenden Beispieldaten.</p>
  </>
  return expanded?<dialog className="preview-fullscreen" ref={dialog} aria-label="Große Design-Vorschau" onCancel={()=>setExpanded(false)} onClose={()=>setExpanded(false)}>{content}</dialog>
    :<section className={`creator-preview ${fullPage?'creator-preview-page':''}`} aria-label="Live-Vorschau">{content}</section>
}
