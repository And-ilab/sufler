import type { Meta, StoryObj } from '@storybook/react-vite'
import { AiHubAdminApp } from './AiHubAdminApp'

const meta = {
  title: 'AI Hub/Admin Shell',
  component: AiHubAdminApp,
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    roles: ['software_administrator'],
    initialScreen: 'llm_config_assistant',
    demoRoleSwitcher: true,
  },
} satisfies Meta<typeof AiHubAdminApp>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const ModelParameters: Story = {
  args: {
    initialScreen: 'model_params',
    initialProfile: 'assistant',
    initialModelParams: {
      profile: 'assistant_bank',
      slot: 'llm_assistant_bank',
      generation: {
        temperature: 0.35,
        top_p: 0.9,
        max_tokens: 1024,
        response_chars_max: 500,
      },
      rag: {
        chunk_size_tokens: 512,
        chunk_overlap_tokens: 100,
        context_inclusion: 0.6,
        deterministic_answer: 0.85,
      },
      read_only: {
        dev_model: 'stub:assistant_bank',
        prod_candidate: null,
        status: 'approved_dev',
      },
      constraints: {
        temperature: { min: 0, max: 1, step: 0.01 },
        top_p: { min: 0.01, max: 1, step: 0.01 },
        max_tokens: { min: 1, max: 32768 },
        response_chars_max: { min: 1, max: 500 },
      },
      revision: 1,
      updated_at: '2026-07-20T12:00:00Z',
      updated_by: 'admin',
    },
  },
}

export const QuPreview: Story = {
  args: {
    initialScreen: 'qu_admin',
  },
}

export const ReadOnlyAudit: Story = {
  args: {
    initialScreen: 'audit',
  },
  play: async ({ canvasElement }) => {
    const select = canvasElement.querySelector<HTMLSelectElement>('select')
    if (select) {
      select.value = 'auditor'
      select.dispatchEvent(new Event('change', { bubbles: true }))
    }
  },
}
