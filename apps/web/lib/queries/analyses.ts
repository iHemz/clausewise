'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export const analysisKeys = {
  detail: (id: string) => ['analyses', id] as const,
};

export function useAnalyzeContract() {
  // A mutation rather than a query: uploading is a side effect the user
  // triggers, and the result is not something to refetch on focus.
  return useMutation({
    mutationFn: (file: File) => api.analyses.analyze(file),
  });
}

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: analysisKeys.detail(id),
    queryFn: () => api.analyses.get(id),
  });
}
