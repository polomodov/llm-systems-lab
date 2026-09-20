const CONTEXTS = [8192, 16384, 32768];
const ARCHITECTURES = ['dense', 'moe', 'hybrid-moe', 'hybrid-dense'];
const NEEDS = ['hardware-preflight', 'artifact-pin', 'backend-smoke', 'local-provider-bridge'];
const HF_REPOSITORY = /^[A-Za-z0-9][A-Za-z0-9_.-]*\/[A-Za-z0-9][A-Za-z0-9_.-]*$/;

function object(value, name) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must be an object`);
}

function string(value, name) {
  if (typeof value !== 'string' || !value.trim() || value !== value.trim()) throw new Error(`${name} must be a nonempty trimmed string`);
}

function number(value, name, allowZero = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || (allowZero ? value < 0 : value <= 0)) {
    throw new Error(`${name} must be a finite ${allowZero ? 'nonnegative' : 'positive'} number`);
  }
}

function sources(value, name) {
  if (!Array.isArray(value) || value.length === 0) throw new Error(`${name} must contain source URLs`);
  for (const source of value) {
    string(source, name);
    let url;
    try { url = new URL(source); } catch { throw new Error(`${name} contains an invalid URL`); }
    if (url.protocol !== 'https:' || url.username || url.password) throw new Error(`${name} must use HTTPS URLs without credentials`);
  }
  if (new Set(value).size !== value.length) throw new Error(`${name} contains duplicate URLs`);
}

function validateArtifact(model) {
  if (model.model_revision !== undefined && (typeof model.model_revision !== 'string' || !/^[a-fA-F0-9]{40}$/.test(model.model_revision))) {
    throw new Error(`${model.id}.model_revision must be a 40-character commit hash`);
  }
  if (model.artifact === undefined) return;
  const artifact = model.artifact;
  object(artifact, `${model.id}.artifact`);
  string(artifact.repository, `${model.id}.artifact.repository`);
  if (!HF_REPOSITORY.test(artifact.repository)) throw new Error(`${model.id}.artifact.repository must be a Hugging Face repository ID`);
  if (typeof artifact.revision !== 'string' || !/^[a-fA-F0-9]{40}$/.test(artifact.revision)) throw new Error(`${model.id}.artifact.revision must be a 40-character commit hash`);
  if (model.model_revision === undefined) throw new Error(`${model.id}.model_revision is required with artifact metadata`);
  if (artifact.checksum_status !== 'publisher_metadata_not_download_verified') throw new Error(`${model.id}.artifact.checksum_status must describe unverified publisher metadata`);
  if (!Array.isArray(artifact.files) || artifact.files.length === 0) throw new Error(`${model.id}.artifact.files must be nonempty`);
  const paths = new Set();
  let total = 0;
  for (const file of artifact.files) {
    object(file, `${model.id}.artifact file`);
    string(file.path, `${model.id}.artifact file path`);
    if (!file.path.endsWith('.gguf') || file.path.includes('..') || file.path.split('/').some(part => !/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(part))) {
      throw new Error(`${model.id}.artifact file path must be a safe relative .gguf path`);
    }
    if (paths.has(file.path)) throw new Error(`${model.id}.artifact contains a duplicate file path`);
    paths.add(file.path);
    if (!Number.isSafeInteger(file.bytes) || file.bytes <= 0) throw new Error(`${model.id}.artifact file bytes must be a positive safe integer`);
    if (typeof file.sha256 !== 'string' || !/^[a-fA-F0-9]{64}$/.test(file.sha256)) throw new Error(`${model.id}.artifact file sha256 must be a 64-character hash`);
    total += file.bytes;
    if (!Number.isSafeInteger(total)) throw new Error(`${model.id}.artifact total size exceeds safe integer precision`);
  }
  if (!Number.isSafeInteger(artifact.total_bytes) || artifact.total_bytes !== total) throw new Error(`${model.id}.artifact.total_bytes must equal the sum of file bytes`);
  const weightGib = total / (2 ** 30);
  if (model.weights_gib_estimate < weightGib || model.weights_gib_estimate - weightGib > 0.1 + 1e-12) {
    throw new Error(`${model.id}.weights_gib_estimate must round artifact size up by at most 0.1 GiB`);
  }
}

/** Validate planning inputs only; this does not verify hardware or model artifacts. */
export function validateLocalPlanData(catalog, hardware) {
  object(catalog, 'catalog');
  object(hardware, 'hardware');
  if (catalog.schema_version !== 1 || hardware.schema_version !== 1) throw new Error('Unsupported local plan schema_version');
  string(catalog.as_of, 'catalog.as_of');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(catalog.as_of) || !Number.isFinite(Date.parse(catalog.as_of)) || new Date(catalog.as_of).toISOString().slice(0, 10) !== catalog.as_of) {
    throw new Error('catalog.as_of must be a valid YYYY-MM-DD date');
  }
  if (!Array.isArray(catalog.models) || catalog.models.length === 0) throw new Error('catalog.models must be nonempty');
  const ids = new Set(), modelIds = new Set();
  for (const model of catalog.models) {
    object(model, 'model');
    string(model.id, 'model.id');
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(model.id)) throw new Error(`Invalid model slug: ${model.id}`);
    if (ids.has(model.id)) throw new Error(`Duplicate model id: ${model.id}`);
    ids.add(model.id);
    string(model.model_id, `${model.id}.model_id`);
    if (!HF_REPOSITORY.test(model.model_id)) throw new Error(`Invalid Hugging Face model_id: ${model.model_id}`);
    if (modelIds.has(model.model_id)) throw new Error(`Duplicate model_id: ${model.model_id}`);
    modelIds.add(model.model_id);
    if (![1, 2, 3].includes(model.priority)) throw new Error(`${model.id}.priority must be 1, 2 or 3`);
    if (!ARCHITECTURES.includes(model.architecture)) throw new Error(`${model.id}.architecture is invalid`);
    number(model.parameters_total_b, `${model.id}.parameters_total_b`);
    number(model.parameters_active_b, `${model.id}.parameters_active_b`);
    if (model.parameters_active_b > model.parameters_total_b) throw new Error(`${model.id}: active parameters exceed total parameters`);
    number(model.weights_gib_estimate, `${model.id}.weights_gib_estimate`);
    string(model.weights_basis, `${model.id}.weights_basis`);
    string(model.quantization, `${model.id}.quantization`);
    string(model.reason, `${model.id}.reason`);
    if (!['candidate', 'conditional'].includes(model.fit)) throw new Error(`${model.id}.fit must be candidate or conditional`);
    if (!Array.isArray(model.context_tokens) || model.context_tokens.length === 0 || model.context_tokens.some(context => !CONTEXTS.includes(context)) || new Set(model.context_tokens).size !== model.context_tokens.length) {
      throw new Error(`${model.id}.context_tokens must contain unique supported context sizes: ${CONTEXTS.join(', ')}`);
    }
    sources(model.sources, `${model.id}.sources`);
    validateArtifact(model);
  }
  string(hardware.id, 'hardware.id');
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(hardware.id)) throw new Error('hardware.id must be a slug');
  string(hardware.cpu, 'hardware.cpu');
  if (hardware.os !== 'linux') throw new Error('hardware.os must be linux for this plan');
  if (hardware.measurement_status !== 'unverified') throw new Error('hardware.measurement_status must be unverified; this planner does not validate measurements');
  for (const name of ['reported_memory_gb', 'planning_memory_gib', 'gpu_budget_gib']) number(hardware[name], `hardware.${name}`);
  for (const name of ['os_reserve_gib', 'runtime_reserve_gib']) number(hardware[name], `hardware.${name}`, true);
  if (hardware.planning_memory_gib > hardware.reported_memory_gb) throw new Error('hardware.planning_memory_gib exceeds reported memory in GB');
  if (hardware.os_reserve_gib >= hardware.planning_memory_gib) throw new Error('hardware.os_reserve_gib leaves no usable memory');
  if (hardware.gpu_budget_gib > hardware.planning_memory_gib) throw new Error('hardware.gpu_budget_gib exceeds planning memory');
  object(hardware.kv_cache_reserve_gib, 'hardware.kv_cache_reserve_gib');
  const contextKeys = Object.keys(hardware.kv_cache_reserve_gib);
  if (contextKeys.length !== CONTEXTS.length || contextKeys.some(key => !CONTEXTS.map(String).includes(key))) throw new Error('hardware.kv_cache_reserve_gib must declare all supported contexts');
  let previousReserve = -1;
  for (const context of CONTEXTS) {
    const reserve = hardware.kv_cache_reserve_gib[context];
    number(reserve, `hardware.kv_cache_reserve_gib.${context}`, true);
    if (reserve < previousReserve) throw new Error('hardware.kv_cache_reserve_gib must not decrease with context size');
    previousReserve = reserve;
  }
  sources(hardware.sources, 'hardware.sources');
  return true;
}

/** Produce deterministic estimates, never run records or a verified-fit verdict. */
export function buildLocalPlan(catalog, hardware, options = {}) {
  validateLocalPlanData(catalog, hardware);
  object(options, 'options');
  for (const key of Object.keys(options)) {
    if (!['model', 'context', 'gpuBudgetGib', 'memoryGib'].includes(key)) throw new Error(`Unknown local plan option: ${key}`);
  }
  const context = options.context === undefined ? 16384 : options.context;
  if (!CONTEXTS.includes(context)) throw new Error(`Unsupported context: ${context}; expected ${CONTEXTS.join(', ')}`);
  const memory = options.memoryGib === undefined ? hardware.planning_memory_gib : options.memoryGib;
  const gpuBudget = options.gpuBudgetGib === undefined ? hardware.gpu_budget_gib : options.gpuBudgetGib;
  number(memory, 'memoryGib');
  number(gpuBudget, 'gpuBudgetGib');
  if (memory <= hardware.os_reserve_gib) throw new Error('memoryGib must exceed the OS reserve');
  if (options.model !== undefined) string(options.model, 'model');
  const selected = options.model === undefined ? catalog.models : catalog.models.filter(model => model.id === options.model);
  if (selected.length === 0) throw new Error(`Unknown model: ${options.model}`);
  const available = memory - hardware.os_reserve_gib;
  const budget = Math.min(available, gpuBudget);
  const cacheReserve = hardware.kv_cache_reserve_gib[context];
  const rows = [...selected].sort((a, b) => a.priority - b.priority || a.weights_gib_estimate - b.weights_gib_estimate || a.id.localeCompare(b.id, 'en')).map(model => {
    if (!model.context_tokens.includes(context)) throw new Error(`Context ${context} is not listed for model ${model.id}`);
    const estimated = model.weights_gib_estimate + hardware.runtime_reserve_gib + cacheReserve;
    number(estimated, `${model.id}.estimated total`);
    // Avoid declaring a decimal boundary over budget because of floating point noise.
    const headroom = Number((budget - estimated).toFixed(9));
    return {
      id: model.id,
      model_id: model.model_id,
      priority: model.priority,
      architecture: model.architecture,
      parameters_total_b: model.parameters_total_b,
      parameters_active_b: model.parameters_active_b,
      quantization: model.quantization,
      context_tokens: context,
      budget_gib: budget,
      estimates: { weights_gib: model.weights_gib_estimate, runtime_reserve_gib: hardware.runtime_reserve_gib, kv_cache_reserve_gib: cacheReserve, total_gib: estimated },
      headroom_gib: headroom,
      status: headroom < 0 ? 'over-budget' : model.fit,
      fit_verified: false,
      weights_basis: model.weights_basis,
      reason: model.reason,
      sources: [...model.sources],
      needs: [...NEEDS],
    };
  });
  return {
    schema_version: 1,
    as_of: catalog.as_of,
    hardware_id: hardware.id,
    measurement_status: hardware.measurement_status,
    context_tokens: context,
    budget: { memory_gib: memory, os_reserve_gib: hardware.os_reserve_gib, available_memory_gib: available, gpu_budget_gib: gpuBudget, effective_gib: budget },
    estimate_basis: 'Planning reserves only; KV cache is not calculated from model architecture. Candidate does not mean verified fit.',
    rows,
  };
}
