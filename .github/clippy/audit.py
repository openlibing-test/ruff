# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
import collections
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

phase = sys.argv[1]
root = Path.cwd().resolve()
evidence = root / 'clippy-evidence'
sarif = json.loads((evidence / 'clippy-results.sarif').read_text())
assert sarif['version'] == '2.1.0'
results = [r for run in sarif['runs'] for r in run.get('results', [])]
missing = []
snippets = 0
locations = 0
for result in results:
    for location in result.get('locations', []):
        physical = location.get('physicalLocation', {})
        uri = physical.get('artifactLocation', {}).get('uri', '')
        path = root / unquote(urlparse(uri).path)
        locations += 1
        line = physical.get('region', {}).get('startLine', 0)
        if not path.is_file() or not path.resolve().is_relative_to(root):
            missing.append(uri)
        elif line and line > len(path.read_text(errors='replace').splitlines()):
            missing.append(f'{uri}:{line}')
        if physical.get('region', {}).get('snippet', {}).get('text'):
            snippets += 1
messages = [json.loads(s) for s in (evidence / 'cargo.jsonl').read_text().splitlines() if s.strip()]
diagnostics = [m['message'] for m in messages if m.get('reason') == 'compiler-message']
summary = dict(phase=phase, tool_names=[r['tool']['driver']['name'] for r in sarif['runs']],
               results=len(results), rules=dict(collections.Counter(r.get('ruleId') for r in results)),
               levels=dict(collections.Counter(r.get('level', 'warning') for r in results)),
               locations=locations, missing_sources=missing, snippets=snippets,
               compiler_diagnostics=len(diagnostics),
               clippy_diagnostics=sum((m.get('code') or {}).get('code', '').startswith('clippy::') for m in diagnostics),
               build_finished=[m.get('success') for m in messages if m.get('reason') == 'build-finished'])
(evidence / f'audit-{phase}.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
assert not missing, 'Unresolved SARIF source locations'
assert summary['build_finished'] == [True], 'Cargo build did not finish successfully'
