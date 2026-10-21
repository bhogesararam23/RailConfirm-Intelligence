'use client';

import { useState, useCallback } from 'react';
import type { PassengerInput } from '@/lib/types';

const MAX_PASSENGERS = 6;

const emptyPassenger = (): PassengerInput => ({
  original_status: '',
  current_status: '',
  current_status_observed_at: undefined,
  status_time_unknown: false,
});

interface UsePassengerListReturn {
  passengers: PassengerInput[];
  addPassenger: () => void;
  removePassenger: (index: number) => void;
  updatePassenger: (index: number, updates: Partial<PassengerInput>) => void;
  canAddMore: boolean;
}

/**
 * Manages the list of passenger rows in the prediction form.
 * Enforces a maximum of MAX_PASSENGERS rows.
 * Always starts with one empty passenger row.
 */
export function usePassengerList(): UsePassengerListReturn {
  const [passengers, setPassengers] = useState<PassengerInput[]>([
    emptyPassenger(),
  ]);

  const addPassenger = useCallback(() => {
    setPassengers((prev) => {
      if (prev.length >= MAX_PASSENGERS) return prev;
      return [...prev, emptyPassenger()];
    });
  }, []);

  const removePassenger = useCallback((index: number) => {
    setPassengers((prev) => {
      if (prev.length <= 1) {
        // Reset to a single empty row rather than removing all
        return [emptyPassenger()];
      }
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  const updatePassenger = useCallback(
    (index: number, updates: Partial<PassengerInput>) => {
      setPassengers((prev) =>
        prev.map((p, i) => (i === index ? { ...p, ...updates } : p)),
      );
    },
    [],
  );

  return {
    passengers,
    addPassenger,
    removePassenger,
    updatePassenger,
    canAddMore: passengers.length < MAX_PASSENGERS,
  };
}
