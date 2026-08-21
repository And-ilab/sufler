import { useEffect, useState } from 'react'
import {
  fetchClientHistory,
  type ClientHistorySummaryBlock,
} from '../../online-chat/api/onlineChatApi'

/** Oktell mock callerid until telephony passes the real number. */
export const DEMO_CALLER_PHONE = '+375291234567'

export type SuflerClientSummary = {
  preview: string
  summary: string
  detailedSummary: string
  blocks: ClientHistorySummaryBlock[]
  isFirst: boolean
  previousCount: number
}

const EMPTY: SuflerClientSummary = {
  preview: 'История обращений загружается…',
  summary: 'История обращений загружается…',
  detailedSummary: '',
  blocks: [],
  isFirst: false,
  previousCount: 0,
}

function mapHistory(
  summary: string,
  detailed: string,
  blocks: ClientHistorySummaryBlock[],
  previousCount: number,
  isFirst: boolean,
): SuflerClientSummary {
  const reallyFirst = isFirst || (previousCount <= 0 && blocks.length === 0)
  let text = summary.trim()
  if (!text) {
    text = reallyFirst
      ? 'Первое обращение клиента.'
      : `Клиент обращался ранее (${Math.max(previousCount, blocks.length)}).`
  } else if (!reallyFirst && /^первое обращение клиента\.?$/i.test(text)) {
    text = `Клиент обращался ранее (${Math.max(previousCount, blocks.length)}).`
  }
  return {
    preview: text,
    summary: reallyFirst
      ? 'Первое обращение клиента — предыдущей истории нет.'
      : text,
    detailedSummary: detailed.trim() || text,
    blocks,
    isFirst: reallyFirst,
    previousCount,
  }
}

export function useClientSummary(clientPhone = '') {
  const phone = clientPhone.trim() || DEMO_CALLER_PHONE
  const [data, setData] = useState<SuflerClientSummary>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    void fetchClientHistory({ phone })
      .then((response) => {
        if (cancelled) return
        setData(
          mapHistory(
            response.summary ?? '',
            response.detailed_summary ?? '',
            response.detailed_blocks ?? [],
            response.previous_count ?? response.items?.length ?? 0,
            Boolean(response.is_first),
          ),
        )
      })
      .catch((requestError: unknown) => {
        if (cancelled) return
        setData({
          ...EMPTY,
          preview: 'Не удалось загрузить историю клиента.',
          summary: 'Не удалось загрузить историю клиента.',
        })
        setError(
          requestError instanceof Error
            ? requestError.message
            : 'Не удалось загрузить историю',
        )
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [phone])

  return { phone, data, loading, error }
}
