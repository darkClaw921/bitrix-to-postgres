import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { chartsApi, schemaApi } from '../services/api'
import type { ChartGenerateRequest, ChartSaveRequest, ChartDisplayConfig, SchemaDescriptionUpdateRequest } from '../services/api'

export function useGenerateChart() {
  return useMutation({
    mutationFn: (data: ChartGenerateRequest) => chartsApi.generate(data),
  })
}

export function useSaveChart() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ChartSaveRequest) => chartsApi.save(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] })
    },
  })
}

export function useSavedCharts(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['savedCharts', page, perPage],
    queryFn: () => chartsApi.list(page, perPage),
  })
}

export function useChartData(chartId: number) {
  return useQuery({
    queryKey: ['chartData', chartId],
    queryFn: () => chartsApi.getData(chartId),
    enabled: !!chartId,
  })
}

export function useDeleteChart() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (chartId: number) => chartsApi.delete(chartId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] })
    },
  })
}

export function useToggleChartPin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (chartId: number) => chartsApi.togglePin(chartId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] })
    },
  })
}

export function useUpdateChartConfig() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ chartId, config }: { chartId: number; config: Partial<ChartDisplayConfig> }) =>
      chartsApi.updateConfig(chartId, config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savedCharts'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useSchemaDescription() {
  return useQuery({
    queryKey: ['schemaDescription'],
    queryFn: schemaApi.describe,
    enabled: false, // manual trigger via refetch()
  })
}

export function useSchemaDescribeRaw() {
  return useQuery({
    queryKey: ['schemaDescribeRaw'],
    queryFn: schemaApi.describeRaw,
    enabled: false, // manual trigger via refetch()
  })
}

export function useSchemaHistory() {
  return useQuery({
    queryKey: ['schemaHistory'],
    queryFn: schemaApi.getHistory,
  })
}

export function useUpdateSchemaDescription() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ descId, data }: { descId: number; data: SchemaDescriptionUpdateRequest }) =>
      schemaApi.update(descId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schemaDescription'] })
      queryClient.invalidateQueries({ queryKey: ['schemaHistory'] })
    },
  })
}

export function useSchemaTables() {
  return useQuery({
    queryKey: ['schemaTables'],
    queryFn: schemaApi.tables,
  })
}

export function useChartPromptTemplate() {
  return useQuery({
    queryKey: ['chartPromptTemplate'],
    queryFn: chartsApi.getPromptTemplate,
  })
}

export function useUpdateChartPromptTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (content: string) => chartsApi.updatePromptTemplate(content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chartPromptTemplate'] })
    },
  })
}
