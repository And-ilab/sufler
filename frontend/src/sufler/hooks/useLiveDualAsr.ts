import { useCallback, useRef, useState } from 'react'
import { transcribeUtterance } from '../api/transcribe'

export type DualSpeaker = 'client' | 'operator'

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

function rms(samples: Float32Array): number {
  let sum = 0
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index]
    sum += value * value
  }
  return Math.sqrt(sum / Math.max(1, samples.length))
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

function attachPcmUtterances(
  context: AudioContext,
  stream: MediaStream,
  recordingRef: { current: boolean },
  onLevel: (level: number) => void,
  onWav: (wav: Blob) => void,
): { processor: ScriptProcessorNode; stop: () => void } {
  const source = context.createMediaStreamSource(stream)
  const processor = context.createScriptProcessor(4096, 1, 1)
  const sink = context.createGain()
  sink.gain.value = 0
  source.connect(processor)
  processor.connect(sink)
  sink.connect(context.destination)
  const chunks: Float32Array[] = []
  let speaking = false
  let silenceMs = 0
  processor.onaudioprocess = (event) => {
    if (!recordingRef.current) return
    const input = event.inputBuffer.getChannelData(0)
    const level = rms(input)
    onLevel(level)
    if (level >= 0.02) {
      speaking = true
      silenceMs = 0
      chunks.push(new Float32Array(input))
    } else if (speaking) {
      silenceMs += (input.length / event.inputBuffer.sampleRate) * 1000
      chunks.push(new Float32Array(input))
      if (silenceMs >= 700) {
        speaking = false
        silenceMs = 0
        const mergedLength = chunks.reduce((sum, item) => sum + item.length, 0)
        const merged = new Float32Array(mergedLength)
        let offset = 0
        for (const item of chunks) {
          merged.set(item, offset)
          offset += item.length
        }
        chunks.length = 0
        const rate = event.inputBuffer.sampleRate
        const pcm = downsample(merged, rate, 16000)
        if (pcm.length < 16000 * 0.35) return
        onWav(encodeWav(pcm, 16000))
      }
    }
  }
  return {
    processor,
    stop: () => {
      processor.disconnect()
      source.disconnect()
      sink.disconnect()
    },
  }
}

export interface LiveDualAsrState {
  recording: boolean
  micLevel: number
  systemLevel: number
  micSpeaker: DualSpeaker
  systemSpeaker: DualSpeaker
  status: string
  error: string
  systemCapture: boolean
}

