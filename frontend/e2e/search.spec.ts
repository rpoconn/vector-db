import { expect, test } from '@playwright/test'
import { cardCategories } from './support.ts'

test.describe('search', () => {
  test('search-as-you-type ranks matching products first', async ({ page }) => {
    await page.goto('/')
    await page.getByLabel('Search products').pressSequentially('lamp', { delay: 30 })

    await expect(page).toHaveURL(/[?&]q=lamp/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Results for “lamp”')
    await expect(page.getByText(/% match$/).first()).toBeVisible()
    const names = page.locator('main ul > li h3')
    await expect(names.first()).toContainText('Lamp')
    for (const name of (await names.allTextContents()).slice(0, 4)) {
      expect(name).toContain('Lamp')
    }
  })

  test('searching within a category only returns that category', async ({ page }) => {
    await page.goto('/?q=cozy%20winter&category=Blanket')

    await expect(page.getByText('within Blanket')).toBeVisible()
    await expect.poll(() => cardCategories(page)).toEqual(Array<string>(8).fill('Blanket'))
  })

  test('a result opens a product whose gallery switches angles', async ({ page }) => {
    await page.goto('/?q=lamp')
    const firstHit = page.locator('main ul > li a').first()
    const hitName = await firstHit.getByRole('heading', { level: 3 }).textContent()
    await firstHit.click()

    await expect(page).toHaveURL(/\/products\/DEMO\d+$/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(hitName ?? '')
    const tabs = page.getByRole('tab')
    expect(await tabs.count()).toBeGreaterThanOrEqual(2)
    const mainImage = page.getByRole('tabpanel').locator('img')
    const first = await mainImage.getAttribute('src')

    await tabs.nth(1).click()
    await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true')
    const second = await mainImage.getAttribute('src')
    expect(second).not.toBe(first)

    await page.keyboard.press('ArrowRight')
    await expect(tabs.nth(2)).toHaveAttribute('aria-selected', 'true')
    expect(await mainImage.getAttribute('src')).not.toBe(second)

    await page.getByRole('button', { name: 'Previous image' }).click()
    await expect(mainImage).toHaveAttribute('src', second ?? '')

    await page.goBack()
    await expect(page.getByLabel('Search products')).toHaveValue('lamp')
  })
})
