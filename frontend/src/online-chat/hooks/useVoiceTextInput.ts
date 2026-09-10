import { useCallback, useEffect, useRef, useState } from 'react'
import { transcribeUtterance } from '../../sufler/api/transcribe'

const TARGET_RATE = 16000
const MIN_DURATION_SEC = 0.35
const DEFAULT_MAX_DURATION_MS = 60_000
const PROCESSOR_BUFFER = 4096

interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  abort?: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error?: string }) => void) | null
  onend: (() => void) | null
}

interface SpeechRecognitionEventLike {
  resultIndex: number
  results: ArrayLike<{
    isFinal: boolean
    0: { transcript: string }
  }>
}

type SpeechRecognitionCtor = new () => SpeechRecognitionLike

function speechCtor(): SpeechRecognitionCtor | null {
  const holder = window as Window & {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return holder.SpeechRecognition || holder.webkitSpeechRecognition || null
}

function downsample(input: Float32Array, inRate: number, outRate: number): Float32Array {
  if (inRate === outRate) return input
  const ratio = inRate / outRate
  const length = Math.max(1, Math.floor(input.length / ratio))
  const output = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    output[index] = input[Math.min(input.length - 1, Math.floor(index * ratio))]
  }
  return output
}

function encodeWav(float32: Float32Array, sampleRate: number): Blob {
  const pcm = new Int16Array(float32.length)
  for (let index = 0; index < float32.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, float32[index]))
    pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
  }
  const buffer = new ArrayBuffer(44 + pcm.length * 2)
  const view = new DataView(buffer)
  const write = (offset: number, text: string) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index))
    }
  }
  write(0, 'RIFF')
  view.setUint32(4, 36 + pcm.length * 2, true)
  write(8, 'WAVE')
  write(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  write(36, 'data')
  view.setUint32(40, pcm.length * 2, true)
  new Int16Array(buffer, 44).set(pcm)
  return new Blob([buffer], { type: 'audio/wav' })
}

function mixMono(buffer: AudioBuffer): Float32Array {
  const left = buffer.getChannelData(0)
  if (buffer.numberOfChannels < 2) return new Float32Array(left)
  const right = buffer.getChannelData(1)
  const mixed = new Float32Array(left.length)
  for (let index = 0; index < left.length; index += 1) {
    mixed[index] = (left[index] + right[index]) * 0.5
  }
  return mixed
}

function mergeChunks(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((sum, item) => sum + item.length, 0)
  const merged = new Float32Array(total)
  let offset = 0
  for (const item of chunks) {
    merged.set(item, offset)
    offset += item.length
  }
  return merged
}

function isInsecureRemoteOrigin(): boolean {
  if (window.isSecureContext) return false
  const host = window.location.hostname
  return host !== 'localhost' && host !== '127.0.0.1'
}

export function appendVoiceTranscript(current: string, incoming: string): string {
  const next = incoming.trim()
  if (!next) return current
  const prefix = current.trimEnd()
  if (!prefix) {
    return next.charAt(0).toUpperCase() + next.slice(1)
  }
  return `${prefix} ${next}`
}

export type VoiceInputPhase = 'idle' | 'recording' | 'processing'

export interface VoiceTextInputState {
  phase: VoiceInputPhase
  recording: boolean
  processing: boolean
  elapsedMs: number
  analyser: AnalyserNode | null
  error: string
}

export interface UseVoiceTextInputOptions {
  onTranscript: (text: string) => void
  onError?: (message: string) => void
  maxDurationMs?: number
  enabled?: boolean
}

