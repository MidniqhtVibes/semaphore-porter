import { Component, lazy, Suspense, type ErrorInfo, type ReactNode } from 'react'
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { Layout } from './components/Layout'
import { Loading, Notice } from './components/ui'
import { LoginPage } from './pages/LoginPage'
import { AdminDashboardPage } from './pages/admin/DashboardPage'
import { ApplicationsPage, PresetsPage, ProjectTemplatesPage } from './pages/admin/CatalogPages'
import { AuditPage, AdminTasksPage, PermissionsPage } from './pages/admin/OpsPages'
import { SemaphorePage } from './pages/admin/SemaphorePage'
import { VaultPage } from './pages/admin/VaultPage'
const CredentialsPage=lazy(()=>import('./pages/admin/CredentialsPage').then(module=>({default:module.CredentialsPage})))
const GitLabPage=lazy(()=>import('./pages/admin/GitLabPage').then(module=>({default:module.GitLabPage})))
const ProgramPackagesPage=lazy(()=>import('./pages/admin/ProgramPackagesPage').then(module=>({default:module.ProgramPackagesPage})))
const ProgramPackagePage=lazy(()=>import('./pages/admin/ProgramPackagePage').then(module=>({default:module.ProgramPackagePage})))
const GitLabChangesPage=lazy(()=>import('./pages/admin/GitLabChangesPage').then(module=>({default:module.GitLabChangesPage})))
const GitLabReleasesPage=lazy(()=>import('./pages/admin/GitLabReleasesPage').then(module=>({default:module.GitLabReleasesPage})))
import { TenantDetailPage, TenantsPage } from './pages/admin/TenantsPage'
import { TenantWizardPage } from './pages/admin/TenantWizardPage'
import { ProjectsPage, ProjectEditorPage } from './pages/admin/ProjectsPage'
import { UsersPage } from './pages/admin/UsersPage'
import { DesignsPage } from './pages/DesignsPage'
import { LegalPage } from './pages/LegalPage'
const DesignStudioPage=lazy(()=>import('./pages/DesignStudioPage'))
const DoomPage=__PORTAL_ARCADE__?lazy(()=>import('./pages/DoomPage')):null
import {
  AccountPage, MyProjectsPage, PortalDashboardPage, ProjectDetailPage, RunDetailPage,
  RunsPage, TaskStartPage,
} from './pages/portal/PortalPages'

class ErrorBoundary extends Component<{children:ReactNode},{error:string}> {
  state={error:''}
  static getDerivedStateFromError(error:Error){return{error:error.message||'Unbekannter Anwendungsfehler'}}
  componentDidCatch(error:Error,info:ErrorInfo){console.error(error,info)}
  render(){return this.state.error?<div className="fatal"><Notice type="error"><strong>Die Ansicht konnte nicht geladen werden.</strong><br/>{this.state.error}</Notice><button className="button button-secondary" onClick={()=>window.location.reload()}>Neu laden</button></div>:this.props.children}
}

function Protected({admin=false}:{admin?:boolean}){
  const {user,loading,isAdmin}=useAuth(),location=useLocation()
  if(loading)return <div className="app-loading"><Loading label="Portal wird geladen …"/></div>
  if(!user)return <Navigate to="/login" replace state={{from:location}}/>
  if(admin&&!isAdmin)return <Navigate to="/portal" replace/>
  if(user.must_change_password&&location.pathname!=='/portal/konto')return <Navigate to="/portal/konto" replace/>
  return <Outlet/>
}
function AdminShell(){return <Layout mode="admin"><ErrorBoundary><Outlet/></ErrorBoundary></Layout>}
function PortalShell(){return <Layout mode="portal"><ErrorBoundary><Outlet/></ErrorBoundary></Layout>}
function LoginRoute(){const {user,loading,isAdmin}=useAuth();if(loading)return <div className="app-loading"><Loading/></div>;return user?<Navigate to={isAdmin?'/admin':'/portal'} replace/>:<LoginPage/>}
function StudioRoute(){return <ErrorBoundary><Suspense fallback={<div className="app-loading"><Loading label="Designstudio wird geladen …"/></div>}><DesignStudioPage/></Suspense></ErrorBoundary>}
function DeferredPage({children}:{children:ReactNode}){return <Suspense fallback={<Loading/>}>{children}</Suspense>}

export function App(){return <Routes>
  <Route path="/impressum" element={<LegalPage page="imprint"/>}/>
  <Route path="/datenschutz" element={<LegalPage page="privacy"/>}/>
  <Route path="/login" element={<LoginRoute/>}/>
  <Route element={<Protected admin/>}>
    <Route path="/admin/designs/studio" element={<StudioRoute/>}/>
    <Route path="/admin" element={<AdminShell/>}>
    <Route path="vault" element={<VaultPage/>}/>
    <Route path="zugangsprofile" element={<DeferredPage><CredentialsPage/></DeferredPage>}/>
    <Route path="gitlab" element={<DeferredPage><GitLabPage/></DeferredPage>}/>
    <Route path="programmpakete" element={<DeferredPage><ProgramPackagesPage/></DeferredPage>}/>
    <Route path="programmpakete/:draftId" element={<DeferredPage><ProgramPackagePage/></DeferredPage>}/>
    <Route path="freigaben" element={<DeferredPage><GitLabChangesPage/></DeferredPage>}/>
    <Route path="pruefungen" element={<DeferredPage><GitLabChangesPage pipelinesOnly/></DeferredPage>}/>
    <Route path="uebernahme" element={<DeferredPage><GitLabReleasesPage/></DeferredPage>}/>
    <Route path="designs" element={<DesignsPage/>}/>
    <Route path="projekte" element={<ProjectsPage/>}/><Route path="projekte/:projectId" element={<ProjectEditorPage/>}/>
    <Route index element={<AdminDashboardPage/>}/><Route path="tenants" element={<TenantsPage/>}/><Route path="tenants/:tenantId" element={<TenantDetailPage/>}/><Route path="tenant-erstellen" element={<TenantWizardPage/>}/><Route path="anwendungen" element={<ApplicationsPage/>}/><Route path="vorlagen" element={<ProjectTemplatesPage/>}/><Route path="presets" element={<PresetsPage/>}/><Route path="benutzer" element={<UsersPage/>}/><Route path="berechtigungen" element={<PermissionsPage/>}/><Route path="tasks" element={<AdminTasksPage/>}/><Route path="audit" element={<AuditPage/>}/><Route path="semaphore" element={<SemaphorePage/>}/>
  </Route></Route>
  <Route element={<Protected/>}>
    {DoomPage&&<Route path="/portal/iddqd" element={<ErrorBoundary><Suspense fallback={<div className="app-loading"><Loading/></div>}><DoomPage/></Suspense></ErrorBoundary>}/>}
    <Route path="/portal/designs/studio" element={<StudioRoute/>}/>
    <Route path="/portal" element={<PortalShell/>}>
    <Route path="designs" element={<DesignsPage/>}/>
    <Route index element={<PortalDashboardPage/>}/><Route path="projekte" element={<MyProjectsPage/>}/><Route path="projekte/:tenantId" element={<ProjectDetailPage/>}/><Route path="projekte/:tenantId/tasks/:taskId" element={<TaskStartPage/>}/><Route path="laufende-tasks" element={<RunsPage runningOnly/>}/><Route path="historie" element={<RunsPage/>}/><Route path="runs/:runId" element={<RunDetailPage/>}/><Route path="konto" element={<AccountPage/>}/>
  </Route></Route>
  <Route path="*" element={<Navigate to="/portal" replace/>}/>
  </Routes>}

