export type User = {
  id: string
  email: string
  username?: string | null
  display_name: string
  color?: 'slate'|'blue'|'violet'|'green'|'amber'|'rose'
  tags?: string[]
  profile_color?: 'slate'|'blue'|'violet'|'green'|'amber'|'rose'
  avatar_version?: string|null
  position?: string
  department?: string
  location?: string
  is_active: boolean
  must_change_password: boolean
  roles: string[]
  last_login_at?: string | null
  created_at?: string
}

export type TeamProfile = {
  id:string; name:string; description:string; color:NonNullable<User['color']>
  responsibilities:string[]; responsibility_notes:string; member_count:number
}
export type PersonProfile = {
  id:string; display_name:string; email:string; is_active:boolean; bio:string; skills:string[]
  responsibilities:string[]; responsibility_notes:string; phone:string; profile_color:NonNullable<User['color']>
  position:string; department:string; location:string; primary_team_id:string|null; avatar_version:string|null
  teams:TeamProfile[]; team_responsibilities:string[]
}

export type Tenant = {
  id: string
  tenant_slug: string
  display_name: string
  description: string
  application_id?: string | null
  application_ids?: string[]
  database_types?: string[]
  dataset_ids?: string[]
  status: 'draft' | 'active' | 'inactive' | 'deleted'
  configuration_complete?: boolean
  semaphore_project?: { id: number; name: string; last_verified_at?: string | null; last_error?: string | null } | null
  task_templates?: TaskTemplate[]
  memberships?: Array<Record<string, unknown>>
}

export type TaskTemplate = {
  id: string
  semaphore_template_id?: number
  name: string
  description: string
  app: string
  is_enabled?: boolean
  has_policy?: boolean
  can_start?: boolean
  can_stop?: boolean
  survey_schema?: Array<Record<string, unknown>>
}

export type TaskRun = {
  id: string
  tenant_id: string
  tenant: string
  task_template_id: string
  task_template: string
  started_by: string
  status: string
  semaphore_task_id: number
  started_at: string
  finished_at?: string | null
  duration_seconds?: number | null
  last_synced_at?: string | null
  sync_error?: string | null
  can_stop?: boolean
}

export type ApiErrorBody = { detail?: string | { message?: string; fields?: Record<string, string> } | Array<{loc?:Array<string|number>;msg:string}> }

