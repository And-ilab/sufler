import { useEffect, useRef } from 'react'

const BAR_COUNT = 28

export function VoiceWaveform({
  analyser,
  active,
  width = 148,
  height = 32,
}: {
  analyser: AnalyserNode | null
  active: boolean
  width?: number
  height?: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const peaksRef = useRef<Float32Array>(new Float32Array(BAR_COUNT))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !analyser || !active) return

    const context = canvas.getContext('2d')
    if (!context) return

    const bins = new Uint8Array(analyser.frequencyBinCount)
    let frame = 0

    const draw = () => {
      const ratio = window.devicePixelRatio || 1
      const nextWidth = Math.floor(width * ratio)
      const nextHeight = Math.floor(height * ratio)
      if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
        canvas.width = nextWidth
        canvas.height = nextHeight
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
      context.clearRect(0, 0, width, height)

      analyser.getByteFrequencyData(bins)
      const skip = 2
      const usable = Math.max(1, bins.length - skip)
      const peaks = peaksRef.current
      const gap = 2
      const barWidth = Math.max(2, (width - gap * (BAR_COUNT - 1)) / BAR_COUNT)
      const midY = height / 2

      for (let index = 0; index < BAR_COUNT; index += 1) {
        const start = skip + Math.floor((index * usable) / BAR_COUNT)
        const end = skip + Math.floor(((index + 1) * usable) / BAR_COUNT)
        let sum = 0
        for (let bin = start; bin < end; bin += 1) sum += bins[bin] || 0
        const magnitude = sum / Math.max(1, end - start) / 255
        const target = 0.08 + magnitude * 0.92
        peaks[index] += (target - peaks[index]) * 0.35
        const barHeight = Math.max(3, peaks[index] * (height - 4))
        const x = index * (barWidth + gap)
        const y = midY - barHeight / 2
        const gradient = context.createLinearGradient(x, y, x, y + barHeight)
        gradient.addColorStop(0, '#ff8a80')
        gradient.addColorStop(0.5, '#ef5350')
        gradient.addColorStop(1, '#c62828')
        context.fillStyle = gradient
        const radius = Math.min(2, barWidth / 2)
        context.beginPath()
        if (typeof context.roundRect === 'function') {
          context.roundRect(x, y, barWidth, barHeight, radius)
        } else {
          context.rect(x, y, barWidth, barHeight)
        }
        context.fill()
      }

      frame = window.requestAnimationFrame(draw)
    }

    frame = window.requestAnimationFrame(draw)
    return () => {
      window.cancelAnimationFrame(frame)
      peaksRef.current = new Float32Array(BAR_COUNT)
    }
  }, [analyser, active, height, width])

  return (
    <canvas
      ref={canvasRef}
      className="voice-input__waveform-canvas"
      width={width}
      height={height}
      aria-hidden
    />
  )
}
