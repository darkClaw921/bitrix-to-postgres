import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardsApi } from '../services/api'
import type { SelectorCreateRequest, SelectorUpdateRequest, FilterPreviewRequest } from '../services/api'

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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['selectors', variables.dashboardId] })
      queryClient.invalidateQueries({ queryKey: ['dashboard', variables.dashboardId] })
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
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['selectors', variables.dashboardId] })
      queryClient.invalidateQueries({ queryKey: ['dashboard', variables.dashboardId] })
    },
  })
}

export function useDeleteSelector() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ dashboardId, selectorId }: { dashboardId: number; selectorId: number }) =>
      dashboardsApi.deleteSelector(dashboardId, selectorId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['selectors', variables.dashboardId] })
      queryClient.invalidateQueries({ queryKey: ['dashboard', variables.dashboardId] })
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

export function useFilterPreview() {
  return useMutation({
    mutationFn: ({
      dashboardId,
      dcId,
      data,
    }: {
      dashboardId: number
      dcId: number
      data: FilterPreviewRequest
    }) => dashboardsApi.previewFilter(dashboardId, dcId, data),
  })
}
