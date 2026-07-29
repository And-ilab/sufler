import {
  expect,
  test,
  type Page,
} from '../../frontend/node_modules/@playwright/test/index.js'

async function openWidgetSample(page: Page) {
  await page.goto('/widget/sample.html')
  await page.evaluate(() => document.fonts.ready)
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        caret-color: transparent !important;
        transition: none !important;
      }
    `,
  })
  await expect(page.locator('#bb-chat-widget-host')).toBeAttached({
    timeout: 10_000,
  })
}

test('embeddable widget opens on sample bank page (FR-CC-09)', async ({ page }) => {
  await openWidgetSample(page)
  const host = page.locator('#bb-chat-widget-host')
  await expect(host).toHaveAttribute('data-widget-id', 'site-belarusbank')

  await host.getByTestId('widget-fab').click()
  const panel = host.getByTestId('widget-panel')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('Беларусбанк')
  await expect(panel).toContainText('site-belarusbank')

  await host.getByTestId('widget-start').click()
  await expect(host.getByTestId('widget-messages')).toBeVisible()
  await host.getByTestId('widget-input').fill('Лимит снятия?')
  await host.getByTestId('widget-send').click()
  await expect(host.getByTestId('widget-messages')).toContainText('Лимит снятия?')
  await expect(host.getByTestId('widget-telegram')).toBeVisible()
  await expect(host.getByTestId('widget-viber')).toBeVisible()
})

test('chat-widget-sample', async ({ page }) => {
  await openWidgetSample(page)
  const host = page.locator('#bb-chat-widget-host')
  await host.getByTestId('widget-fab').click()
  await host.getByTestId('widget-start').click()
  await expect(host.getByTestId('widget-messages')).toBeVisible()
  await expect(page.locator('body')).toHaveScreenshot('chat-widget-sample.png', {
    animations: 'disabled',
    scale: 'css',
  })
})
