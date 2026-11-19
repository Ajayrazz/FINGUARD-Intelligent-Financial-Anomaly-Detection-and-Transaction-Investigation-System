import type { RiskAssessmentDetail } from '../../api/types'
import { RiskBadge } from './RiskBadge'
import { COMPONENT_LABEL, COMPONENT_ORDER } from './riskLabels'

/** Per-component value, weight and contribution; unavailable components are named with the reason, never shown as 0. */
export function BreakdownTable({ a }: { a: RiskAssessmentDetail }) {
  return (
    <div>
      <p className="text-sm">
        {a.overall_score === null ? (
          <span>Not scored: {a.policy === 'strict' ? 'a signal is missing and the strict policy refuses to guess.' : 'no signal was available.'}</span>
        ) : (
          <>
            <span className="text-3xl font-semibold tabular-nums">{a.overall_score.toFixed(1)}</span> <RiskBadge category={a.category} />
            <span className="text-slate-600"> · signal coverage {(a.weight_coverage * 100).toFixed(0)}% · config v{a.config_version} · algorithm {a.algorithm_version} · policy {a.policy}</span>
          </>
        )}
      </p>
      {a.low_coverage && (
        <p role="note" className="mt-1 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          Low coverage: fewer than half of the weighted signals were available, so the score rests on little evidence.
          {a.capped && ' It would have been Critical but is held at High until an analyst reviews it.'}
        </p>
      )}
      <table className="mt-2 w-full text-left text-sm">
        <caption className="sr-only">Components of the risk score</caption>
        <thead className="border-b border-slate-300 text-slate-600"><tr><th className="py-1">Signal</th><th className="text-right">Value</th><th className="text-right">Weight</th><th className="text-right">Contribution</th><th className="pl-4">Note</th></tr></thead>
        <tbody>
          {COMPONENT_ORDER.map((k) => {
            const c = a.components[k]
            return (
              <tr key={k} className="border-b border-slate-100 align-top">
                <td className="py-1"><span className="font-medium">{COMPONENT_LABEL[k].name}</span><br /><span className="text-xs text-slate-500">{COMPONENT_LABEL[k].meaning}</span></td>
                {c.value !== null ? (
                  <>
                    <td className="text-right tabular-nums">{c.value.toFixed(0)}</td>
                    <td className="text-right tabular-nums">{(c.weight * 100).toFixed(0)}%</td>
                    <td className="text-right tabular-nums">{c.contribution !== null ? c.contribution.toFixed(1) : '—'}</td>
                    <td className="pl-4 text-xs text-slate-600">{c.imputed ? 'Imputed (population median): no measurement' : ''}</td>
                  </>
                ) : (
                  <>
                    <td className="text-right text-slate-500">n/a</td>
                    <td className="text-right tabular-nums">{(c.weight * 100).toFixed(0)}%</td>
                    <td className="text-right text-slate-500">excluded</td>
                    <td className="pl-4 text-xs text-slate-600">Unavailable — {c.reason}</td>
                  </>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-600">A risk score is a prioritisation aid built from model scores and indicators. It is not a finding of wrongdoing.</p>
    </div>
  )
}
