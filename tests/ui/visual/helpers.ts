/**
 * Shared helpers for canvas-registry visual regression (P8-09).
 * Diff threshold: maxDiffPixelRatio 0.001 (== 0.1%).
 */
import {
  expect,
  type Page,
} from '../../../frontend/node_modules/@playwright/test/index.js'

/** Fail CI when more than 0.1% of pixels differ from baseline. */
export const MAX_DIFF_PIXEL_RATIO = 0.001

export async function openStory(page: Page, storyId: string): Promise<void> {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto(`/iframe.html?id=${storyId}&viewMode=story`, {
    waitUntil: 'networkidle',
  })
  await page.evaluate(() => document.fonts.ready)
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation: none !important;
        caret-color: transparent !important;
        transition: none !important;
      }
      html, body {
        background: #f5f7fb !important;
        overflow: hidden !important;
      }
      #storybook-root {
        min-height: 800px !important;
      }
    `,
  })
  const story = page.locator('#storybook-root')
  await expect(story).toBeVisible()
  await expect(story.locator(':scope > *').first()).toBeVisible()
  // Settle layout after fonts/styles (Storybook iframe).
  await page.waitForTimeout(400)
}

export async function assertCanvasScreenshot(
  page: Page,
  snapshot: string,
): Promise<void> {
  // Fixed viewport screenshot (not element clip) for stable baseline size.
  await expect(page).toHaveScreenshot(snapshot, {
    animations: 'disabled',
    caret: 'hide',
    scale: 'css',
    fullPage: false,
    maxDiffPixelRatio: MAX_DIFF_PIXEL_RATIO,
  })
}
