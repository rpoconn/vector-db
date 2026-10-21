import { expect, test } from '@playwright/test'
import {
  PASSWORD,
  emailedLink,
  register,
  registerVerified,
  signIn,
  submitSignIn,
  uniqueEmail,
} from './support.ts'

const NEW_PASSWORD = 'staple-battery-horse'

test.describe('accounts', () => {
  test('register, confirm the address, sign in, stay signed in, sign out', async ({
    page,
    request,
  }) => {
    const email = uniqueEmail('new')
    await register(page, email)

    // Signing in before confirming is refused with a way to resend the link.
    await page.goto('/login')
    await submitSignIn(page, email, PASSWORD)
    await expect(page.getByRole('alert')).toContainText(/confirm your e-mail/i)
    await expect(page.getByRole('button', { name: 'Send a new link' })).toBeVisible()

    await page.goto(await emailedLink(request, email, '/verify-email'))
    await expect(page.getByRole('heading', { name: 'E-mail confirmed' })).toBeVisible()

    await page.getByRole('main').getByRole('link', { name: 'Sign in' }).click()
    await submitSignIn(page, email, PASSWORD)
    await expect(page).toHaveURL(/\/$/)
    const account = page.getByRole('navigation', { name: 'Account' })
    await expect(account).toContainText(email)

    await page.reload()
    await expect(account).toContainText(email)

    await account.getByRole('button', { name: 'Sign out' }).click()
    await expect(account.getByRole('link', { name: 'Sign in' })).toBeVisible()
  })

  test('signing in from a product page returns there', async ({ page, request }) => {
    const email = uniqueEmail('redirect')
    await registerVerified(page, request, email)

    await page.goto('/products/DEMO0001')
    await page.getByRole('link', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/login\?redirect=/)
    await submitSignIn(page, email, PASSWORD)

    await expect(page).toHaveURL(/\/products\/DEMO0001$/)
    await expect(page.getByRole('navigation', { name: 'Account' })).toContainText(email)
  })

  test('forgot password e-mails a reset link that sets a new password', async ({
    page,
    request,
  }) => {
    const email = uniqueEmail('reset')
    await registerVerified(page, request, email)

    await page.goto('/forgot-password')
    await page.getByLabel('E-mail').fill(email)
    await page.getByRole('button', { name: 'Send reset link' }).click()
    await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible()

    await page.goto(await emailedLink(request, email, '/reset-password'))
    await page.getByLabel(/^New password/).fill(NEW_PASSWORD)
    await page.getByLabel('Confirm new password').fill(NEW_PASSWORD)
    await page.getByRole('button', { name: 'Change password' }).click()
    await expect(page.getByRole('heading', { name: 'Password updated' })).toBeVisible()

    await page.goto('/login')
    await submitSignIn(page, email, PASSWORD)
    await expect(page.getByRole('alert')).toContainText(/password/i)

    await signIn(page, email, NEW_PASSWORD)
  })

  test('wrong credentials and duplicate registration show friendly errors', async ({
    page,
    request,
  }) => {
    const email = uniqueEmail('errors')
    await registerVerified(page, request, email)

    await page.goto('/login')
    await submitSignIn(page, email, 'not-the-password')
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByRole('navigation', { name: 'Account' })).not.toContainText(email)

    await page.goto('/register')
    await page.getByLabel('E-mail').fill(email)
    await page.getByLabel(/^Password/).fill(PASSWORD)
    await page.getByLabel('Confirm password').fill(PASSWORD)
    await page.getByRole('button', { name: 'Create account' }).click()
    await expect(page.getByRole('alert')).toContainText(/already/i)
  })
})
