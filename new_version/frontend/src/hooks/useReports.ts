import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi, publishedReportsApi } from '../services/api'
import type { ReportConversationRequest, ReportSaveRequest, ReportScheduleUpdateRequest, PublishReportRequest } from '../services/api'

export function useReportConverse() {
  return useMutation({
    mutationFn: (data: ReportConversationRequest) => reportsApi.converse(data),
  })
}

export function useReportSave() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ReportSaveRequest) => reportsApi.save(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useReports(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['reports', page, perPage],
    queryFn: () => reportsApi.list(page, perPage),
  })
}

export function useDeleteReport() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (reportId: number) => reportsApi.delete(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useUpdateReportSchedule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ reportId, data }: { reportId: number; data: ReportScheduleUpdateRequest }) =>
      reportsApi.updateSchedule(reportId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useRunReport() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (reportId: number) => reportsApi.run(reportId),
    onSuccess: (_, reportId) => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['reportRuns', reportId] })
    },
  })
}

export function useToggleReportPin() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (reportId: number) => reportsApi.togglePin(reportId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

export function useReportRuns(reportId: number, page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['reportRuns', reportId, page, perPage],
    queryFn: () => reportsApi.listRuns(reportId, page, perPage),
    enabled: !!reportId,
  })
}

export function useReportPromptTemplate() {
  return useQuery({
    queryKey: ['reportPromptTemplate'],
    queryFn: reportsApi.getPromptTemplate,
  })
}

export function useUpdateReportPromptTemplate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (content: string) => reportsApi.updatePromptTemplate(content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reportPromptTemplate'] })
    },
  })
}

// === Published Reports ===

export function usePublishReport() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: PublishReportRequest) => publishedReportsApi.publish(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publishedReports'] })
    },
  })
}

export function usePublishedReports(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['publishedReports', page, perPage],
    queryFn: () => publishedReportsApi.list(page, perPage),
  })
}

export function useDeletePublishedReport() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (pubId: number) => publishedReportsApi.delete(pubId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publishedReports'] })
    },
  })
}

export function useAddPublishedReportLink() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ pubId, data }: { pubId: number; data: { linked_published_report_id: number; label?: string; sort_order?: number } }) =>
      publishedReportsApi.addLink(pubId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publishedReports'] })
    },
  })
}

export function useRemovePublishedReportLink() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ pubId, linkId }: { pubId: number; linkId: number }) =>
      publishedReportsApi.removeLink(pubId, linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publishedReports'] })
    },
  })
}
