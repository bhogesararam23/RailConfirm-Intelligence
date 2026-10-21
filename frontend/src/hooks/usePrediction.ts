'use client';

import { useState, useCallback } from 'react';
import { submitPrediction, APIError } from '@/lib/api';
import type { PredictionRequest, PredictionResponse } from '@/lib/types';

type PredictionState = 'idle' | 'loading' | 'success' | 'error';

interface UsePredictionReturn {
  state: PredictionState;
  result: PredictionResponse | null;
  error: string | null;
  errorCode: string | null;
  submit: (request: PredictionRequest) => Promise<void>;
  reset: () => void;
}

/**
 * Hook that manages the full lifecycle of a prediction submission:
 * idle → loading → success | error → idle (via reset).
 *
 * Error messages are user-friendly; technical codes are available separately
 * for display context (e.g., "no_trained_model" maps to an abstention card).
 */
export function usePrediction(): UsePredictionReturn {
  const [state, setState] = useState<PredictionState>('idle');
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const submit = useCallback(async (request: PredictionRequest) => {
    setState('loading');
    setResult(null);
    setError(null);
    setErrorCode(null);

    try {
      const response = await submitPrediction(request);
      setResult(response);
      setState('success');
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.message);
        setErrorCode(err.code);
      } else if (err instanceof Error) {
        setError(err.message);
        setErrorCode('NETWORK_ERROR');
      } else {
        setError('An unexpected error occurred. Please try again.');
        setErrorCode('UNKNOWN');
      }
      setState('error');
    }
  }, []);

  const reset = useCallback(() => {
    setState('idle');
    setResult(null);
    setError(null);
    setErrorCode(null);
  }, []);

  return { state, result, error, errorCode, submit, reset };
}