export function useVoiceTextInput({
  onTranscript,
  onError,
  maxDurationMs = DEFAULT_MAX_DURATION_MS,
  enabled = true,
}: UseVoiceTextInputOptions) {
  const [state, setState] = useState<VoiceTextInputState>({
    phase: 'idle',
    recording: false,
    processing: false,
    elapsedMs: 0,
    analyser: null,
    error: '',
  })
  const recordingRef = useRef(false)
  const processingRef = useRef(false)
  const enabledRef = useRef(enabled)
  enabledRef.current = enabled
  const onTranscriptRef = useRef(onTranscript)
  onTranscriptRef.current = onTranscript
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError
  const startingRef = useRef(false)
  const cleanupRef = useRef<(() => void) | null>(null)
  const chunksRef = useRef<Float32Array[]>([])
  const sampleRateRef = useRef(TARGET_RATE)
  const browserTextRef = useRef('')
  const startedAtRef = useRef(0)
  const maxTimerRef = useRef<number | null>(null)
  const tickTimerRef = useRef<number | null>(null)
  const stopRef = useRef<(() => Promise<void>) | null>(null)

  const emitError = useCallback((message: string) => {
    setState((current) => ({ ...current, error: message }))
    onErrorRef.current?.(message)
  }, [])

  const clearTimers = useCallback(() => {
    if (maxTimerRef.current != null) {
      window.clearTimeout(maxTimerRef.current)
      maxTimerRef.current = null
    }
    if (tickTimerRef.current != null) {
      window.clearInterval(tickTimerRef.current)
      tickTimerRef.current = null
    }
  }, [])

  const releaseCapture = useCallback(() => {
    cleanupRef.current?.()
    cleanupRef.current = null
    chunksRef.current = []
    browserTextRef.current = ''
    startedAtRef.current = 0
    clearTimers()
  }, [clearTimers])

  const stopRecording = useCallback(async () => {
    if (!recordingRef.current || processingRef.current) return
    recordingRef.current = false
    startingRef.current = false
    processingRef.current = true
    clearTimers()

    const chunks = chunksRef.current.slice()
    const sampleRate = sampleRateRef.current
    const backup = browserTextRef.current.trim()
    cleanupRef.current?.()
    cleanupRef.current = null
    chunksRef.current = []
    browserTextRef.current = ''

    setState({
      phase: 'processing',
      recording: false,
      processing: true,
      elapsedMs: Date.now() - (startedAtRef.current || Date.now()),
      analyser: null,
      error: '',
    })

    const pcm = downsample(mergeChunks(chunks), sampleRate, TARGET_RATE)
    const tooShort = pcm.length < TARGET_RATE * MIN_DURATION_SEC

    try {
      let text = ''
      if (!tooShort) {
        text = await transcribeUtterance(encodeWav(pcm, TARGET_RATE), 'operator')
      }
      if (!text) text = backup
      const cleaned = text.trim()
      if (!cleaned) {
        emitError('Речь не распознана. Повторите запись или введите текст.')
      } else {
        onTranscriptRef.current(cleaned)
      }
    } catch (error: unknown) {
      if (backup) {
        onTranscriptRef.current(backup)
      } else {
        const network = error instanceof TypeError
        emitError(
          network
            ? 'Нет связи с распознаванием речи. Проверьте сеть и повторите запись.'
            : 'Не удалось распознать речь. Повторите запись или введите текст.',
        )
      }
    } finally {
      processingRef.current = false
      startedAtRef.current = 0
      setState({
        phase: 'idle',
        recording: false,
        processing: false,
        elapsedMs: 0,
        analyser: null,
        error: '',
      })
    }
  }, [clearTimers, emitError])

  stopRef.current = stopRecording

  const startRecording = useCallback(async () => {
    if (!enabledRef.current || recordingRef.current || processingRef.current || startingRef.current) return
    startingRef.current = true
    setState({
      phase: 'processing',
      recording: false,
      processing: true,
      elapsedMs: 0,
      analyser: null,
      error: '',
    })
    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      startingRef.current = false
      setState((current) => ({ ...current, phase: 'idle', processing: false }))
      emitError('Браузер не поддерживает запись с микрофона.')
      return
    }

    const micErrorMessage = (error: unknown) => {
      const name = error instanceof DOMException ? error.name : ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        return 'Нет доступа к микрофону. Разрешите его в браузере и нажмите на микрофон снова.'
      }
      if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        return 'Микрофон не найден. Подключите устройство и повторите.'
      }
      if (name === 'NotReadableError' || name === 'AbortError') {
        return 'Микрофон занят другим приложением. Закройте его и повторите.'
      }
      return 'Не удалось включить микрофон. Проверьте устройство и повторите.'
    }

    let micStream: MediaStream
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    } catch (error: unknown) {
      startingRef.current = false
      setState({
        phase: 'idle',
        recording: false,
        processing: false,
        elapsedMs: 0,
        analyser: null,
        error: '',
      })
      emitError(micErrorMessage(error))
      return
    }

    if (!enabledRef.current) {
      startingRef.current = false
      micStream.getTracks().forEach((track) => track.stop())
      setState({
        phase: 'idle',
        recording: false,
        processing: false,
        elapsedMs: 0,
        analyser: null,
        error: '',
      })
      return
    }

    let context: AudioContext
    try {
      context = new AudioContext()
    } catch {
      startingRef.current = false
      micStream.getTracks().forEach((track) => track.stop())
      setState({
        phase: 'idle',
        recording: false,
        processing: false,
        elapsedMs: 0,
        analyser: null,
        error: '',
      })
      emitError('Браузер не поддерживает запись звука.')
      return
    }
    void context.resume()

    let source: MediaStreamAudioSourceNode
    let analyser: AnalyserNode
    let processor: ScriptProcessorNode
    let sink: GainNode
    try {
      source = context.createMediaStreamSource(micStream)
      analyser = context.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.72
      processor = context.createScriptProcessor(PROCESSOR_BUFFER, 2, 1)
      sink = context.createGain()
      sink.gain.value = 0
      source.connect(analyser)
      analyser.connect(processor)
      processor.connect(sink)
      sink.connect(context.destination)
    } catch {
      startingRef.current = false
      micStream.getTracks().forEach((track) => track.stop())
      void context.close()
      setState({
        phase: 'idle',
        recording: false,
        processing: false,
        elapsedMs: 0,
        analyser: null,
        error: '',
      })
      emitError('Не удалось начать запись звука.')
      return
    }

    chunksRef.current = []
    browserTextRef.current = ''
    sampleRateRef.current = context.sampleRate
    recordingRef.current = true
    startedAtRef.current = Date.now()

    processor.onaudioprocess = (event) => {
      if (!recordingRef.current) return
      const input = mixMono(event.inputBuffer)
      sampleRateRef.current = event.inputBuffer.sampleRate
      chunksRef.current.push(input)
    }

    const Recognition = speechCtor()
    let recognition: SpeechRecognitionLike | null = null
    if (Recognition && !isInsecureRemoteOrigin()) {
      recognition = new Recognition()
      recognition.lang = 'ru-RU'
      recognition.continuous = true
      recognition.interimResults = true
      recognition.onresult = (event) => {
        let finals = ''
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const piece = String(event.results[index]?.[0]?.transcript || '').trim()
          if (event.results[index].isFinal && piece) finals += `${piece} `
        }
        if (finals.trim()) {
          browserTextRef.current = `${browserTextRef.current} ${finals}`.trim()
        }
      }
      recognition.onerror = () => {
        /* Vosk remains the primary path */
      }
      recognition.onend = () => {
        if (!recordingRef.current || !recognition) return
        window.setTimeout(() => {
          if (!recordingRef.current || !recognition) return
          try {
            recognition.start()
          } catch {
            /* already started */
          }
        }, 250)
      }
      try {
        recognition.start()
      } catch {
        recognition = null
      }
    }

    cleanupRef.current = () => {
      processor.onaudioprocess = null
      processor.disconnect()
      source.disconnect()
      analyser.disconnect()
      sink.disconnect()
      micStream.getTracks().forEach((track) => track.stop())
      void context.close()
      if (recognition) {
        try {
          recognition.onend = null
          recognition.stop()
        } catch {
          /* already stopped */
        }
      }
    }

    setState({
      phase: 'recording',
      recording: true,
      processing: false,
      elapsedMs: 0,
      analyser,
      error: '',
    })

    tickTimerRef.current = window.setInterval(() => {
      if (!startedAtRef.current) return
      setState((current) =>
        current.recording
          ? { ...current, elapsedMs: Date.now() - startedAtRef.current }
          : current,
      )
    }, 200)

    maxTimerRef.current = window.setTimeout(() => {
      void stopRef.current?.()
    }, maxDurationMs)
  }, [emitError, maxDurationMs])

  const toggleRecording = useCallback(() => {
    if (!enabledRef.current && !recordingRef.current) return
    if (processingRef.current) return
    if (recordingRef.current) {
      void stopRecording()
      return
    }
    void startRecording()
  }, [startRecording, stopRecording])

  useEffect(() => {
    if (!enabled && recordingRef.current) {
      void stopRecording()
    }
  }, [enabled, stopRecording])

  useEffect(() => {
    return () => {
      recordingRef.current = false
      processingRef.current = false
      startingRef.current = false
      releaseCapture()
    }
  }, [releaseCapture])

  return {
    ...state,
    startRecording,
    stopRecording,
    toggleRecording,
  }
}
