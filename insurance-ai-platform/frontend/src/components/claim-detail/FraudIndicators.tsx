import type { ClaimReviewPacket } from "../../api/types";
import { formatCurrency, formatDate, titleCase } from "../../lib/format";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";

const FRAUD_RELATED_RULE_TYPES = new Set(["fraud_detection", "compliance"]);

export function FraudIndicators({ packet }: { packet: ClaimReviewPacket }) {
  const fraudRules = packet.matched_rules.filter((rule) => FRAUD_RELATED_RULE_TYPES.has(rule.rule_type));
  const conflictCheck = packet.guardrail_checks.find((check) => check.name === "no_fraud_or_policy_conflict");
  const flaggedByAI = packet.recommendation_type === "flag_for_fraud";
  const hasIndicators = flaggedByAI || fraudRules.length > 0 || conflictCheck?.passed === false;

  return (
    <Card title="Fraud indicators">
      <div className="space-y-4">
        {hasIndicators ? (
          <Badge tone="danger">Indicators present — review before approving</Badge>
        ) : (
          <Badge tone="success">No fraud or policy-conflict rules matched</Badge>
        )}

        {fraudRules.length > 0 && (
          <ul className="space-y-2">
            {fraudRules.map((rule) => (
              <li key={rule.rule_code} className="rounded-md bg-red-50 p-3 text-sm ring-1 ring-inset ring-red-200">
                <div className="font-medium text-red-800">
                  {rule.rule_code} · {titleCase(rule.rule_type)}
                </div>
                <p className="mt-0.5 text-red-700">{rule.reason}</p>
              </li>
            ))}
          </ul>
        )}

        <div>
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            This member's other {titleCase(packet.claim_type)} claims
          </h3>
          {packet.similar_claims.length === 0 ? (
            <p className="text-sm text-slate-500">No other claims of this type on record.</p>
          ) : (
            <table className="min-w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {packet.similar_claims.map((claim) => (
                  <tr key={claim.claim_id}>
                    <td className="py-1.5 pr-3 font-medium text-slate-800">{claim.claim_number}</td>
                    <td className="py-1.5 pr-3 text-slate-600">{formatDate(claim.date_of_service)}</td>
                    <td className="py-1.5 pr-3 text-slate-600">{formatCurrency(claim.billed_amount)}</td>
                    <td className="py-1.5 text-slate-600">{titleCase(claim.final_decision)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Card>
  );
}
