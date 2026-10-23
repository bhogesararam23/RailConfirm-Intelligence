'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiFailure, submitPrediction } from '@/lib/api';
import type { PredictionRequest, PredictionResponse } from '@/lib/types';

export type PredictionState = 'idle' | 'loading' | 'success' | 'error';

export interface PredictionFailure {
  message: string;
  kind: ApiFailure['kind'];
  status: number | null;
  code: string | null;
  requestId: string | null;
  /** Server field paths the request failed on, already mapped to form keys. */
  fieldErrors: Record<string, string>;
}

export interface UsePredictionReturn {
  state: PredictionState;
  result: PredictionResponse | null;
  failure: PredictionFailure | null;
  submit: (request: PredictionRequest) => Promise<void>;
  reset: () => void;
}

/**
 * Submits a prediction and holds exactly one in-flight request.
 *
 * `requestSeq` ignores a response that arrives after the user reset or superseded
 * the request, which otherwise repaints a stale result over a cleared form.
 */
export function usePrediction(): UsePredictionReturn {
  const [state, setState] = useState<PredictionState>('idle');
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [failure, setFailure] = useState<PredictionFailure | null>(null);
  const requestSeq = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      requestSeq.current += 1;
    };
  }, []);

  const submit = useCallback(async (request: PredictionRequest) => {
    const seq = ++requestSeq.current;
    setState('loading');
    setResult(null);
    setFailure(null);

    try {
      const response = await submitPrediction(request);
      if (!mounted.current || seq !== requestSeq.current) return;
      setResult(response);
      setState('success');
    } catch (error) {
      if (!mounted.current || seq !== requestSeq.current) return;
      if (error instanceof ApiFailure) {
        setFailure({
          message: error.message,
          kind: error.kind,
          status: error.status,
          code: error.code,
          requestId: error.requestId,
          fieldErrors: error.fieldErrors,
        });
      } else {
        setFailure({
          message:
            error instanceof Error
              ? error.message
              : 'The request could not be completed.',
          kind: 'network',
          status: null,
          code: 'UNEXPECTED_ERROR',
          requestId: null,
          fieldErrors: {},
        });
      }
      setState('error');
    }
  }, []);

  const reset = useCallback(() => {
    requestSeq.current += 1;
    setState('idle');
    setResult(null);
    setFailure(null);
  }, []);

  return { state, result, failure, submit, reset };
}
