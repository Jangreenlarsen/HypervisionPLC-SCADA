#!/usr/bin/env node
// Statuslinje: model | plan:ja/nej (hvis oplyst) | effort (hvis tilgængeligt) | branch | ctx %
const { execFileSync } = require('child_process');

let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => (raw += c));
process.stdin.on('end', () => {
  let d = {};
  try { d = JSON.parse(raw || '{}'); } catch (e) { /* tom input */ }

  const parts = [];
  parts.push((d.model && d.model.display_name) || '?');

  const mode = d.permission_mode || d.permissionMode || (d.mode && String(d.mode));
  if (mode !== undefined && mode !== null) parts.push('plan:' + (String(mode).toLowerCase() === 'plan' ? 'ja' : 'nej'));

  if (d.effort && d.effort.level) parts.push('effort:' + d.effort.level);

  const cwd = (d.workspace && d.workspace.current_dir) || d.cwd || process.cwd();
  try {
    const b = execFileSync('git', ['--no-optional-locks', 'branch', '--show-current'],
      { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 2000 }).trim();
    if (b) parts.push(b);
  } catch (e) { /* ikke et git-repo */ }

  const used = d.context_window && d.context_window.used_percentage;
  parts.push('ctx ' + (used !== null && used !== undefined ? Math.round(used) + '%' : '-'));

  process.stdout.write(parts.join(' | '));
});
