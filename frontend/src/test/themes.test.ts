import { describe, expect, it } from 'vitest'
import { BUILTIN_THEMES, contrast, createDraft, exportThemeFile, MAX_THEME_IMAGE_BYTES, parseThemeFile, resolveCustomTheme } from '../designs/themes'
import example from '../../public/themes/example.theme.json'
import { ANIMATED_GIF } from './fixtures/images'

describe('Design-Dateien',()=>{
  it('erhält beide GIF-Bilder und die Unschärfe beim Export, Import und Kopieren',()=>{
    const definition=parseThemeFile({...example,logo:ANIMATED_GIF,loginBackground:ANIMATED_GIF,loginBackgroundBlur:12})
    const theme=resolveCustomTheme(definition)
    const imported=parseThemeFile(JSON.parse(JSON.stringify(exportThemeFile(theme))))
    expect(imported).toMatchObject({logo:ANIMATED_GIF,loginBackground:ANIMATED_GIF,loginBackgroundBlur:12})
    expect(createDraft(resolveCustomTheme(imported))).toMatchObject({logo:ANIMATED_GIF,loginBackground:ANIMATED_GIF,loginBackgroundBlur:12})
  })
  it('validiert die Unschärfe und behält die Bildgrößengrenze auch für GIFs',()=>{
    for(const loginBackgroundBlur of [-1,25,0.5,'12',null])expect(()=>parseThemeFile({...example,loginBackgroundBlur})).toThrow('Unschärfe')
    for(const loginBackgroundBlur of [0,24])expect(parseThemeFile({...example,loginBackgroundBlur}).loginBackgroundBlur).toBe(loginBackgroundBlur)
    const oversized='data:image/gif;base64,'+btoa('x'.repeat(MAX_THEME_IMAGE_BYTES+1))
    for(const field of ['logo','loginBackground'])expect(()=>parseThemeFile({...example,[field]:oversized})).toThrow('250 KB')
    expect(resolveCustomTheme(parseThemeFile(example)).loginBackgroundBlur).toBeUndefined()
  })
  it('aktualisiert alte Produkttexte und behält individuelle Firmenbezeichnungen',()=>{
    const legacy=parseThemeFile({...example,copy:{title:'Semaphore',subtitle:'Meine Firma'},legal:{footer:'Tenant Portal',imprint:'Louis Findeisen'}})
    expect(legacy.copy).toEqual({title:'Semaporter',subtitle:'Meine Firma'})
    expect(legacy.legal).toEqual({footer:'Semaporter',imprint:'Louis Findeisen'})
    const custom=parseThemeFile({...example,copy:{title:'Mein Firmenportal'},legal:{footer:'Meine Firma'}})
    expect(custom.copy?.title).toBe('Mein Firmenportal')
    expect(custom.legal?.footer).toBe('Meine Firma')
  })
  it.each(BUILTIN_THEMES)('exportiert und importiert $name ohne Farbverlust',theme=>{
    const imported=resolveCustomTheme(parseThemeFile(JSON.parse(JSON.stringify(exportThemeFile(theme)))))
    expect(imported.colors).toEqual(theme.colors)
    expect(imported.font).toBe(theme.font)
    expect(imported.logoAsset).toBe(theme.logoAsset)
    expect(imported.logoTone).toBe(theme.logoTone)
    expect(contrast(theme.colors.text,theme.colors.surface)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(theme.colors['on-primary'],theme.colors.primary)).toBeGreaterThanOrEqual(4.5)
  })
  it('akzeptiert die mitgelieferte firmenneutrale Vorlage',()=>{
    const theme=resolveCustomTheme(parseThemeFile(example))
    expect(theme.id).toBe('custom:meine-firma')
    expect(theme.colors.bg).toBe(BUILTIN_THEMES[0].colors.bg)
    expect(theme.colors.primary).toBe('#b6a4ff')
  })
  it('normalisiert ältere Markenangaben und behandelt Bilder über allgemeine Logofelder',()=>{
    const legacy=parseThemeFile({...example,base:'sit-light',branding:'sit'})
    expect(legacy.branding).toBeUndefined()
    expect(legacy.logoAsset).toBe('sit-logo')
    expect(legacy.logoTone).toBe('dark')
    const own=parseThemeFile({...example,logo:'data:image/png;base64,aGVsbG8=',logoTone:'dark'})
    expect(resolveCustomTheme(own).logoTone).toBe('dark')
    expect(()=>parseThemeFile({...example,logoTone:['dark']})).toThrow()
  })
  it('übernimmt die SIT-Bildmarke nur bei ausdrücklicher Auswahl in eigenen Designs',()=>{
    const definition={...example,base:'sit-light'}
    expect(resolveCustomTheme(parseThemeFile(definition)).logoAsset).toBeUndefined()
    expect(resolveCustomTheme(parseThemeFile({...definition,branding:'sit'})).logoAsset).toBe('sit-logo')
  })
  it.each([
    {schema_version:2}, {base:'unknown'}, {font:'url(https://example.com/font)'},
    {css:'body {display:none}'}, {colors:{background:'red'}}, {colors:{bg:'url(https://example.com)'}},
    {colors:{text:'#0d1117'}}, {radius:100}, {font:['sora']}, {branding:'external-logo'},
  ])('weist ungültige oder unlesbare Designs zurück: %j',override=>{
    expect(()=>parseThemeFile({...example,...override})).toThrow()
  })
})
