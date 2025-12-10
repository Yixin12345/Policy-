import { create } from 'zustand'

type ResultsTab = 'fields' | 'tables' | 'canonical' | 'raw'

type ViewerState = {
  jobId: string | null
  currentPage: number
  totalPages: number
  selectedTab: ResultsTab
  zoom: number
  showBoundingBoxes: boolean
  setJobId: (jobId: string | null, totalPages?: number) => void
  setCurrentPage: (page: number) => void
  setTotalPages: (total: number) => void
  setSelectedTab: (tab: ResultsTab) => void
  setZoom: (zoom: number) => void
  toggleBoundingBoxes: () => void
}

export const useViewerStore = create<ViewerState>((set) => ({
  jobId: null,
  currentPage: 1,
  totalPages: 0,
  selectedTab: 'fields',
  zoom: 1,
  showBoundingBoxes: false,
  setJobId: (jobId, totalPages) =>
    set(() => ({
      jobId,
      currentPage: 1,
      totalPages: totalPages ?? 0,
      selectedTab: 'fields'
    })),
  setCurrentPage: (page) => set({ currentPage: page }),
  setTotalPages: (total) => set({ totalPages: total }),
  setSelectedTab: (tab) => set({ selectedTab: tab }),
  setZoom: (zoom) => set({ zoom }),
  toggleBoundingBoxes: () =>
    set((state) => ({ showBoundingBoxes: !state.showBoundingBoxes }))
}))

export type { ResultsTab }
