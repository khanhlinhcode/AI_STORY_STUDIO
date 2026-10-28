"use client";

import { create } from "zustand";

interface StudioState {
  selectedSceneId?: string;
  compareMode: boolean;
  setSelectedScene: (id: string) => void;
  toggleCompare: () => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  compareMode: false,
  setSelectedScene: (selectedSceneId) => set({ selectedSceneId }),
  toggleCompare: () => set((state) => ({ compareMode: !state.compareMode })),
}));

