import { streamSceneChat } from '@/api/scene-agent'
import { DEFAULT_CHAT_MODEL, DEFAULT_TEMPERATURE } from '@/constants/chat'
import {
  SCENE_DEFAULT_TITLE,
  SCENE_DEFAULT_TOP_K,
  SCENE_KB_NONE,
  SCENE_STORAGE_KEY,
  SCENE_TOOL_LABELS
} from '@/constants/scene'
import type { TokenUsage } from '@/types/chat'
import type { RagSource } from '@/types/rag'
import type {
  SceneActionPayload,
  SceneHistoryMessage,
  SceneMessage,
  SceneObjectSnapshot,
  SceneSession,
  SceneSessionsStorage,
  SceneToolStep
} from '@/types/scene'

function formatSceneError(message: string): string {
  if (/401|authentication|api key|invalid.*key/i.test(message)) {
    return 'DeepSeek API Key 无效或未配置，请在 server/.env 中设置 DEEPSEEK_API_KEY 后重启后端'
  }
  return message
}

function createId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function createMessage(role: SceneMessage['role'], content: string): SceneMessage {
  return { id: createId(role), role, content }
}

function createSession(knowledgeBaseId: string): SceneSession {
  const now = Date.now()
  return {
    id: createId('scene-session'),
    title: SCENE_DEFAULT_TITLE,
    knowledgeBaseId,
    messages: [],
    createdAt: now,
    updatedAt: now
  }
}

function createDefaultStorage(knowledgeBaseId: string): SceneSessionsStorage {
  const session = createSession(knowledgeBaseId)
  return { activeSessionId: session.id, sessions: [session] }
}

function parseStorage(raw: string | null, fallbackKbId: string): SceneSessionsStorage {
  if (!raw) return createDefaultStorage(fallbackKbId)
  try {
    const parsed = JSON.parse(raw) as SceneSessionsStorage
    if (!parsed.sessions?.length) return createDefaultStorage(fallbackKbId)
    return parsed
  } catch {
    return createDefaultStorage(fallbackKbId)
  }
}

function toolStatusLabel(name: string, phase: 'calling' | 'done'): string {
  const label = SCENE_TOOL_LABELS[name] ?? name
  return phase === 'calling' ? `正在调用 ${label}…` : `${label} 已完成`
}

