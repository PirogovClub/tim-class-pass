import type { Page } from '@playwright/test'

export class Actor {
  constructor(public readonly name: string, private readonly page: Page) {}
  get browseTheWeb(): Page { return this.page }
  async attemptsTo(...tasks: Array<(page: Page) => Promise<void>>) {
    for (const task of tasks) {await task(this.page)}
  }
  async asks<T>(question: (page: Page) => Promise<T>) {
    return question(this.page)
  }
}
