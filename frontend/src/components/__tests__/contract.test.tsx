/**
 * Contract rendering tests.
 *
 * These exist because the frontend previously declared a response shape the
 * backend never sends (`observed_status`) and nothing caught it: type-checking
 * passed, ESLint passed and the build passed while observed statuses were never
 * displayed and abstentions showed the wrong explanation.
 *
 * The payload builders below are copied field-for-field from
 * backend/railconfirm/api/v1/schemas.py. If the backend changes, these fixtures
 * and docs/architecture/API_CONTRACT.md are where the mismatch shows up.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PredictionResult } from '@/components/prediction/PredictionResult';
import { PassengerOutcomeCard } from '@/components/prediction/PassengerOutcomeCard';
import { GroupOutcomeCard } from '@/components/prediction/GroupOutcomeCard';
import { PassengerList } from '@/components/prediction/PassengerList';
import { AbstentionCard } from '@/components/ui/AbstentionCard';
import { ProbabilityBar } from '@/components/ui/ProbabilityBar';
import type { GroupOutcome, PassengerOutcome, PredictionResponse } from '@/lib/types';

// Link needs a router context that does not exist under jsdom; a plain anchor keeps
// the assertion about the href, which is the part the contract defines.
vi.mock('next/link', () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

const supportedOutcome: PassengerOutcome = {
  passenger_id: '8f4a0f4c-0000-0000-0000-000000000001',
  original_status: 'GNWL/45',
  original_status_normalized: 'WL',
  current_status: 'GNWL/12',
  current_status_normalized: 'WL',
  p_cnf: 0.6454545,
  p_rac: 0.190909,
  p_wl: 0.1000001,
  p_cancelled: 0.0545454,
  p_other: 0.0090909,
  is_supported: true,
  abstention_reason: null,
  basis: 'cohort=SL/GN/WL n=105 exact_status_match=true',
  parse_warnings: [],
};

const abstainingOutcome: PassengerOutcome = {
  ...supportedOutcome,
  passenger_id: '...0002',
  current_status: 'CK',
  current_status_normalized: 'UNKNOWN',
  p_cnf: null,
  p_rac: null,
  p_wl: null,
  p_cancelled: null,
  p_other: null,
  is_supported: false,
  abstention_reason: 'no_approved_data',
  basis: null,
  parse_warnings: ['current_status: Status family \'CK\' is not verified'],
};

const group: GroupOutcome = {
  p_all_cnf: 0.4166,
  p_all_cnf_or_rac: 0.6666,
  p_at_least_one_wl: 0.2,
  method: 'independence_baseline',
  assumptions: 'Assumes passenger confirmation outcomes are statistically independent.',
  is_supported: true,
  abstention_reason: null,
};

const secondSupportedOutcome: PassengerOutcome = {
  ...supportedOutcome,
  passenger_id: '8f4a0f4c-0000-0000-0000-000000000002',
};

const response = (overrides: Partial<PredictionResponse> = {}): PredictionResponse => ({
  prediction_id: 'a1b2c3d4-0000-0000-0000-000000000009',
  target: 'final_chart_cnf',
  target_definition: 'Probability of each final-chart outcome for each passenger.',
  prediction_at: '2026-12-10T08:00:00+05:30',
  created_at: '2026-12-10T02:30:00Z',
  model_version: 'fixture_v1',
  registry_status: 'ready',
  feature_schema_version: '2.0.0',
  evidence_coverage: 'sufficient',
  is_supported: true,
  passenger_count: 1,
  passenger_outcomes: [supportedOutcome],
  group_outcome: null,
  limitations: ['RailConfirm is an independent research tool and not an official IRCTC service.'],
  warnings: [],
  outcome_classes: 'CNF, RAC, WL, CANCELLED, OTHER — mutually exclusive and exhaustive.',
  stored: false,
  report_url: null,
  retention_expires_at: null,
  ...overrides,
});

describe('PassengerOutcomeCard', () => {
  it('shows both observed statuses, which the old shape never rendered', () => {
    const { container } = render(<PassengerOutcomeCard index={0} outcome={supportedOutcome} />);
    const text = container.textContent ?? '';
    expect(text).toContain('As booked:');
    expect(text).toContain('Observed now:');
    expect(text).toContain('GNWL/45');
    expect(text).toContain('GNWL/12');
  });

  it('renders the evidence cohort and sample size', () => {
    render(<PassengerOutcomeCard index={0} outcome={supportedOutcome} />);
    expect(screen.getByText(/105 historical records/)).toBeInTheDocument();
  });

  it('surfaces parse warnings from the server', () => {
    render(<PassengerOutcomeCard index={0} outcome={abstainingOutcome} />);
    expect(screen.getByText(/is not verified/)).toBeInTheDocument();
  });

  it('shows an abstention with its own reason, not a zeroed distribution', () => {
    render(<PassengerOutcomeCard index={0} outcome={abstainingOutcome} />);
    expect(screen.getByRole('status', { name: 'Estimate not available' })).toBeInTheDocument();
    expect(screen.getByText(/no historical dataset has been approved/i)).toBeInTheDocument();
    expect(screen.queryByText(/64\.5%/)).not.toBeInTheDocument();
  });
});

describe('ProbabilityBar', () => {
  it('renders all five outcome classes so the legend is a complete breakdown', () => {
    const { container } = render(
      <ProbabilityBar
        p_cnf={0.6454}
        p_rac={0.19}
        p_wl={0.1}
        p_cancelled={0.0545}
        p_other={0.0091}
      />,
    );
    const text = container.textContent ?? '';
    for (const label of [
      'Confirmed berth',
      'RAC accommodation',
      'Remains waitlisted',
      'Cancelled',
      'Other outcome',
    ]) {
      expect(text).toContain(label);
    }
    // Every class carries a value, and they add up to the whole distribution.
    expect(text).toContain('Cancelled: 5.5%');
    expect(text).toContain('Other outcome: 0.9%');
  });

  it('shows a dash rather than a fabricated zero for a missing class', () => {
    const { container } = render(
      <ProbabilityBar p_cnf={0.5} p_rac={null} p_wl={0.5} p_cancelled={0} p_other={0} />,
    );
    const text = container.textContent ?? '';
    expect(text).toContain('RAC accommodation: —');
    expect(text).toContain('Cancelled: 0.0%');
  });

  it('describes the whole distribution to assistive technology', () => {
    const { getByRole } = render(
      <ProbabilityBar p_cnf={1} p_rac={0} p_wl={0} p_cancelled={0} p_other={0} />,
    );
    const bar = getByRole('img');
    expect(bar.getAttribute('aria-label')).toContain('Cancelled: 0.0%');
    expect(bar.getAttribute('aria-label')).toContain('Other outcome: 0.0%');
  });
});

describe('PredictionResult', () => {
  it('publishes the provenance a reader needs to judge the number', () => {
    render(<PredictionResult result={response()} onReset={vi.fn()} />);
    expect(screen.getByText('fixture_v1')).toBeInTheDocument();
    expect(screen.getByText('ready')).toBeInTheDocument();
    expect(screen.getByText('2.0.0')).toBeInTheDocument();
    expect(screen.getByText(/Confirmed berth at final chart preparation/)).toBeInTheDocument();
    expect(screen.getByText(/Every passenger has an estimate/)).toBeInTheDocument();
  });

  it('labels a mixed group as partial rather than abstaining', () => {
    const partial = response({
      evidence_coverage: 'partial',
      is_supported: true,
      passenger_count: 2,
      passenger_outcomes: [supportedOutcome, abstainingOutcome],
    });
    render(<PredictionResult result={partial} onReset={vi.fn()} />);
    expect(screen.getByText(/Some passengers have estimates/)).toBeInTheDocument();
    expect(screen.getByText(/1 of 2 passengers have an estimate/)).toBeInTheDocument();
  });

  it('renders the group card only when the backend computed one', () => {
    render(<PredictionResult result={response()} onReset={vi.fn()} />);
    expect(screen.queryByText(/Group outcomes/)).not.toBeInTheDocument();

    render(
      <PredictionResult
        result={response({
          passenger_count: 2,
          passenger_outcomes: [supportedOutcome, secondSupportedOutcome],
          group_outcome: group,
        })}
        onReset={vi.fn()}
      />,
    );
    expect(screen.getByText(/Group outcomes \(2 passengers\)/)).toBeInTheDocument();
  });

  it('shows limitations and the outcome class statement', () => {
    render(<PredictionResult result={response()} onReset={vi.fn()} />);
    expect(screen.getByText(/not an official IRCTC service/)).toBeInTheDocument();
    expect(screen.getByText(/mutually exclusive and exhaustive/)).toBeInTheDocument();
  });

  it('agrees the count sentence with a single passenger', () => {
    const { container } = render(<PredictionResult result={response()} onReset={vi.fn()} />);
    expect(container.textContent).toContain('1 of 1 passenger has an estimate.');
  });

  it('offers a reopen link only when the backend kept the report', () => {
    const kept = render(
      <PredictionResult
        result={response({
          stored: true,
          report_url: '/v1/predictions/a1b2c3d4-0000-0000-0000-000000000009',
          retention_expires_at: '2026-12-17T02:30:00Z',
        })}
        onReset={vi.fn()}
      />,
    );
    const link = kept.getByRole('link', { name: 'this report' });
    expect(link).toHaveAttribute('href', '/prediction/a1b2c3d4-0000-0000-0000-000000000009');
    expect(kept.container.textContent).toContain('Kept on this machine.');
    expect(kept.container.textContent).toContain('retrievable until');
    kept.unmount();

    const notKept = render(<PredictionResult result={response()} onReset={vi.fn()} />);
    expect(notKept.queryByRole('link', { name: 'this report' })).not.toBeInTheDocument();
    expect(notKept.container.textContent).not.toContain('Kept on this machine.');
  });

  it('never claims a report was kept from the request alone', () => {
    // A caller that asked to persist but was refused must not see a saved banner.
    const refused = response({
      stored: false,
      report_url: null,
      retention_expires_at: null,
      limitations: [
        'This server keeps no prediction history (RAILCONFIRM_PERSIST_PREDICTIONS is not enabled), so the report was not stored.',
      ],
    });
    const { container } = render(<PredictionResult result={refused} onReset={vi.fn()} />);
    expect(container.textContent).not.toContain('Kept on this machine.');
    expect(container.textContent).toContain('keeps no prediction history');
  });

  it('uses the plural form for a group', () => {
    const { container } = render(
      <PredictionResult
        result={response({
          passenger_count: 2,
          passenger_outcomes: [supportedOutcome, secondSupportedOutcome],
          group_outcome: group,
        })}
        onReset={vi.fn()}
      />,
    );
    expect(container.textContent).toContain('2 of 2 passengers have an estimate.');
    expect(container.textContent).toContain('Group outcomes (2 passengers)');
  });
});

describe('GroupOutcomeCard', alwaysVisibleAssumptions);

function alwaysVisibleAssumptions() {
  it('states the independence assumption next to the numbers', () => {
    render(<GroupOutcomeCard group={group} passengerCount={2} />);
    expect(screen.getByText(/statistically independent/)).toBeInTheDocument();
    expect(screen.getByText(/Independence baseline \(approximation\)/)).toBeInTheDocument();
    expect(screen.getByText(/do not sum to 100%/)).toBeInTheDocument();
  });

  it('keeps the assumption visible when it abstains', () => {
    const { container } = render(
      <GroupOutcomeCard
        group={{
          ...group,
          p_all_cnf: null,
          p_all_cnf_or_rac: null,
          p_at_least_one_wl: null,
          method: 'insufficient_data',
          is_supported: false,
          abstention_reason: 'unknown_status',
        }}
        passengerCount={2}
      />,
    );
    const text = container.textContent ?? '';
    expect(text).toMatch(/statistically independent/);
    expect(text).toMatch(/Reason code: unknown_status/);
    // An abstaining group shows no probabilities at all, not zeros.
    expect(text).not.toMatch(/\d+\.\d%/);
  });

  it('renders confirmed berths distribution when p_at_least_k_cnf is provided', () => {
    render(
      <GroupOutcomeCard
        group={{
          ...group,
          p_at_least_k_cnf: { 1: 0.9, 2: 0.4 },
        }}
        passengerCount={2}
      />,
    );
    expect(screen.getByText(/Confirmed berths distribution/)).toBeInTheDocument();
    expect(screen.getByText(/At least 1 passenger/)).toBeInTheDocument();
    expect(screen.getByText(/At least 2 passengers/)).toBeInTheDocument();
    expect(screen.getByText('90.0%')).toBeInTheDocument();
    expect(screen.getByText('40.0%')).toBeInTheDocument();
  });

  it('renders queue-clearing comonotonic bound method label', () => {
    render(
      <GroupOutcomeCard
        group={{
          ...group,
          method: 'queue_dependent_comonotonic',
        }}
        passengerCount={2}
      />,
    );
    expect(screen.getByText(/Queue-clearing comonotonic bound/)).toBeInTheDocument();
  });
}

describe('AbstentionCard', () => {
  it.each([
    ['no_trained_model', /no validated model has been promoted/i],
    ['model_artifact_invalid', /failed validation/i],
    ['unsupported_status', /outside the population/i],
    ['insufficient_sample', /too few matching historical records/i],
  ] as const)('explains %s distinctly', (reason, expected) => {
    render(<AbstentionCard reason={reason} />);
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it('admits an unknown reason instead of showing the wrong explanation', () => {
    render(<AbstentionCard reason={'future_reason' as never} />);
    expect(screen.getByText(/does not recognise/i)).toBeInTheDocument();
    expect(screen.getByText(/future_reason/)).toBeInTheDocument();
  });
});

describe('PassengerList', () => {
  const rows = [
    {
      rowId: 'row-1',
      original_status: '',
      current_status: '',
      current_status_observed_at: null,
      timeUnknown: true,
    },
  ];

  it('labels every input and links its error', async () => {
    render(
      <PassengerList
        rows={rows}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
        onChange={vi.fn()}
        limitReached={false}
        errors={{ 0: { original_status: 'status as booked is required.' } }}
      />,
    );
    const input = screen.getByLabelText('Status as booked');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'row-1-original-error');
  });

  it('keeps the add control visible at the limit and says why it is disabled', async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    render(
      <PassengerList
        rows={rows}
        onAdd={onAdd}
        onRemove={vi.fn()}
        onChange={vi.fn()}
        limitReached
      />,
    );
    const button = screen.getByRole('button', { name: '+ Add passenger' });
    expect(button).toBeDisabled();
    expect(screen.getByText(/maximum for one booking group/)).toBeInTheDocument();
    await user.click(button).catch(() => undefined);
    expect(onAdd).not.toHaveBeenCalled();
  });
});
