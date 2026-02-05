import { create } from 'zustand'

interface SyncState {
  runningSyncs: string[]
  addRunningSync: (entityType: string) => void
  removeRunningSync: (entityType: string) => void
}

export const useSyncStore = create<SyncState>((set) => ({
  runningSyncs: [],

  addRunningSync: (entityType: string) =>
    set((state) => ({
      runningSyncs: [...state.runningSyncs, entityType],
    })),

  removeRunningSync: (entityType: string) =>
    set((state) => ({
      runningSyncs: state.runningSyncs.filter((e) => e !== entityType),
    })),
}))
