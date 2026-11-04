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

/** Increment trailing number in status if present (e.g. GNWL 45 -> GNWL 46, RAC 10 -> RAC 11). */
export function incrementStatusString(status: string): string {
  const trimmed = status.trim();
  const match = trimmed.match(/^(.*?)(\d+)$/);
  if (!match) return status;
  const prefix = match[1];
  const num = parseInt(match[2], 10);
  return `${prefix}${num + 1}`;
}

export interface UsePassengerListReturn {
  rows: PassengerRowState[];
  addRow: () => void;
  duplicateRow: (rowId: string) => void;
  removeRow: (rowId: string) => void;
  updateRow: (rowId: string, updates: Partial<PassengerRowState>) => void;
  setAllRows: (newRows: PassengerInput[]) => void;
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

  const duplicateRow = useCallback((rowId: string) => {
    setRows((prev) => {
      if (prev.length >= MAX_PASSENGERS) return prev;
      const targetIndex = prev.findIndex((r) => r.rowId === rowId);
      if (targetIndex === -1) return prev;
      const target = prev[targetIndex];
      rowCounter += 1;
      const cloned: PassengerRowState = {
        rowId: `passenger-row-${rowCounter}`,
        original_status: incrementStatusString(target.original_status),
        current_status: incrementStatusString(target.current_status),
        current_status_observed_at: target.current_status_observed_at,
        timeUnknown: target.timeUnknown,
      };
      const next = [...prev];
      next.splice(targetIndex + 1, 0, cloned);
      return next;
    });
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

  const setAllRows = useCallback((newRows: PassengerInput[]) => {
    setRows(
      newRows.slice(0, MAX_PASSENGERS).map((input) => {
        rowCounter += 1;
        return {
          rowId: `passenger-row-${rowCounter}`,
          original_status: input.original_status,
          current_status: input.current_status,
          current_status_observed_at: input.current_status_observed_at ?? null,
          timeUnknown: input.current_status_observed_at === null,
        };
      }),
    );
  }, []);

  const resetRows = useCallback(() => {
    setRows([newRow()]);
  }, []);

  return {
    rows,
    addRow,
    duplicateRow,
    removeRow,
    updateRow,
    setAllRows,
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