export function useSceneAgent(options: {
  initialKnowledgeBaseId: Ref<string>
  getSceneObjects: () => SceneObjectSnapshot[]
  getSelectedObjectId: () => string | null
  onSceneAction: (action: SceneActionPayload) => void
}) {
  const storage = parseStorage(
    localStorage.getItem(SCENE_STORAGE_KEY),
    options.initialKnowledgeBaseId.value
  )
  const sessions = ref<SceneSession[]>(storage.sessions)
  const activeSessionId = ref(storage.activeSessionId)
  const input = ref('')
  const isStreaming = ref(false)
  const error = ref('')
  const retryNotice = ref('')
  const streamingContent = ref('')
  const streamingToolSteps = ref<SceneToolStep[]>([])
  const streamingSources = ref<RagSource[]>([])
  const streamingStatus = ref('')
  const streamingMessageId = ref<string | null>(null)
  const lastUsage = ref<TokenUsage | null>(null)
  const lastFailedUserText = ref('')

  let abortController: AbortController | null = null

  const activeSession = computed(
    () => sessions.value.find(item => item.id === activeSessionId.value) ?? null
  )

  const messages = computed(() => activeSession.value?.messages ?? [])

  function persist() {
    localStorage.setItem(
      SCENE_STORAGE_KEY,
      JSON.stringify({
        activeSessionId: activeSessionId.value,
        sessions: sessions.value
      } satisfies SceneSessionsStorage)
    )
  }

  watch([sessions, activeSessionId], persist, { deep: true })

  watch(options.initialKnowledgeBaseId, kbId => {
    const session = activeSession.value
    if (!session || session.knowledgeBaseId !== kbId) {
      ensureSessionForScope(kbId)
    }
  })

  function getWritableSession(): SceneSession | null {
    return sessions.value.find(item => item.id === activeSessionId.value) ?? null
  }

  function buildTitle(text: string): string {
    const trimmed = text.trim()
    return trimmed.length > 24 ? `${trimmed.slice(0, 24)}…` : trimmed || SCENE_DEFAULT_TITLE
  }

  function toHistoryPayload(messagesList: SceneMessage[]): SceneHistoryMessage[] {
    return messagesList.map(item => ({ role: item.role, content: item.content }))
  }

  function createNewSession(knowledgeBaseId?: string) {
    if (isStreaming.value) return
    const kbId = knowledgeBaseId !== undefined ? knowledgeBaseId : options.initialKnowledgeBaseId.value
    const session = createSession(kbId)
    sessions.value = [session, ...sessions.value].slice(0, 30)
    activeSessionId.value = session.id
    input.value = ''
    error.value = ''
    retryNotice.value = ''
    lastFailedUserText.value = ''
  }

  function ensureSessionForScope(kbId: string) {
    const forScope = sessions.value.filter(item => item.knowledgeBaseId === kbId)
    if (!forScope.length) {
      createNewSession(kbId)
      return
    }

    const active = activeSession.value
    if (active?.knowledgeBaseId === kbId && forScope.some(item => item.id === active.id)) {
      return
    }

    const latest = [...forScope].sort((a, b) => b.updatedAt - a.updatedAt)[0]
    activeSessionId.value = latest.id
    input.value = ''
    error.value = ''
    retryNotice.value = ''
  }

  function syncSessionsWithKnowledgeBases(validKbIds: string[]) {
    const validSet = new Set(validKbIds)
    const kept = sessions.value.filter(
      item => item.knowledgeBaseId === SCENE_KB_NONE || validSet.has(item.knowledgeBaseId)
    )

    const byScope = new Map<string, SceneSession[]>()
    for (const session of kept) {
      const list = byScope.get(session.knowledgeBaseId) ?? []
      list.push(session)
      byScope.set(session.knowledgeBaseId, list)
    }

    const next: SceneSession[] = []
    for (const list of byScope.values()) {
      const withMessages = list.filter(item => item.messages.length > 0)
      const empty = list.filter(item => item.messages.length === 0)
      if (empty.length <= 1) {
        next.push(...list)
        continue
      }
      const newestEmpty = empty.sort((a, b) => b.updatedAt - a.updatedAt)[0]
      next.push(...withMessages, newestEmpty)
    }

    sessions.value = next.sort((a, b) => b.updatedAt - a.updatedAt)

    if (sessions.value.some(item => item.id === activeSessionId.value)) return

    const kbId = options.initialKnowledgeBaseId.value
    if (kbId === SCENE_KB_NONE || validSet.has(kbId)) {
      ensureSessionForScope(kbId)
    } else if (sessions.value.length) {
      activeSessionId.value = sessions.value[0].id
    } else {
      createNewSession(SCENE_KB_NONE)
    }
  }

  function switchSession(sessionId: string) {
    if (isStreaming.value) return
    const session = sessions.value.find(item => item.id === sessionId)
    if (!session) return
    activeSessionId.value = sessionId
    options.initialKnowledgeBaseId.value = session.knowledgeBaseId
    input.value = ''
    error.value = ''
    retryNotice.value = ''
  }

  function deleteSession(sessionId: string) {
    if (isStreaming.value) return
    const target = sessions.value.find(item => item.id === sessionId)
    if (!target) return

    sessions.value = sessions.value.filter(item => item.id !== sessionId)

    if (activeSessionId.value !== sessionId) return

    const kbId = target.knowledgeBaseId
    const remaining = sessions.value.filter(item => item.knowledgeBaseId === kbId)
    if (remaining.length) {
      activeSessionId.value = remaining[0].id
    } else {
      createNewSession(kbId)
    }
  }

  function resetStreamingState() {
    streamingContent.value = ''
    streamingToolSteps.value = []
    streamingSources.value = []
    streamingStatus.value = ''
    streamingMessageId.value = null
  }

  function commitStreamingContent(fallback = '（无回复内容）') {
    if (!streamingMessageId.value) return

    const session = getWritableSession()
    const target = session?.messages.find(item => item.id === streamingMessageId.value)
    if (target) {
      target.content = streamingContent.value || fallback
      target.toolSteps = streamingToolSteps.value.length
        ? [...streamingToolSteps.value]
        : undefined
      target.sources = streamingSources.value.length ? [...streamingSources.value] : undefined
      if (session) session.updatedAt = Date.now()
    }

    resetStreamingState()
  }

  async function streamAssistantReply(
    session: SceneSession,
    userText: string,
    history: SceneHistoryMessage[]
  ) {
    const kbId = options.initialKnowledgeBaseId.value

    const assistant = createMessage('assistant', '')
    session.messages.push(assistant)
    resetStreamingState()
    streamingMessageId.value = assistant.id
    isStreaming.value = true
    retryNotice.value = ''
    lastUsage.value = null
    abortController = new AbortController()

    try {
      for await (const event of streamSceneChat(
        {
          message: userText,
          history,
          scene_objects: options.getSceneObjects(),
          selected_object_id: options.getSelectedObjectId(),
          ...(kbId ? { knowledge_base_id: kbId, top_k: SCENE_DEFAULT_TOP_K } : {}),
          model: DEFAULT_CHAT_MODEL,
          temperature: DEFAULT_TEMPERATURE
        },
        abortController.signal
      )) {
        if (event.error) throw new Error(event.error)

        if (event.retry) {
          retryNotice.value = `${event.retry.message}（${event.retry.attempt}/${event.retry.max_attempts}）`
        }

        if (event.tool_call) {
          streamingToolSteps.value.push({
            id: event.tool_call.id,
            type: 'tool_call',
            name: event.tool_call.name,
            arguments: event.tool_call.arguments
          })
          streamingStatus.value = toolStatusLabel(event.tool_call.name, 'calling')
        }

        if (event.tool_result) {
          streamingToolSteps.value.push({
            id: event.tool_result.id,
            type: 'tool_result',
            name: event.tool_result.name,
            result: event.tool_result.result
          })
          streamingStatus.value = toolStatusLabel(event.tool_result.name, 'done')
        }

        if (event.scene_action) {
          options.onSceneAction(event.scene_action)
        }

        if (event.sources?.length) {
          streamingSources.value = event.sources
        }

        if (event.content) {
          streamingContent.value = event.content
          streamingStatus.value = '正在生成回答…'
        }

        if (event.usage && streamingMessageId.value) {
          const target = session.messages.find(item => item.id === streamingMessageId.value)
          if (target) target.usage = event.usage
          lastUsage.value = event.usage
        }

        if (event.done) break
      }

      retryNotice.value = ''
      lastFailedUserText.value = ''
      commitStreamingContent()
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        streamingContent.value = streamingContent.value || '（已停止生成）'
        commitStreamingContent('（已停止生成）')
        return
      }

      const message = formatSceneError(err instanceof Error ? err.message : '发送失败')
      error.value = message
      lastFailedUserText.value = userText
      session.messages = session.messages.filter(item => item.id !== assistant.id)
      resetStreamingState()
    } finally {
      isStreaming.value = false
      retryNotice.value = ''
      streamingStatus.value = ''
      abortController = null
    }
  }

  async function sendMessage(overrideText?: string) {
    const text = (overrideText ?? input.value).trim()
    const session = getWritableSession()

    if (!text || !session || isStreaming.value) return

    error.value = ''
    const history = toHistoryPayload(session.messages)
    const isFirst = session.messages.length === 0

    session.messages.push(createMessage('user', text))
    if (isFirst) session.title = buildTitle(text)
    session.updatedAt = Date.now()
    if (!overrideText) input.value = ''

    await streamAssistantReply(session, text, history)
  }

  function explainSelectedObject(name: string) {
    const kbId = options.initialKnowledgeBaseId.value
    const kbHint = kbId
      ? ' 若知识库中有该模型的说明文档，请先检索再回答。'
      : ''
    sendMessage(`请解释当前选中的 3D 模型「${name}」的用途与特点。${kbHint}`)
  }

  async function retryLastMessage() {
    const text = lastFailedUserText.value.trim()
    const session = getWritableSession()
    if (!text || !session || isStreaming.value) return

    error.value = ''
    const history = toHistoryPayload(session.messages)
    await streamAssistantReply(session, text, history)
  }

  async function regenerateMessage(assistantMessageId: string) {
    const session = getWritableSession()
    if (!session || isStreaming.value) return

    const assistantIndex = session.messages.findIndex(item => item.id === assistantMessageId)
    if (assistantIndex === -1 || session.messages[assistantIndex].role !== 'assistant') return

    const userIndex = assistantIndex - 1
    if (userIndex < 0 || session.messages[userIndex].role !== 'user') return

    const userText = session.messages[userIndex].content
    if (!userText.trim()) return

    error.value = ''
    const history = toHistoryPayload(session.messages.slice(0, userIndex))
    session.messages.splice(assistantIndex)
    session.updatedAt = Date.now()

    await streamAssistantReply(session, userText, history)
  }

  function stopStreaming() {
    abortController?.abort()
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  function getMessageContent(message: SceneMessage) {
    if (message.id === streamingMessageId.value) return streamingContent.value
    return message.content
  }

  function getMessageToolSteps(message: SceneMessage) {
    if (message.id === streamingMessageId.value) return streamingToolSteps.value
    return message.toolSteps ?? []
  }

  function getMessageSources(message: SceneMessage) {
    if (message.id === streamingMessageId.value) return streamingSources.value
    return message.sources ?? []
  }

  function isMessageStreaming(message: SceneMessage) {
    return isStreaming.value && message.id === streamingMessageId.value
  }

  return {
    sessions,
    activeSessionId,
    activeSession,
    messages,
    input,
    isStreaming,
    error,
    retryNotice,
    streamingStatus,
    lastFailedUserText,
    lastUsage,
    createNewSession,
    ensureSessionForScope,
    syncSessionsWithKnowledgeBases,
    switchSession,
    deleteSession,
    sendMessage,
    explainSelectedObject,
    retryLastMessage,
    regenerateMessage,
    stopStreaming,
    onKeydown,
    getMessageContent,
    getMessageToolSteps,
    getMessageSources,
    isMessageStreaming
  }
}
