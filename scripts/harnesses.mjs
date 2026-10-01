#!/usr/bin/env node
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { loadProfile } from './lib/harnesses.mjs';
import { main } from './lib/cli.mjs';
await main(() => {
  if (process.argv.length > 2) throw new Error('Usage: npm run harnesses');
  const root=process.cwd();
  const names=readdirSync(join(root,'experiments')).filter(name=>existsSync(join(root,'experiments',name,'harness.json'))).sort();
  const rows=names.map(name=>{
    const profile=loadProfile(root,name);
    return {harness:name,pin:profile.version,providers:Object.keys(profile.providers).join(', '),credentials:[...new Set(Object.values(profile.providers).flatMap(provider=>provider.credential_env))].join(', '),selection:profile.model_policy==='managed'?profile.managed_modes.map(mode=>`managed:${mode}`).join(', '):'explicit model ID',usd:profile.budget.usd,turns:profile.budget.turns};
  });
  console.table(rows);
  console.log('Profiles describe adapter capabilities, not measured task success. Secrets are read only from .env for the selected provider.');
});
