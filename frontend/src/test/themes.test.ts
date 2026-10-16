import { describe, expect, it } from 'vitest'
import { BUILTIN_THEMES, contrast, exportThemeFile, parseThemeFile, resolveCustomTheme } from '../designs/themes'
import example from '../../public/themes/example.theme.json'

describe('Design-Dateien',()=>{
  it.each(BUILTIN_THEMES)('exportiert und importiert $name ohne Farbverlust',theme=>{
    const imported=resolveCustomTheme(parseThemeFile(JSON.parse(JSON.stringify(exportThemeFile(theme)))))
    expect(imported.colors).toEqual(theme.colors)
    expect(imported.font).toBe(theme.font)
    expect(imported.branding).toBe(theme.branding)
    expect(contrast(theme.colors.text,theme.colors.surface)).toBeGreaterThanOrEqual(4.5)
    expect(contrast(theme.colors['on-primary'],theme.colors.primary)).toBeGreaterThanOrEqual(4.5)
  })
  it('akzeptiert die mitgelieferte firmenneutrale Vorlage',()=>{
    const theme=resolveCustomTheme(parseThemeFile(example))
    expect(theme.id).toBe('custom:meine-firma')
    expect(theme.colors.bg).toBe(BUILTIN_THEMES[0].colors.bg)
    expect(theme.colors.primary).toBe('#b6a4ff')
  })
  it('übernimmt die SIT-Bildmarke nur bei ausdrücklicher Auswahl in eigenen Designs',()=>{
    const definition={...example,base:'sit-light'}
    expect(resolveCustomTheme(parseThemeFile(definition)).branding).toBe('neutral')
    expect(resolveCustomTheme(parseThemeFile({...definition,branding:'sit'})).branding).toBe('sit')
  })
  it.each([
    {schema_version:2}, {base:'unknown'}, {font:'url(https://example.com/font)'},
    {css:'body {display:none}'}, {colors:{background:'red'}}, {colors:{bg:'url(https://example.com)'}},
    {colors:{text:'#0d1117'}}, {radius:100}, {font:['sora']}, {branding:'external-logo'},
  ])('weist ungültige oder unlesbare Designs zurück: %j',override=>{
    expect(()=>parseThemeFile({...example,...override})).toThrow()
  })
})