export function useLiveDualAsr(
  onUtterance: (speaker: DualSpeaker, text: string, isFinal: boolean) => void,
) {
  const [state, setState] = useState<LiveDualAsrState>({
    recording: false,
    micLevel: 0,
    systemLevel: 0,
    micSpeaker: 'client',
    systemSpeaker: 'operator',
    status: '',
    error: '',
    systemCapture: false,
  })
  const recordingRef = useRef(false)
  const micSpeakerRef = useRef<DualSpeaker>('client')
  const systemSpeakerRef = useRef<DualSpeaker>('operator')
  const onUtteranceRef = useRef(onUtterance)
  onUtteranceRef.current = onUtterance
  const cleanupRef = useRef<(() => void) | null>(null)

  const setPartial = useCallback((patch: Partial<LiveDualAsrState>) => {
    setState((current) => ({ ...current, ...patch }))
  }, [])

  const swapSpeakers = useCallback(() => {
    setState((current) => {
      const micSpeaker = current.micSpeaker === 'client' ? 'operator' : 'client'
      const systemSpeaker = micSpeaker === 'client' ? 'operator' : 'client'
      micSpeakerRef.current = micSpeaker
      systemSpeakerRef.current = systemSpeaker
      return { ...current, micSpeaker, systemSpeaker }
    })
  }, [])

  const stop = useCallback(() => {
    recordingRef.current = false
    cleanupRef.current?.()
    cleanupRef.current = null
    setPartial({
      recording: false,
      micLevel: 0,
      systemLevel: 0,
      status: 'Запись остановлена',
    })
  }, [setPartial])

  const start = useCallback(async () => {
    if (recordingRef.current) return
    recordingRef.current = true
    const Recognition = speechCtor()
    const recognition = Recognition ? new Recognition() : null
    if (recognition) {
      recognition.lang = 'ru-RU'
      recognition.continuous = true
      recognition.interimResults = true
      recognition.onresult = (event) => {
        let transcript = ''
        let isFinal = false
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index]
          transcript += result[0].transcript
          isFinal = result.isFinal
        }
        const text = transcript.trim()
        if (!text) return
        onUtteranceRef.current(micSpeakerRef.current, text, isFinal)
      }
      recognition.onerror = (event) => {
        if (event.error === 'no-speech' || event.error === 'aborted') return
        setPartial({
          error: '',
          status:
            event.error === 'network' || event.error === 'service-not-allowed'
              ? 'Облачное распознавание недоступно. Говорите паузами — отправим на локальный STT, либо введите реплику.'
              : `Микрофон: ${event.error || 'ошибка распознавания'}`,
        })
      }
      recognition.onend = () => {
        if (recordingRef.current) {
          try {
            recognition.start()
          } catch {
            /* Chrome throws if start() races */
          }
        }
      }
      try {
        recognition.start()
      } catch {
        setPartial({ error: 'Не удалось запустить распознавание микрофона' })
      }
    }

    let micStream: MediaStream
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      })
    } catch {
      try {
        recognition?.stop()
      } catch {
        /* ignore */
      }
      setPartial({ error: 'Нет доступа к микрофону. Разрешите его в браузере.' })
      recordingRef.current = false
      return
    }

    setPartial({
      recording: true,
      error: '',
      status: Recognition
        ? 'Говорите в микрофон. Клиент пишется в ленту, подсказки — через DeepSeek.'
        : 'Говорите паузами или введите реплику — облачного распознавания в этом браузере нет.',
      systemCapture: false,
    })

    const micContext = new AudioContext()
    void micContext.resume()
    const micCapture = attachPcmUtterances(
      micContext,
      micStream,
      recordingRef,
      (level) => setState((current) => ({ ...current, micLevel: level })),
      (wav) => {
        const speaker = micSpeakerRef.current
        void transcribeUtterance(wav, speaker)
          .then((text) => {
            if (text) onUtteranceRef.current(speaker, text, true)
          })
          .catch(() => {
            /* Speech Recognition or manual input still available */
          })
      },
    )

    let systemStream: MediaStream | null = null
    let systemContext: AudioContext | null = null
    let systemCapture: { stop: () => void } | null = null

    const attachSystem = async () => {
      try {
        systemStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
          },
        })
      } catch {
        setPartial({
          status: 'Микрофон пишется. Системный звук не выбран — в Chrome отметьте «Также системный звук».',
        })
        return
      }
      const audioTracks = systemStream.getAudioTracks()
      if (!audioTracks.length) {
        systemStream.getTracks().forEach((track) => track.stop())
        systemStream = null
        setPartial({
          status: 'Микрофон пишется. В окне шаринга включите «Также системный звук».',
        })
        return
      }
      systemContext = new AudioContext({ sampleRate: 16000 })
      void systemContext.resume()
      systemCapture = attachPcmUtterances(
        systemContext,
        systemStream,
        recordingRef,
        (level) => setState((current) => ({ ...current, systemLevel: level })),
        (wav) => {
          const speaker = systemSpeakerRef.current
          void transcribeUtterance(wav, speaker)
            .then((text) => {
              if (text) onUtteranceRef.current(speaker, text, true)
            })
            .catch((error: unknown) => {
              setPartial({
                error: error instanceof Error ? error.message : 'Системный звук не распознан',
              })
            })
        },
      )
      systemStream.getVideoTracks().forEach((track) => {
        track.enabled = false
      })
      setPartial({
        systemCapture: true,
        status: 'Два канала: микрофон и системный звук пишутся отдельно.',
      })
    }
    void attachSystem()

    cleanupRef.current = () => {
      try {
        if (recognition) {
          recognition.onend = null
          recognition.stop()
        }
      } catch {
        /* already stopped */
      }
      micCapture.stop()
      systemCapture?.stop()
      micStream.getTracks().forEach((track) => track.stop())
      systemStream?.getTracks().forEach((track) => track.stop())
      void micContext.close()
      void systemContext?.close()
    }
  }, [setPartial])

  return { ...state, start, stop, swapSpeakers }
}
