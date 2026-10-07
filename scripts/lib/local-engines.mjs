import { buildLocalPlan } from './local-plan.mjs';

function object(value, name) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must be an object`);
}

function string(value, name) {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim()) throw new Error(`${name} must be a nonempty trimmed string`);
}

/** Catalog support labels describe documentation, never this machine's measured support. */
export function validateEngineCatalog(catalog) {
  object(catalog, 'engine catalog');
  if (catalog.schema_version !== 1) throw new Error('Unsupported engine catalog schema_version');
  if (typeof catalog.as_of !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(catalog.as_of) || !Number.isFinite(Date.parse(catalog.as_of)) || new Date(catalog.as_of).toISOString().slice(0, 10) !== catalog.as_of) {
    throw new Error('engine catalog.as_of must be a valid YYYY-MM-DD date');
  }
  if (!Array.isArray(catalog.engines) || catalog.engines.length === 0) throw new Error('engine catalog.engines must be nonempty');
  const ids = new Set();
  for (const engine of catalog.engines) {
    object(engine, 'engine');
    string(engine.id, 'engine.id');
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(engine.id) || engine.id === 'all') throw new Error(`Invalid or reserved engine id: ${engine.id}`);
    if (ids.has(engine.id)) throw new Error(`Duplicate engine id: ${engine.id}`);
    ids.add(engine.id);
    for (const key of ['name', 'engine', 'notes']) string(engine[key], `${engine.id}.${key}`);
    if (!['engine', 'serving-wrapper', 'reference'].includes(engine.kind)) throw new Error(`${engine.id}.kind is invalid`);
    if (!['vulkan', 'rocm', 'metal'].includes(engine.backend)) throw new Error(`${engine.id}.backend must be vulkan, rocm or metal`);
    if (![1, 2, 3].includes(engine.priority)) throw new Error(`${engine.id}.priority must be 1, 2 or 3`);
    if (!['documented', 'conditional', 'experimental'].includes(engine.hardware_support)) throw new Error(`${engine.id}.hardware_support is invalid`);
    if (!['catalog-gguf', 'separate-artifact'].includes(engine.artifact_policy)) throw new Error(`${engine.id}.artifact_policy is invalid`);
    if (engine.runtime_reserve_gib !== null && (typeof engine.runtime_reserve_gib !== 'number' || !Number.isFinite(engine.runtime_reserve_gib) || engine.runtime_reserve_gib < 0)) {
      throw new Error(`${engine.id}.runtime_reserve_gib must be a finite nonnegative GiB value or null`);
    }
    if (!Array.isArray(engine.sources) || engine.sources.length === 0) throw new Error(`${engine.id}.sources must be nonempty`);
    for (const source of engine.sources) {
      string(source, `${engine.id}.sources`);
      let url;
      try { url = new URL(source); } catch { throw new Error(`${engine.id}.sources contains an invalid URL`); }
      if (url.protocol !== 'https:' || url.username || url.password) throw new Error(`${engine.id}.sources must use HTTPS without credentials`);
    }
    if (new Set(engine.sources).size !== engine.sources.length) throw new Error(`${engine.id}.sources contains duplicates`);
  }
  return true;
}

/** Reject catalogs from a different platform, even when called without the CLI loader. */
export function validateEngineHardware(hardware, catalog) {
  validateEngineCatalog(catalog);
  const allowed = { linux: ['vulkan', 'rocm'], macos: ['metal'] }[hardware.os];
  if (!allowed) throw new Error(`Unsupported hardware OS: ${hardware.os}`);
  for (const engine of catalog.engines) {
    if (!allowed.includes(engine.backend)) throw new Error(`Engine ${engine.id} is incompatible with hardware ${hardware.id} (${hardware.os})`);
  }
  return true;
}

/** Build a model × engine plan without transferring GGUF assumptions to other formats. */
export function buildEnginePlan(models, hardware, engines, options = {}) {
  validateEngineHardware(hardware, engines);
  object(options, 'options');
  const { engine: selector = 'all', ...modelOptions } = options;
  string(selector, 'engine');
  const selected = engines.engines.filter(engine => selector === 'all' || engine.id === selector);
  if (selected.length === 0) throw new Error(`Unknown engine: ${selector} for hardware ${hardware.id}`);
  selected.sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id, 'en'));
  const basePlan = buildLocalPlan(models, hardware, modelOptions);
  const modelById = new Map(models.models.map(model => [model.id, model]));
  const rows = selected.flatMap(engine => {
    const usesCatalog = engine.artifact_policy === 'catalog-gguf';
    const hasReserve = usesCatalog && engine.runtime_reserve_gib !== null;
    const enginePlan = hasReserve
      ? buildLocalPlan(models, { ...hardware, runtime_reserve_gib: engine.runtime_reserve_gib }, modelOptions)
      : basePlan;
    return enginePlan.rows.map(base => {
      const model = modelById.get(base.id);
      return {
        id: model.id,
        model_id: model.model_id,
        model_revision: model.model_revision ?? null,
        priority: model.priority,
        architecture: model.architecture,
        parameters_total_b: model.parameters_total_b,
        parameters_active_b: model.parameters_active_b,
        quantization: usesCatalog ? model.quantization : null,
        artifact: usesCatalog && model.artifact ? structuredClone(model.artifact) : null,
        engine: {
          id: engine.id,
          name: engine.name,
          kind: engine.kind,
          engine: engine.engine,
          backend: engine.backend,
          priority: engine.priority,
          hardware_support: engine.hardware_support,
          artifact_policy: engine.artifact_policy,
        },
        context_tokens: base.context_tokens,
        budget_gib: base.budget_gib,
        estimates: hasReserve ? { ...base.estimates } : {
          weights_gib: usesCatalog ? model.weights_gib_estimate : null,
          runtime_reserve_gib: null,
          kv_cache_reserve_gib: null,
          total_gib: null,
        },
        headroom_gib: hasReserve ? base.headroom_gib : null,
        fit_status: !usesCatalog ? 'artifact-required' : hasReserve ? base.status : 'engine-memory-required',
        fit_verified: false,
        weights_basis: usesCatalog ? model.weights_basis : null,
        reason: model.reason,
        sources: [...new Set([...model.sources, ...engine.sources])],
        notes: engine.notes,
        needs: [usesCatalog ? 'artifact-pin' : 'exact-engine-artifact', 'engine-memory-calibration', 'hardware-smoke', 'local-provider-bridge'],
      };
    });
  });
  return {
    schema_version: 1,
    as_of: engines.as_of,
    model_catalog_as_of: models.as_of,
    hardware_id: basePlan.hardware_id,
    measurement_status: basePlan.measurement_status,
    hardware_sources: [...hardware.sources],
    context_tokens: basePlan.context_tokens,
    engine_selection: selector,
    engine_count: selected.length,
    model_count: basePlan.rows.length,
    budget: { ...basePlan.budget },
    estimate_basis: 'Planning estimates only. Engine support labels describe documentation, not verified hardware support. Separate artifacts and unknown engine memory reserves are not assigned GGUF fit estimates.',
    rows,
  };
}
