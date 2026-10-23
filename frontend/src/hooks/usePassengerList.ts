'use client';

import { useCallback, useState } from 'react';
import { MAX_PASSENGERS } from '@/lib/types';
import type { PassengerInput } from '@/lib/types';

export interface PassengerRowState extends PassengerInput {
  /**
   * Stable row identity. Rows are keyed by this rather than by array index, so
   * removing a middle row cannot make React reuse the wrong input's state — and so
   * per-row validation errors keep pointing at the row the user is looking at.
   */
  rowId: string;
  /** True when the user does not know when the status was observed. */
  timeUnknown: boolean;
}

export const MAXROWS = MAX_PASSENGERS;

let rowCounter = 0;

function newRow(): PassengerRowState {
  rowCounter += 1;
  return {
    rowId: `passenger-row-${rowCounter}`,
    original_status: '',
    current_status: '',
    current_status_observed_at: null,
    timeUnknown: true,
  };
}

export interface UsePassengerListReturn {
  rows: PassengerRowState[];
  addRow: () => void;
  removeRow: (rowId: string) => void;
  updateRow: (rowId: string, updates: Partial<PassengerRowState>) => void;
  resetRows: () => void;
  canAddMore: boolean;
  limitReached: boolean;
}

/** Passenger rows for the form, capped at the server's documented limit. */
export function usePassengerList(): UsePassengerListReturn {
  const [rows, setRows] = useState<PassengerRowState[]>(() => [newRow()]);

  const addRow = useCallback(() => {
    setRows((prev) => (prev.length >= MAX_PASSENGERS ? prev : [...prev, newRow()]));
  }, []);

  const removeRow = useCallback((rowId: string) => {
    setRows((prev) => {
      const next = prev.filter((row) => row.rowId !== rowId);
      return next.length > 0 ? next : [newRow()];
    });
  }, []);

  const updateRow = useCallback(
    (rowId: string, updates: Partial<PassengerRowState>) => {
      setRows((prev) =>
        prev.map((row) => (row.rowId === rowId ? { ...row, ...updates } : row)),
      );
    },
    [],
  );

  const resetRows = useCallback(() => {
    setRows([newRow()]);
  }, []);

  return {
    rows,
    addRow,
    removeRow,
    updateRow,
    resetRows,
    canAddMore: rows.length < MAX_PASSENGERS,
    limitReached: rows.length >= MAX_PASSENGERS,
  };
}

/** Convert rows into the request payload, dropping the UI-only identity. */
export function toPassengerInputs(rows: PassengerRowState[]): PassengerInput[] {
  return rows.map((row) => ({
    original_status: row.original_status.trim(),
    current_status: row.current_status.trim(),
    current_status_observed_at: row.timeUnknown
      ? null
      : (row.current_status_observed_at ?? null),
  }));
}
