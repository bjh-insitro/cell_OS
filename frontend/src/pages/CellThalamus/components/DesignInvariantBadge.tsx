/**
 * Design Invariant Badge - Display validation certificate for design
 *
 * Shows:
 * - Validation status (pass/fail with violation count)
 * - Scaffold provenance (ID, hash, 3-way verification)
 * - Expandable violation details
 */

import React, { useState, useMemo } from 'react';
import { checkPhase0V2Design } from '../invariants/index';
import type { Well, DesignMetadata, DesignCertificate, Violation } from '../invariants/types';

interface DesignInvariantBadgeProps {
  wells: Well[];
  metadata?: DesignMetadata;
  compact?: boolean;
}

const DesignInvariantBadge: React.FC<DesignInvariantBadgeProps> = ({ wells, metadata, compact = false }) => {
  const [expanded, setExpanded] = useState(false);

  const certificate: DesignCertificate = useMemo(() => {
    return checkPhase0V2Design(wells, metadata);
  }, [wells, metadata]);

  const errorCount = certificate.violations.filter((v) => v.severity === 'error').length;
  const warningCount = certificate.violations.filter((v) => v.severity === 'warning').length;
  const isPassing = errorCount === 0;

  // Group violations by type
  const violationsByType = useMemo(() => {
    const grouped = new Map<string, Violation[]>();
    for (const v of certificate.violations) {
      const existing = grouped.get(v.type) ?? [];
      existing.push(v);
      grouped.set(v.type, existing);
    }
    return grouped;
  }, [certificate.violations]);

  if (compact) {
    return (
      <div
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium ${
          isPassing
            ? 'bg-green-900/30 text-green-400 border border-green-700/50'
            : 'bg-red-900/30 text-red-400 border border-red-700/50'
        }`}
      >
        <span>{isPassing ? '✓' : '✗'}</span>
        <span>
          {isPassing ? 'Valid' : `${errorCount} error${errorCount !== 1 ? 's' : ''}`}
          {warningCount > 0 && `, ${warningCount} warning${warningCount !== 1 ? 's' : ''}`}
        </span>
      </div>
    );
  }

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold ${
              isPassing
                ? 'bg-green-900/30 text-green-400 border border-green-700/50'
                : 'bg-red-900/30 text-red-400 border border-red-700/50'
            }`}
          >
            <span className="text-lg">{isPassing ? '✓' : '✗'}</span>
            <span>
              {isPassing ? 'Design Validated' : 'Validation Failed'}
            </span>
          </div>
        </div>
        <div className="text-xs text-slate-500">
          {certificate.stats.totalWells} wells • {certificate.stats.nPlates} plates
        </div>
      </div>

      {/* Scaffold Metadata */}
      {certificate.scaffoldMetadata && (
        <div className="mb-3 p-3 bg-slate-900/50 border border-slate-700/50 rounded">
          <div className="text-xs font-semibold text-violet-400 mb-2">Scaffold Provenance</div>
          <div className="space-y-1 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 w-24">ID:</span>
              <span className="text-slate-300 font-mono">
                {certificate.scaffoldMetadata.expected.scaffoldId}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-500 w-24">Expected:</span>
              <span className="text-slate-300 font-mono">
                {certificate.scaffoldMetadata.expected.scaffoldHash}
              </span>
            </div>
            {certificate.scaffoldMetadata.observed?.scaffoldHash && (
              <div className="flex items-center gap-2">
                <span className="text-slate-500 w-24">Observed:</span>
                <span
                  className={`font-mono ${
                    certificate.scaffoldMetadata.observed.scaffoldHash ===
                    certificate.scaffoldMetadata.expected.scaffoldHash
                      ? 'text-green-400'
                      : 'text-red-400'
                  }`}
                >
                  {certificate.scaffoldMetadata.observed.scaffoldHash}
                  <span className="ml-1">
                    {certificate.scaffoldMetadata.observed.scaffoldHash ===
                    certificate.scaffoldMetadata.expected.scaffoldHash
                      ? '✓'
                      : '✗'}
                  </span>
                </span>
              </div>
            )}
            {certificate.scaffoldMetadata.observed?.wellDerivedHash && (
              <div className="flex items-center gap-2">
                <span className="text-slate-500 w-24">Well-derived:</span>
                <span
                  className={`font-mono ${
                    certificate.scaffoldMetadata.observed.wellDerivedMatchesExpected
                      ? 'text-green-400'
                      : 'text-red-400'
                  }`}
                >
                  {certificate.scaffoldMetadata.observed.wellDerivedHash}
                  <span className="ml-1">
                    {certificate.scaffoldMetadata.observed.wellDerivedMatchesExpected ? '✓' : '✗'}
                  </span>
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Violations Summary */}
      {certificate.violations.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full flex items-center justify-between text-sm font-medium text-slate-300 hover:text-white transition-colors"
          >
            <span>
              {errorCount > 0 && (
                <span className="text-red-400">
                  {errorCount} error{errorCount !== 1 ? 's' : ''}
                </span>
              )}
              {errorCount > 0 && warningCount > 0 && <span className="text-slate-500"> • </span>}
              {warningCount > 0 && (
                <span className="text-yellow-400">
                  {warningCount} warning{warningCount !== 1 ? 's' : ''}
                </span>
              )}
            </span>
            <span className="text-slate-500">{expanded ? '▼' : '▶'}</span>
          </button>

          {expanded && (
            <div className="mt-3 space-y-2 max-h-96 overflow-y-auto">
              {Array.from(violationsByType.entries())
                .sort(([, a], [, b]) => {
                  // Sort errors first, then by count descending
                  const aSev = a[0].severity === 'error' ? 0 : 1;
                  const bSev = b[0].severity === 'error' ? 0 : 1;
                  if (aSev !== bSev) return aSev - bSev;
                  return b.length - a.length;
                })
                .map(([type, violations]) => (
                  <div key={type} className="p-3 bg-slate-900/50 border border-slate-700/50 rounded text-xs">
                    <div className="flex items-start gap-2 mb-2">
                      <span className="text-lg">
                        {violations[0].severity === 'error' ? '❌' : '⚠️'}
                      </span>
                      <div className="flex-1">
                        <div className="font-semibold text-slate-200 mb-1">
                          {type}
                          <span className="ml-2 text-slate-500">({violations.length})</span>
                        </div>
                        <div className="text-slate-400">{violations[0].message}</div>
                        {violations[0].suggestion && (
                          <div className="mt-1 text-slate-500 italic">
                            Suggestion: {violations[0].suggestion}
                          </div>
                        )}
                        {violations[0].details && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-slate-500 hover:text-slate-400">
                              Show details
                            </summary>
                            <pre className="mt-1 text-slate-600 text-[10px] overflow-x-auto">
                              {JSON.stringify(violations[0].details, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DesignInvariantBadge;
