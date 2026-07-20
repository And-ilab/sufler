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
