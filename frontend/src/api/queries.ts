import { queryOptions, useQuery } from '@tanstack/react-query'
import { apiClient, unwrap } from './client.ts'

export const healthQuery = queryOptions({
  queryKey: ['health'],
  queryFn: async ({ signal }) => unwrap(await apiClient.GET('/health', { signal })),
})

export function useHealth() {
  return useQuery(healthQuery)
}
