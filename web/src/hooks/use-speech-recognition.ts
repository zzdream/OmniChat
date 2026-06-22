type SpeechRecognitionCtor = new () => SpeechRecognition

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function useSpeechRecognition(options?: {
  lang?: string
  /** 识别到一段完整语句时回调 */
  onFinal?: (text: string) => void
  /** 实时中间结果（可选，用于预览） */
  onInterim?: (text: string) => void
}) {
  const isSupported = ref(Boolean(getSpeechRecognitionCtor()))
  const isListening = ref(false)
  const error = ref('')

  let recognition: SpeechRecognition | null = null
  let baseInput = ''

  function cleanup() {
    if (!recognition) return
    recognition.onresult = null
    recognition.onerror = null
    recognition.onend = null
    try {
      recognition.stop()
    } catch {
      /* ignore */
    }
    recognition = null
    isListening.value = false
  }

  function formatError(code: string): string {
    switch (code) {
      case 'not-allowed':
      case 'service-not-allowed':
        return '麦克风权限被拒绝，请在浏览器设置中允许访问'
      case 'no-speech':
        return '未检测到语音，请再试一次'
      case 'network':
        return '语音识别需要网络连接（Chrome 使用 Google 服务）'
      case 'aborted':
        return ''
      default:
        return `语音识别失败（${code}）`
    }
  }

  function start(initialText = '') {
    error.value = ''
    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) {
      error.value = '当前浏览器不支持 Web Speech API，请使用 Chrome / Edge'
      return
    }

    cleanup()
    baseInput = initialText.trim()

    recognition = new Ctor()
    recognition.lang = options?.lang ?? 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ''
      let finalText = ''

      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const transcript = event.results[i][0]?.transcript ?? ''
        if (event.results[i].isFinal) {
          finalText += transcript
        } else {
          interim += transcript
        }
      }

      if (interim) {
        options?.onInterim?.(baseInput ? `${baseInput} ${interim}` : interim)
      }

      if (finalText.trim()) {
        const merged = baseInput ? `${baseInput} ${finalText.trim()}` : finalText.trim()
        options?.onFinal?.(merged)
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const message = formatError(event.error)
      if (message) error.value = message
      isListening.value = false
    }

    recognition.onend = () => {
      isListening.value = false
    }

    try {
      recognition.start()
      isListening.value = true
    } catch {
      error.value = '无法启动语音识别，请稍后重试'
      isListening.value = false
    }
  }

  function stop() {
    cleanup()
  }

  function toggle(initialText = '') {
    if (isListening.value) {
      stop()
      return
    }
    start(initialText)
  }

  onUnmounted(() => {
    cleanup()
  })

  return {
    isSupported,
    isListening,
    error,
    start,
    stop,
    toggle
  }
}
