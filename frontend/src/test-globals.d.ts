declare module 'vitest' {
  export const describe: (name: string, fn: () => void) => void
  export const it: (name: string, fn: () => void) => void
  export const beforeEach: (fn: () => void | Promise<void>) => void
  export const afterEach: (fn: () => void | Promise<void>) => void
  export const vi: any
  export const expect: (value: unknown) => {
    toBe: (expected: unknown) => void
    toContain: (expected: string) => void
  }
}
