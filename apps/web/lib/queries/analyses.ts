'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { api, type Analysis } from '@/lib/api';

export const analysisKeys = {
  detail: (id: string) => ['analyses', id] as const,
};

export function useStartAnalysis() {
  // A mutation rather than a query: uploading is a side effect the user
  // triggers, and the result is not something to refetch on focus.
  return useMutation({
    mutationFn: (file: File) => api.analyses.start(file),
  });
}

/**
 * Poll one analysis until the pipeline reports it finished.
 *
 * Polling rather than a stream on purpose: the payload is small, a dropped
 * connection recovers by itself on the next tick, and there is no second
 * transport to keep working. It stops the moment the server says `done`, so a
 * finished review costs nothing.
 */
export function useAnalysisProgress(id: string | null, seed?: Analysis) {
  return useQuery({
    queryKey: analysisKeys.detail(id ?? ''),
    queryFn: () => api.analyses.get(id as string),
    enabled: id !== null,
    initialData: seed,
    // 900ms: fast enough that the clause counter moves visibly, slow enough
    // that a 13-clause review is ~30 requests rather than 300.
    refetchInterval: (query) => (query.state.data?.stage === 'done' ? false : 900),
    refetchIntervalInBackground: false,
  });
}
