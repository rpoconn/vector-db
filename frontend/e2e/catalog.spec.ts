import { expect, test } from '@playwright/test'
import { cardCategories } from './support.ts'

const PAGE_SIZE = 24

test.describe('catalog', () => {
  test('landing shows a page of products with loaded thumbnails', async ({ page }) => {
    await page.goto('/')

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('All products')
    const items = page.locator('main ul > li')
    await expect(items).toHaveCount(PAGE_SIZE)
    await expect(items.first().getByRole('heading', { level: 3 })).not.toBeEmpty()
    await expect(items.first().getByText(/^\$\d/)).toBeVisible()

    const thumbnail = items.first().locator('img')
    await expect
      .poll(() => thumbnail.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth))
      .toBeGreaterThan(0)
    await expect(page.getByRole('contentinfo')).toContainText('Amazon Berkeley Objects')
  })

  test('pagination moves between pages and the URL follows', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/^Page 1 of \d+$/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Previous' })).toBeDisabled()

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page).toHaveURL(/[?&]page=2/)
    await expect(page.getByText(/^Page 2 of \d+$/)).toBeVisible()
    await expect(page.locator('main ul > li')).not.toHaveCount(0)

    await page.goBack()
    await expect(page.getByText(/^Page 1 of \d+$/)).toBeVisible()
  })

  test('category filter narrows the grid', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('combobox', { name: 'Category' }).selectOption({ value: 'Lamp' })

    await expect(page).toHaveURL(/[?&]category=Lamp/)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Lamp')
    // Retries while the previous page's placeholder data is still showing.
    await expect.poll(() => cardCategories(page)).toEqual(Array<string>(8).fill('Lamp'))
  })
})
