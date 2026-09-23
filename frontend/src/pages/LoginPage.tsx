import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { KeyRound, LockKeyhole, Mail, ShieldCheck } from 'lucide-react'
import { z } from 'zod'
import { useAuth } from '../auth'
import { ApiError } from '../api'
import { Button, Notice } from '../components/ui'

const schema = z.object({ email: z.string().email('Bitte eine gültige E-Mail-Adresse eingeben.'), password: z.string().min(1, 'Passwort fehlt.') })
type FormData = z.infer<typeof schema>

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({ resolver: zodResolver(schema) })
  const submit = async (values: FormData) => {
    setError('')
    try {
      const user = await login(values.email, values.password)
      navigate(user.roles.includes('system_admin') ? '/admin' : '/portal', { replace: true })
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : 'Anmeldung nicht möglich.') }
  }
  return <div className="login-page"><div className="login-ambient login-ambient-a"/><div className="login-ambient login-ambient-b"/>
    <section className="login-intro"><div className="brand brand-large"><div className="brand-mark"><KeyRound size={26}/></div><div><strong>Semaphore</strong><span>Tenant Portal</span></div></div><div className="login-copy"><span className="eyebrow">KONTROLLIERTE AUTOMATISIERUNG</span><h1>Deployments starten.<br/><em>Sicher getrennt.</em></h1><p>Eine zentrale Oberfläche für Mandanten, Anwendungen und freigegebene Semaphore-Tasks.</p><div className="security-points"><span><ShieldCheck/>Serverseitige Task Policies</span><span><LockKeyhole/>Keine API-Tokens im Browser</span></div></div></section>
    <section className="login-panel"><form className="login-card" onSubmit={handleSubmit(submit)}><div><h2>Willkommen zurück</h2><p>Melden Sie sich mit Ihrem lokalen Portalkonto an.</p></div>{error && <Notice type="error">{error}</Notice>}
      <label className="field"><span className="field-label">E-Mail-Adresse</span><div className="input-icon"><Mail size={17}/><input autoComplete="username" autoFocus {...register('email')} placeholder="name@unternehmen.de"/></div>{errors.email && <span className="field-error">{errors.email.message}</span>}</label>
      <label className="field"><span className="field-label">Passwort</span><div className="input-icon"><LockKeyhole size={17}/><input type="password" autoComplete="current-password" {...register('password')}/></div>{errors.password && <span className="field-error">{errors.password.message}</span>}</label>
      <Button type="submit" loading={isSubmitting}>Sicher anmelden</Button><p className="login-note">Bei wiederholten Fehlversuchen wird die Anmeldung vorübergehend begrenzt.</p>
    </form></section>
  </div>
}

