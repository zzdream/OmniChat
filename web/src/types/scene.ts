import type { TokenUsage } from '@/types/chat'
import type { RagSource } from '@/types/rag'

export interface SceneVector3 {
  x: number
  y: number
  z: number
}

export interface SceneObjectSnapshot {
  id: string
  name: string
  fileName?: string
  position: SceneVector3
  rotation: SceneVector3
  scale: SceneVector3
}

export type SceneActionType =
  | 'move'
  | 'rotate'
  | 'focus'
  | 'highlight'
  | 'clear_highlight'

export interface SceneActionPayload {
  action: SceneActionType
  object_id?: string
  object_name?: string
  axis?: 'x' | 'y' | 'z'
  distance?: number
  degrees?: number
}

export interface SceneToolStep {
  id: string
  type: 'tool_call' | 'tool_result'
  name: string
  arguments?: string
  result?: string
}

export interface SceneHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface SceneChatRequestPayload {
  message: string
  system?: string
  history?: SceneHistoryMessage[]
  temperature?: number
  model?: string
  knowledge_base_id?: string
  top_k?: number
  scene_objects: SceneObjectSnapshot[]
  selected_object_id?: string | null
}

export interface SceneChatStreamEvent {
  content?: string
  tool_call?: {
    id: string
    name: string
    arguments: string
  }
  tool_result?: {
    id: string
    name: string
    result: string
  }
  scene_action?: SceneActionPayload
  sources?: RagSource[]
  usage?: TokenUsage
  retry?: {
    attempt: number
    max_attempts: number
    message: string
  }
  done?: boolean
  error?: string
}

export interface SceneMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolSteps?: SceneToolStep[]
  sources?: RagSource[]
  usage?: TokenUsage
}

export interface SceneSession {
  id: string
  title: string
  knowledgeBaseId: string
  messages: SceneMessage[]
  createdAt: number
  updatedAt: number
}

export interface SceneSessionsStorage {
  activeSessionId: string
  sessions: SceneSession[]
}

export interface LoadedSceneObject {
  id: string
  name: string
  fileName: string
  root: import('three').Object3D
}