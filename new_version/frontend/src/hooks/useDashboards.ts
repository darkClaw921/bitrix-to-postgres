import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardsApi } from '../services/api'
import type {
  DashboardPublishRequest,
  DashboardUpdateRequest,
  DashboardLayoutUpdateRequest,
  ChartOverrideUpdateRequest,
  IframeCodeRequest,
} from '../services/api'

export function usePublishDashboard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: DashboardPublishRequest) => dashboardsApi.publish(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] })
    },
  })
}

export function useDashboardList(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['dashboards', page, perPage],
    queryFn: () => dashboardsApi.list(page, perPage),
  })
}

export function useDashboard(id: number) {
  return useQuery({
    queryKey: ['dashboard', id],
    queryFn: () => dashboardsApi.get(id),
    enabled: !!id,
  })
}

export function useUpdateDashboard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: DashboardUpdateRequest }) =>
      dashboardsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDeleteDashboard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => dashboardsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboards'] })
    },
  })
}

export function useUpdateDashboardLayout() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: DashboardLayoutUpdateRequest }) =>
      dashboardsApi.updateLayout(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard', variables.id] })
    },
  })
}

export function useUpdateChartOverride() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      dashboardId,
      dcId,
      data,
    }: {
      dashboardId: number
      dcId: number
      data: ChartOverrideUpdateRequest
    }) => dashboardsApi.updateChartOverride(dashboardId, dcId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useRemoveChartFromDashboard() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ dashboardId, dcId }: { dashboardId: number; dcId: number }) =>
      dashboardsApi.removeChart(dashboardId, dcId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['dashboards'] })
    },
  })
}

export function useChangeDashboardPassword() {
  return useMutation({
    mutationFn: (id: number) => dashboardsApi.changePassword(id),
  })
}

export function useIframeCode() {
  return useMutation({
    mutationFn: (data: IframeCodeRequest) => dashboardsApi.getIframeCode(data),
  })
}
