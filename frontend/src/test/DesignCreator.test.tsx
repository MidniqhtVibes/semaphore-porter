import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { within } from '@testing-library/react'
import { DesignCreator, createDraft } from '../designs/DesignCreator'
import { ANIMATED_GIF } from './fixtures/images'
import { BUILTIN_THEMES, parseThemeFile, resolveCustomTheme } from '../designs/themes'

describe('Design-Creator',()=>{
  it('zeigt dieselben Menügruppen und wechselt zur Benutzeransicht',()=>{
    render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={vi.fn()} onClose={()=>{}}/>)
    const menu=within(screen.getByRole('navigation',{name:'Hauptmenü'}))
    expect(menu.getByRole('button',{name:'Arbeitsbereich'})).toHaveAttribute('aria-expanded','true')
    expect(menu.getByRole('button',{name:'Zugriff'})).toHaveAttribute('aria-expanded','false')
    fireEvent.click(menu.getByRole('button',{name:'Zugriff'}))
    expect(menu.getByRole('button',{name:'Benutzer & Gruppen'})).toBeVisible()
    expect(menu.getByRole('button',{name:'Audit-Log'})).toBeVisible()
    fireEvent.click(menu.getByRole('button',{name:'Berechtigungen'}))
    expect(menu.getByRole('button',{name:'Berechtigungen'})).toHaveClass('selected')
    fireEvent.change(screen.getByLabelText('Menüvorschau'),{target:{value:'portal'}})
    expect(menu.getByRole('button',{name:'Meine Projekte'})).toBeVisible()
    expect(menu.getByRole('button',{name:'Mein Konto'})).toBeVisible()
    expect(menu.getByRole('button',{name:'Persönlich'})).toHaveAttribute('aria-expanded','true')
    expect(menu.queryByRole('button',{name:'Benutzer & Gruppen'})).not.toBeInTheDocument()
  })
  it('bietet nur Farbwähler und steuert Transparenz ohne Hex-Eingaben',()=>{
    render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={vi.fn()} onClose={()=>{}}/>)
    expect(screen.queryByLabelText(/Hex/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Seitenhintergrund wählen')).toHaveAttribute('type','color')
    fireEvent.click(screen.getByText('Weitere Farben und Zustände'))
    fireEvent.change(screen.getByLabelText('Akzentfläche Deckkraft'),{target:{value:'40'}})
    expect(screen.getByTestId('design-live-preview').style.getPropertyValue('--accent-soft')).toBe('#8bb9ff66')
  })
  it('zeigt Farben und rechtliche Texte sofort in der passenden Vorschau',()=>{
    const save=vi.fn()
    render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={save} onClose={()=>{}}/>)
    fireEvent.change(screen.getByLabelText('Seitenhintergrund w\u00e4hlen'),{target:{value:'#101820'}})
    expect(screen.getByTestId('design-live-preview').style.getPropertyValue('--bg')).toBe('#101820')
    fireEvent.click(screen.getByRole('button',{name:'Texte & Bilder'}))
    fireEvent.change(screen.getByLabelText('Impressum'),{target:{value:'Meine Firma\nMusterstraße 12\n\nKontakt: team@firma.test'}})
    expect(screen.getByRole('tab',{name:'Impressum'})).toHaveAttribute('aria-selected','true')
    expect(within(screen.getByTestId('design-live-preview')).getByText(/Musterstraße 12/)).toBeVisible()
    fireEvent.change(screen.getByLabelText('Datenschutz'),{target:{value:'Informationen zur Verarbeitung von Daten.'}})
    expect(screen.getByRole('tab',{name:'Datenschutz'})).toHaveAttribute('aria-selected','true')
    expect(within(screen.getByTestId('design-live-preview')).getByText('Informationen zur Verarbeitung von Daten.')).toBeVisible()
    expect(save).not.toHaveBeenCalled()
  })
  it('wechselt zwischen Geräten, Portal und Zuständen und vergleicht mit dem Ausgangsdesign',()=>{
    render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={vi.fn()} onClose={()=>{}}/>)
    fireEvent.click(screen.getByRole('tab',{name:'Portal'}))
    expect(within(screen.getByTestId('design-live-preview')).getByText('Kundenportal')).toBeVisible()
    fireEvent.click(screen.getByRole('button',{name:'Mobil-Vorschau'}))
    expect(screen.getByRole('button',{name:'Mobil-Vorschau'})).toHaveAttribute('aria-pressed','true')
    fireEvent.click(screen.getByRole('button',{name:'Texte & Bilder'}))
    fireEvent.change(screen.getByLabelText('Portalname'),{target:{value:'Neues Portal'}})
    expect(within(screen.getByTestId('design-live-preview')).getByText('Neues Portal')).toBeVisible()
    fireEvent.click(screen.getByRole('button',{name:'Vergleichen'}))
    expect(within(screen.getByTestId('design-live-preview')).getByText('Semaporter',{selector:'strong'})).toBeVisible()
    fireEvent.click(screen.getByRole('button',{name:'Vergleichen'}))
    expect(within(screen.getByTestId('design-live-preview')).getByText('Neues Portal')).toBeVisible()
    fireEvent.click(screen.getByRole('tab',{name:'Elemente'}))
    fireEvent.click(screen.getByRole('button',{name:'Task starten'}))
    expect(screen.getByRole('status')).toHaveTextContent('Aktion erfolgreich ausgeführt.')
  })
  it('übernimmt ein hochgeladenes Bild sofort in die Vorschau',async()=>{
    const imageMock=vi.spyOn(globalThis,'Image').mockImplementation(function(){
      const image=document.createElement('img')
      Object.defineProperty(image,'src',{set(){queueMicrotask(()=>image.onload?.(new Event('load')))}})
      return image
    })
    try{
      const save=vi.fn()
      render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={save} onClose={()=>{}}/>)
      fireEvent.click(screen.getByRole('button',{name:'Texte & Bilder'}))
      const file=new File(['image-bytes'],'firma.png',{type:'image/png'})
      fireEvent.change(screen.getByLabelText('Eigenes Logo'),{target:{files:[file]}})
      expect(await screen.findByRole('img',{name:'Logo-Vorschau'})).toHaveAttribute('src','data:image/png;base64,aW1hZ2UtYnl0ZXM=')
      fireEvent.change(screen.getByLabelText('Hintergrundbild der Anmeldung'),{target:{files:[file]}})
      await screen.findByRole('button',{name:'Hintergrundbild entfernen'})
      expect(screen.getByTestId('design-live-preview').querySelector('.login-background')?.getAttribute('style')).toContain('data:image/png;base64,')
      expect(save).not.toHaveBeenCalled()
    }finally{imageMock.mockRestore()}
  })
  it('lädt animierte GIFs für Logo und Hintergrund und speichert Unschärfe getrennt vom Formular',async()=>{
    const imageMock=vi.spyOn(globalThis,'Image').mockImplementation(function(){
      const image=document.createElement('img')
      Object.defineProperty(image,'src',{set(){queueMicrotask(()=>image.onload?.(new Event('load')))}})
      return image
    })
    try{
      const save=vi.fn()
      render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={save} onClose={()=>{}}/>)
      fireEvent.click(screen.getByRole('button',{name:'Texte & Bilder'}))
      const bytes=Uint8Array.from(atob(ANIMATED_GIF.split(',')[1]),char=>char.charCodeAt(0))
      const file=new File([bytes],'animiert.gif',{type:'image/gif'})
      expect(screen.getByLabelText('Eigenes Logo')).toHaveAttribute('accept',expect.stringContaining('image/gif'))
      fireEvent.change(screen.getByLabelText('Eigenes Logo'),{target:{files:[file]}})
      expect(await screen.findByRole('img',{name:'Logo-Vorschau'})).toHaveAttribute('src',ANIMATED_GIF)
      fireEvent.change(screen.getByLabelText('Hintergrundbild der Anmeldung'),{target:{files:[file]}})
      await screen.findByRole('button',{name:'Hintergrundbild entfernen'})
      fireEvent.change(screen.getByRole('slider',{name:'Hintergrund-Unschärfe'}),{target:{value:'12'}})
      const preview=screen.getByTestId('design-live-preview')
      expect(preview.querySelector('.login-background')).toHaveStyle({filter:'blur(12px)'})
      expect(preview.querySelector('.login-background')?.getAttribute('style')).toContain(ANIMATED_GIF)
      expect(preview.querySelector<HTMLElement>('.preview-login')?.style.filter).toBe('')
      fireEvent.click(screen.getByRole('button',{name:'Speichern und aktivieren'}))
      expect(save).toHaveBeenCalledWith(expect.objectContaining({logo:ANIMATED_GIF,loginBackground:ANIMATED_GIF,loginBackgroundBlur:12}))
    }finally{imageMock.mockRestore()}
  })
  it('speichert eigene Texte und Farben erst nach ausdrücklichem Speichern',()=>{
    const save=vi.fn(), draft=createDraft(BUILTIN_THEMES[0])
    render(<DesignCreator initial={draft} onSave={save} onClose={()=>{}}/>)
    fireEvent.change(screen.getByLabelText('Design-Name'),{target:{value:'Meine Firma'}})
    fireEvent.change(screen.getByLabelText('Portalname'),{target:{value:'Firmenportal'}})
    fireEvent.change(screen.getByLabelText('Links und Fokus w\u00e4hlen'),{target:{value:'#b6a4ff'}})
    expect(screen.getByText('Firmenportal')).toBeInTheDocument()
    expect(save).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button',{name:'Speichern und aktivieren'}))
    expect(save).toHaveBeenCalledWith(expect.objectContaining({name:'Meine Firma',copy:{title:'Firmenportal'},colors:expect.objectContaining({accent:'#b6a4ff'})}))
  })
  it('verhindert das Speichern unlesbarer Farben',()=>{
    render(<DesignCreator initial={createDraft(BUILTIN_THEMES[0])} onSave={vi.fn()} onClose={()=>{}}/>)
    fireEvent.change(screen.getByLabelText('Haupttext w\u00e4hlen'),{target:{value:'#1b2028'}})
    expect(screen.getByRole('button',{name:'Speichern und aktivieren'})).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Kontrast')
    fireEvent.click(screen.getByRole('button',{name:'Änderungen zurücksetzen'}))
    expect(screen.getByRole('button',{name:'Speichern und aktivieren'})).toBeEnabled()
  })
  it('erhält Logo und Texte beim Exportformat und lehnt externe oder aktive Bilder ab',()=>{
    const draft={...createDraft(BUILTIN_THEMES[0]),copy:{title:'Firma'},logo:'data:image/png;base64,aGVsbG8='}
    expect(resolveCustomTheme(parseThemeFile(draft))).toMatchObject({copy:{title:'Firma'},logo:draft.logo})
    for(const logo of ['https://example.com/logo.png','data:image/svg+xml;base64,PHN2Zz4='])expect(()=>parseThemeFile({...draft,logo})).toThrow('Logo')
    expect(()=>parseThemeFile({...draft,copy:{unknown:'Text'}})).toThrow('Text')
    const extended={...draft,loginBackground:draft.logo,logoWidth:80,legal:{footer:'Meine Firma',imprint:'Meine Firma\nKontakt',privacy:'Datenschutzhinweise'}}
    expect(resolveCustomTheme(parseThemeFile(JSON.parse(JSON.stringify(extended))))).toMatchObject({loginBackground:draft.logo,logoWidth:80,legal:extended.legal})
    expect(()=>parseThemeFile({...extended,legal:{imprint:'a'.repeat(12001)}})).toThrow('Rechtstext')
    expect(()=>parseThemeFile({...extended,loginBackground:'https://example.com/bild.jpg'})).toThrow('Hintergrundbild')
    expect(()=>parseThemeFile({...extended,logoWidth:121})).toThrow('Logobreite')
  })
})
