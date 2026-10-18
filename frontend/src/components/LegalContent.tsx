export type LegalPageId = 'imprint' | 'privacy'

export const LEGAL_TITLES = {imprint:'Impressum',privacy:'Datenschutz'}

export function LegalContent({page,text,heading='h2'}:{page:LegalPageId;text:string;heading?:'h1'|'h2'}) {
  const Heading=heading
  return <article className="legal-content">
    <Heading>{LEGAL_TITLES[page]}</Heading>
    {text.trim()
      ? text.split(/\n\s*\n/).map((paragraph,index)=><p key={index}>{paragraph}</p>)
      : <p className="legal-placeholder">Hier erscheint dein Text für {page==='imprint'?'das Impressum':'den Datenschutz'}. Trage ihn links im Editor ein.</p>}
  </article>
}
