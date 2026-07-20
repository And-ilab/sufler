import {
  expect,
  test,
  type Page,
} from '../../frontend/node_modules/@playwright/test/index.js'

const stories = [
  ['button-primary', 'foundation-button--primary'],
  ['card-default', 'foundation-card--default'],
  ['hint-card-compact', 'foundation-hintcard--compact'],
  ['hint-card-expanded', 'foundation-hintcard--expanded'],
  ['sidebar-default', 'foundation-sidebar--default'],
  ['fab-default', 'foundation-fab--default'],
  ['status-badge-success', 'foundation-statusbadge--success'],
  ['portal-launcher-menu', 'portal-launcher--menu-open'],
  ['admin-shell-default', 'ai-hub-admin-shell--default'],
  ['model-params-form', 'ai-hub-admin-shell--model-parameters'],
  ['ai-hub-panel-assistant', 'ai-hub-panel--default-assistant'],
  ['ai-hub-panel-call', 'ai-hub-panel--active-call'],
] as const

async function openStory(page: Page, storyId: string) {
  await page.goto(`/iframe.html?id=${storyId}&viewMode=story`)
  await page.evaluate(() => document.fonts.ready)
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        caret-color: transparent !important;
        transition: none !important;
      }
      body { background: #f5f7fb !important; }
    `,
  })
}

test('launcher opens both authorized module windows', async ({ page }) => {
  await openStory(page, 'portal-launcher--menu-open')
  await page.getByRole('menuitem', { name: /Суфлёр/ }).click()
  await page.getByTestId('launcher-button').click()
  await page.getByRole('menuitem', { name: /Ассистент/ }).click()

  await expect(page.getByTestId('sufler-window')).toBeVisible()
  await expect(page.getByTestId('assistant-window')).toBeVisible()
})

test('launcher is hidden for unauthorized role', async ({ page }) => {
  await openStory(page, 'portal-launcher--unauthorized')
  await expect(page.getByTestId('launcher-button')).toHaveCount(0)
  await expect(page.getByTestId('launcher-menu')).toHaveCount(0)
})

test('launcher module window can be resized', async ({ page }) => {
  await openStory(page, 'portal-launcher--menu-open')
  await page.getByRole('menuitem', { name: /Суфлёр/ }).click()

  const windowPanel = page.getByTestId('sufler-window')
  const handle = page.getByRole('button', {
    name: 'Изменить размер окна Суфлёр',
  })
  const before = await windowPanel.boundingBox()
  const handleBox = await handle.boundingBox()
  expect(before).not.toBeNull()
  expect(handleBox).not.toBeNull()

  await page.mouse.move(
    handleBox!.x + handleBox!.width / 2,
    handleBox!.y + handleBox!.height / 2,
  )
  await page.mouse.down()
  await page.mouse.move(
    handleBox!.x + handleBox!.width / 2 + 60,
    handleBox!.y + handleBox!.height / 2 + 40,
  )
  await page.mouse.up()

  const after = await windowPanel.boundingBox()
  expect(after!.width).toBeGreaterThan(before!.width)
  expect(after!.height).toBeGreaterThan(before!.height)
})

test('admin sidebar exposes all groups and routable screens', async ({ page }) => {
  await openStory(page, 'ai-hub-admin-shell--default')

  const sidebar = page.getByTestId('admin-sidebar')
  await expect(sidebar).toBeVisible()
  for (const group of ['ОБЩЕЕ', 'АССИСТЕНТ', 'СУФЛЁР / КЦ', 'ДОКУМЕНТЫ', 'ССЫЛКИ']) {
    await expect(sidebar.getByRole('heading', { name: group })).toBeAttached()
  }

  const links = sidebar.getByRole('link')
  await expect(links).toHaveCount(20)
  await expect(page.getByTestId('admin-save-footer')).toBeVisible()
  await expect(page.getByLabel('Демо роль')).toBeVisible()

  const routes = [
    'audit', 'llm_config_assistant', 'model_params', 'prompts_assistant',
    'capabilities', 'kb_admin', 'qu_admin', 'data_sources', 'assistant_tools',
    'monitoring', 'llm_config_cc', 'model_params/cc', 'scenario_editor',
    'scenario_test', 'scenario_bindings', 'sufler_policies', 'doc_types',
    'doc_export', 'external',
  ]
  for (const route of routes) {
    await sidebar.locator(`a[href="/ai-hub/admin/${route}"]`).click()
    const screenId = route === 'model_params/cc' ? 'model_params' : route
    await expect(page.locator(`[data-screen-id="${screenId}"]`)).toBeVisible()
    await expect(page).toHaveURL(new RegExp(`/ai-hub/admin/${route}$`))
  }
})

test('model params validates and saves through API', async ({ page }) => {
  await page.route('**/api/admin/model-registry/model-params/**', async (route) => {
    const payload = route.request().postDataJSON()
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        profile: 'assistant_bank',
        slot: 'llm_assistant_bank',
        ...payload,
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
        revision: 2,
        updated_at: '2026-07-20T12:30:00Z',
        updated_by: 'admin',
      }),
    })
  })
  await openStory(page, 'ai-hub-admin-shell--model-parameters')

  const overlap = page.getByLabel('Chunk overlap, tokens')
  await overlap.fill('600')
  await expect(page.getByText('Overlap должен быть меньше размера chunk')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Сохранить' })).toBeDisabled()

  await overlap.fill('120')
  await page.getByLabel('Max tokens').fill('1536')
  await page.getByRole('button', { name: 'Сохранить' }).click()

  await expect(page.getByText('Сохранено · revision 2')).toBeVisible()
  await expect(page.getByLabel('Max tokens')).toHaveValue('1536')
})

test('QU admin previews ranked results with matched example', async ({ page }) => {
  await page.route('**/api/admin/qu/preview/', async (route) => {
    expect(route.request().postDataJSON()).toEqual({
      query: 'оформление отпуска сотруднику',
      limit: 5,
    })
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        query: 'оформление отпуска сотруднику',
        kb_id: 'cc_production',
        min_relevance: 0.65,
        min_relevance_percent: 65,
        documents: [
          {
            rank: 1,
            article_id: 101,
            chunk_index: 0,
            title: 'Положение об отпусках',
            permalink: 'https://suz.local/articles/101',
            snippet: 'Правила оформления ежегодного оплачиваемого отпуска.',
            relevance_score: 0.92,
            relevance_percent: 92,
            meets_min_relevance: true,
            matched_example_id: 7,
            matched_example: 'Как оформить отпуск сотруднику?',
          },
        ],
      }),
    })
  })
  await openStory(page, 'ai-hub-admin-shell--qu-preview')

  await page.getByLabel('Запрос пользователя').fill('оформление отпуска сотруднику')
  await page.getByRole('button', { name: 'Preview' }).click()

  const results = page.getByRole('table')
  await expect(results).toBeVisible()
  await expect(results.getByText('Положение об отпусках')).toBeVisible()
  await expect(results.getByText('92%')).toBeVisible()
  await expect(results.getByText('Как оформить отпуск сотруднику?')).toBeVisible()
})

test('AI Hub panel hides tabs by RBAC', async ({ page }) => {
  await openStory(page, 'ai-hub-panel--documents-only')
  const tablist = page.getByRole('tablist', { name: 'Модули AI Hub' })

  await expect(tablist.getByRole('tab')).toHaveCount(1)
  await expect(tablist.getByRole('tab', { name: 'Документы' })).toBeVisible()
  await expect(tablist.getByRole('tab', { name: 'Ассистент' })).toHaveCount(0)
  await expect(tablist.getByRole('tab', { name: 'Суфлёр' })).toHaveCount(0)
})

test('active call locks AI Hub to Sufler and controls work', async ({ page }) => {
  await openStory(page, 'ai-hub-panel--active-call')
  const tablist = page.getByRole('tablist', { name: 'Модули AI Hub' })

  await expect(tablist.getByRole('tab')).toHaveCount(1)
  await expect(tablist.getByRole('tab', { name: /Суфлёр/ })).toBeVisible()
  await expect(page.getByText('Активный звонок')).toBeVisible()

  const hint = page.getByRole('button', { name: /Повышение лимита перевода/ })
  await hint.click()
  await expect(hint).toHaveAttribute('aria-expanded', 'true')

  await page.getByRole('button', { name: 'Закрепить панель' }).click()
  await expect(page.getByRole('button', { name: 'Открепить панель' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Свернуть панель' }).click()
  await expect(page.getByTestId('hub-panel')).toHaveCount(0)
  await page.getByTestId('hub-panel-fab').click()
  await expect(page.getByTestId('hub-panel')).toBeVisible()
  await page.getByRole('button', { name: 'Закрыть панель' }).click()
  await expect(page.getByTestId('hub-panel')).toHaveCount(0)
})

for (const [snapshotName, storyId] of stories) {
  test(snapshotName, async ({ page }) => {
    await openStory(page, storyId)
    const story = page.locator('#storybook-root')
    await expect(story).toBeVisible()
    await expect(story).toHaveScreenshot(`${snapshotName}.png`, {
      animations: 'disabled',
      scale: 'css',
    })
  })
}
