export type ContainerAction='start'|'stop'|'restart'|'pause'|'resume'|'remove'
export const actionNames:Record<ContainerAction,string>={start:'Starten',stop:'Stoppen',restart:'Neu starten',pause:'Pausieren',resume:'Fortsetzen',remove:'Entfernen'}
export type AgentConnection={id:string;name:string;base_url:string;token_present:boolean;ca_pem:string;client_cert_pem?:string;client_key_present?:boolean;active:boolean;projects:string[];use_agent_scope:boolean;write_enabled:boolean;allowed_actions:ContainerAction[]}
export type ContainerConfig={enabled:boolean;revision:string;agents:AgentConnection[]}
export type ManagedContainer={id:string;name:string;image:string;image_id:string;stack:string;state:string;status:string;ports:Array<{IP?:string;PrivatePort:number;PublicPort?:number;Type:string}>;networks:string[];volumes:string[];protected:boolean;actions:ContainerAction[]}
export type ContainerDetail=ManagedContainer&{details:{started_at:string;finished_at:string;exit_code:number;restart_count:number;restart_policy:string;environment_names:string[]}}
export type ContainerInventory={containers:ManagedContainer[];stacks:string[];images:string[];volumes:string[];networks:string[]}
export type ContainerStats={running:boolean;cpu_percent:number|null;memory_bytes:number|null;memory_limit:number|null;network_rx:number|null;network_tx:number|null;block_read:number|null;block_write:number|null}
export type ContainerOperation={id:string;agent_id:string;agent_name:string;container_id:string;container_name:string;action:ContainerAction;status:string;message:string;created_at:string;requires_review:boolean}
export const containerBase='/admin/containers'
export const agentPath=(id:string)=>`${containerBase}/agents/${encodeURIComponent(id)}`
export const containerPath=(agent:string,id:string)=>`${agentPath(agent)}/containers/${encodeURIComponent(id)}`
export const stateNames:Record<string,string>={running:'Läuft',exited:'Gestoppt',created:'Erstellt',paused:'Pausiert',restarting:'Startet neu',removing:'Wird entfernt',dead:'Fehler',unknown:'Unbekannt'}
export function byteSize(value:number|null|undefined){
  if(value==null)return 'Nicht verfügbar'
  const units=['B','KiB','MiB','GiB','TiB'];let amount=value,index=0
  while(amount>=1024&&index<units.length-1){amount/=1024;index++}
  return `${amount.toLocaleString('de-DE',{maximumFractionDigits:1})} ${units[index]}`
}
