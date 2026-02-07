import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardsApi } from '../services/api'
import type { SelectorCreateRequest, SelectorUpdateRequest } from '../services/api'

export function useDashboardSelectors(dashboardId: number) {
  return useQuery({
    queryKey: ['selectors', dashboardId],
    queryFn: () => dashboardsApi.listSelectors(dashboardId),
    enabled: !!dashboardId,
  })
}

export function useCreateSelector() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ dashboardId, data }: { dashboardId: number; data: SelectorCreateRequest }) =>
      dashboardsApi.createSelector(dashboardId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useUpdateSelector() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      dashboardId,
      selectorId,
      data,
    }: {
      dashboardId: number
      selectorId: number
      data: SelectorUpdateRequest
    }) => dashboardsApi.updateSelector(dashboardId, selectorId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDeleteSelector() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ dashboardId, selectorId }: { dashboardId: number; selectorId: number }) =>
      dashboardsApi.deleteSelector(dashboardId, selectorId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useAddSelectorMapping() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      dashboardId,
      selectorId,
      data,
    }: {
      dashboardId: number
      selectorId: number
      data: {
        dashboard_chart_id: number
        target_column: string
        target_table?: string
        operator_override?: string
      }
    }) => dashboardsApi.addSelectorMapping(dashboardId, selectorId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useRemoveSelectorMapping() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      dashboardId,
      selectorId,
      mappingId,
    }: {
      dashboardId: number
      selectorId: number
      mappingId: number
    }) => dashboardsApi.removeSelectorMapping(dashboardId, selectorId, mappingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useSelectorOptions(dashboardId: number, selectorId: number) {
  return useQuery({
    queryKey: ['selectorOptions', dashboardId, selectorId],
    queryFn: () => dashboardsApi.getSelectorOptions(dashboardId, selectorId),
    enabled: !!dashboardId && !!selectorId,
  })
}

export function useChartColumns(dashboardId: number, dcId: number) {
  return useQuery({
    queryKey: ['chartColumns', dashboardId, dcId],
    queryFn: () => dashboardsApi.getChartColumns(dashboardId, dcId),
    enabled: !!dashboardId && !!dcId,
  })
}

export function useGenerateSelectors() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (dashboardId: number) =>
      dashboardsApi.generateSelectors(dashboardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['selectors'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}
