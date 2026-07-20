import type { Meta, StoryObj } from '@storybook/react-vite'
import { HintCard } from './HintCard'

const content =
  'Для оформления карты потребуется паспорт. Заявку можно подать в отделении или через интернет-банкинг. Срок выпуска зависит от выбранного продукта и региона обслуживания.'

const meta = {
  title: 'Foundation/HintCard',
  component: HintCard,
  args: {
    title: 'Рекомендуемый ответ',
    relevance: 'Релевантность 96%',
    children: content,
    style: { width: 520 },
  },
} satisfies Meta<typeof HintCard>

export default meta
type Story = StoryObj<typeof meta>

export const Compact: Story = { args: { defaultExpanded: false } }
export const Expanded: Story = { args: { defaultExpanded: true } }
