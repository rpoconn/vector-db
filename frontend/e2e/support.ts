import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const PASSWORD = 'correct-horse-battery'

/** Served by the backend only under `APP_ENV=test`; reached through the Vite `/api` proxy. */
const MAILBOX_PATH = '/api/_test/mailbox'

interface MailboxMessage {
  to: string
  subject: string
  body: string
}

function isMailboxMessage(value: unknown): value is MailboxMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    'to' in value &&
    typeof value.to === 'string' &&
    'body' in value &&
    typeof value.body === 'string'
  )
}

/** The category line (first paragraph) of every product card in the grid. */
export function cardCategories(page: Page): Promise<(string | undefined)[]> {
  return page
    .locator('main ul > li')
    .evaluateAll((cards) => cards.map((card) => card.querySelector('p')?.textContent ?? undefined))
}

/** A fresh address per test, so parallel specs never share an account. */
export function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
}

/**
 * The path and query of the latest link to `path` e-mailed to `to`, e.g.
 * `/reset-password?token=…`. Polls, because the app e-mails after answering the request.
 */
export async function emailedLink(
  request: APIRequestContext,
  to: string,
  path: string,
): Promise<string> {
  const pattern = new RegExp(`https?://[^\\s]*(${path}\\?token=[\\w.-]+)`)
  let link: string | undefined
  await expect
    .poll(async () => {
      const response = await request.get(MAILBOX_PATH, { params: { to } })
      const body: unknown = await response.json()
      const messages = Array.isArray(body) ? body.filter(isMailboxMessage) : []
      link = messages.map((message) => pattern.exec(message.body)?.[1]).findLast(Boolean)
      return link
    })
    .toBeDefined()
  if (link === undefined) {
    throw new Error(`No link to ${path} was e-mailed to ${to}`)
  }
  return link
}

export async function register(page: Page, email: string, password = PASSWORD): Promise<void> {
  await page.goto('/register')
  await page.getByLabel('E-mail').fill(email)
  await page.getByLabel(/^Password/).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible()
}

/** Registers and confirms the address, leaving the browser signed out. */
export async function registerVerified(
  page: Page,
  request: APIRequestContext,
  email: string,
  password = PASSWORD,
): Promise<void> {
  await register(page, email, password)
  await page.goto(await emailedLink(request, email, '/verify-email'))
  await expect(page.getByRole('heading', { name: 'E-mail confirmed' })).toBeVisible()
}

/** Submits the sign-in form from wherever the page currently is. */
export async function submitSignIn(page: Page, email: string, password: string): Promise<void> {
  await page.getByLabel('E-mail').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
}

export async function signIn(page: Page, email: string, password = PASSWORD): Promise<void> {
  await page.goto('/login')
  await submitSignIn(page, email, password)
  await expect(page.getByRole('navigation', { name: 'Account' })).toContainText(email)
}
