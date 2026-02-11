import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { syncApi, statusApi, referencesApi, type BitrixFilter } from '../services/api'

export function useSyncConfig() {
  return useQuery({
    queryKey: ['syncConfig'],
    queryFn: syncApi.getConfig,
  })
}

export function useSyncStatus() {
  return useQuery({
    queryKey: ['syncStatus'],
    queryFn: syncApi.getStatus,
    refetchInterval: 5000, // Poll every 5 seconds
  })
}

export function useRunningSyncs() {
  return useQuery({
    queryKey: ['runningSyncs'],
    queryFn: syncApi.getRunningSyncs,
    refetchInterval: 2000, // Poll every 2 seconds
  })
}

export function useSyncHistory(params?: {
  page?: number
  per_page?: number
  entity_type?: string
  status?: string
  sync_type?: string
}) {
  return useQuery({
    queryKey: ['syncHistory', params],
    queryFn: () => statusApi.getHistory(params),
    refetchInterval: 10000, // Refresh every 10 seconds
  })
}

export function useSyncStats() {
  return useQuery({
    queryKey: ['syncStats'],
    queryFn: statusApi.getStats,
    refetchInterval: 30000, // Refresh every 30 seconds
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: statusApi.getHealth,
    refetchInterval: 10000, // Check every 10 seconds
  })
}

export function useUpdateSyncConfig() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: syncApi.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncConfig'] })
    },
  })
}

export function useStartSync() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ entity, syncType, filter }: { entity: string; syncType: 'full' | 'incremental'; filter?: BitrixFilter }) =>
      syncApi.startSync(entity, syncType, filter),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
      queryClient.invalidateQueries({ queryKey: ['runningSyncs'] })
    },
  })
}

// === Reference hooks ===

export function useReferenceStatus() {
  return useQuery({
    queryKey: ['referenceStatus'],
    queryFn: referencesApi.getStatus,
    refetchInterval: 5000,
  })
}

export function useStartRefSync() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (refName: string) => referencesApi.syncOne(refName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['referenceStatus'] })
    },
  })
}

export function useStartAllRefSync() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => referencesApi.syncAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['referenceStatus'] })
    },
  })
}
