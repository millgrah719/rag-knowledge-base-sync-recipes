import assert from 'node:assert/strict';
import fs from 'node:fs';

const wf = JSON.parse(fs.readFileSync(new URL('../n8n/rag-dataset-qa.json', import.meta.url), 'utf8'));
const node = name => wf.nodes.find(n => n.name === name);
const reference = refs => name => ({first: () => ({json: refs[name]})});
const execute = (name, input, refs = {}) => new Function('$input', '$', node(name).parameters.jsCode)(
  {first: () => ({json: input})}, reference(refs),
);
const expression = (value, input, refs) => typeof value === 'string' && value.startsWith('={{')
  ? new Function('$json', '$', 'return (' + value.slice(3, -2).trim() + ');')(input, reference(refs))
  : value;
const run = {id: 'fixture-run', status: 'SUCCEEDED', defaultKeyValueStoreId: 'fixture-store', defaultDatasetId: 'fixture-dataset'};
const completeStatus = {status: 'COMPLETE', baselineEligible: true};
const sampleOps = [{operation: 'UPSERT', chunkId: 'a'}, {operation: 'DELETE', chunkId: 'b'}];

// Execute the actual connected Code nodes with mocked HTTP responses. This catches
// disconnected gates and accidental repeated starts, but is not an n8n runtime test.
function fixture({initial = run, followUp = run, completion = completeStatus, operations = sampleOps} = {}) {
  const calls = [];
  const visited = new Set();
  const refs = {};
  let name = 'Run manually';
  let input = {};
  try {
    while (name) {
      assert(!visited.has(name), 'Workflow must not loop back into any node, especially the billable start');
      visited.add(name);
      const current = node(name);
      assert(current, 'Connected node must exist: ' + name);
      if (current.type === 'n8n-nodes-base.code') {
        const items = execute(name, input, refs);
        assert.equal(items.length, 1);
        input = items[0].json;
      } else if (current.type === 'n8n-nodes-base.httpRequest') {
        const method = current.parameters.method || 'GET';
        const url = new URL(expression(current.parameters.url, input, refs));
        calls.push({name, method, url});
        if (method === 'POST') {
          assert.equal(name, 'Start Apify report', 'Only the initial Actor start may write');
          assert.equal(expression(current.parameters.jsonBody, input, refs), JSON.stringify(input));
          input = {data: initial};
        } else if (url.pathname.startsWith('/v2/actor-runs/')) {
          assert.equal(url.pathname, '/v2/actor-runs/' + encodeURIComponent(initial.id));
          assert.equal(url.searchParams.get('waitForFinish'), '60');
          input = {data: followUp};
        } else if (url.pathname.endsWith('/records/SYNC_STATUS')) {
          input = completion;
        } else if (url.pathname.endsWith('/records/QA')) {
          input = {duplicateRows: 1};
        } else if (url.pathname.endsWith('/items')) {
          input = {body: operations};
        } else {
          assert.fail('Unexpected HTTP destination: ' + url);
        }
      } else {
        assert.equal(current.type, 'n8n-nodes-base.manualTrigger');
      }
      refs[name] = input;
      const outputs = wf.connections[name]?.main ?? [];
      assert(outputs.length <= 1, 'This bounded workflow uses no branch or polling loop');
      assert((outputs[0] ?? []).length <= 1, 'A node must not fan out into duplicate starts');
      name = outputs[0]?.[0]?.node;
    }
    return {calls, refs, result: input};
  } catch (error) {
    return {calls, refs, error};
  }
}

let checked = 0;
function check(label, fn) {
  fn();
  checked++;
  console.log('PASS: ' + label);
}
function assertSingleStart(result, followUpCount = 1) {
  assert.equal(result.calls.filter(call => call.method === 'POST').length, 1);
  assert.equal(result.calls.filter(call => call.name === 'Wait for same run').length, followUpCount);
}

check('initial success completes through the same-run GET and report gates', () => {
  const result = fixture();
  assert.ifError(result.error);
  assertSingleStart(result);
  assert.equal(result.result.runId, run.id);
  assert.equal(result.result.upserts.length, 1);
  assert.equal(result.result.deleteSuggestions.length, 1);
  assert.equal(result.result.baselineEligible, true);
});

for (const status of ['READY', 'RUNNING']) {
  check('initial ' + status + ' can complete without another POST', () => {
    const result = fixture({initial: {...run, status}});
    assert.ifError(result.error);
    assertSingleStart(result);
    assert.equal(result.result.runId, run.id);
  });
}

for (const status of ['FAILED', 'ABORTED', 'TIMED-OUT', 'ABORTING', 'TIMING-OUT', 'RUNNING', 'READY']) {
  check('follow-up ' + status + ' stops before reading outputs', () => {
    const result = fixture({initial: {...run, status: 'RUNNING'}, followUp: {...run, status}});
    assert(result.error);
    assert.match(result.error.message, /fixture-run/);
    assertSingleStart(result);
    assert.equal(result.calls.length, 2);
  });
}

check('an initial failure stops immediately without another POST or unnecessary GET', () => {
  const result = fixture({initial: {...run, status: 'FAILED'}});
  assert(result.error);
  assert.match(result.error.message, /fixture-run/);
  assertSingleStart(result, 0);
});

for (const initial of [null, {}, {status: 'RUNNING'}, {id: '', status: 'RUNNING'}, {id: ' ', status: 'RUNNING'}]) {
  check('missing/blank initial run ID stops before follow-up', () => {
    const result = fixture({initial});
    assert(result.error);
    assert.match(result.error.message, /did not return a run ID/);
    assertSingleStart(result, 0);
  });
}

check('a response for a different run cannot unlock outputs', () => {
  const result = fixture({followUp: {...run, id: 'different-run'}});
  assert(result.error);
  assert.match(result.error.message, /fixture-run/);
  assertSingleStart(result);
  assert.equal(result.calls.length, 2);
});

for (const field of ['defaultKeyValueStoreId', 'defaultDatasetId']) {
  check('missing ' + field + ' blocks output reads', () => {
    const result = fixture({followUp: {...run, [field]: ''}});
    assert(result.error);
    assertSingleStart(result);
    assert.equal(result.calls.length, 2);
  });
}

for (const completion of [null, [], {}, {status: 'BILLING_UNKNOWN'}, {status: 'OUTPUT_READY'}, {status: 'BUDGET_LIMIT'}, {status: 'FAILED'}]) {
  check('incomplete or malformed report blocks QA and chunk consumption', () => {
    const result = fixture({completion});
    assert(result.error);
    assert.match(result.error.message, /not COMPLETE/);
    assertSingleStart(result);
    assert.equal(result.calls.length, 3);
  });
}

check('an unchanged snapshot can return an empty operations array', () => {
  const result = fixture({operations: []});
  assert.ifError(result.error);
  assertSingleStart(result);
  assert.deepEqual(result.result.upserts, []);
  assert.deepEqual(result.result.deleteSuggestions, []);
});

check('malformed operations cannot be consumed', () => {
  const result = fixture({operations: {}});
  assert(result.error);
  assert.match(result.error.message, /complete JSON array/);
  assertSingleStart(result);
});

check('export remains inactive, credential-free, capped and bounded', () => {
  assert.equal(wf.active, false);
  assert.equal(execute('Choose input', {})[0].json.inputMode, 'demo');
  const requests = wf.nodes.filter(n => n.type === 'n8n-nodes-base.httpRequest');
  assert.equal(requests.length, 5);
  assert(requests.every(n => n.parameters.genericAuthType === 'httpHeaderAuth'));
  assert(!wf.nodes.some(n => n.credentials));
  assert(!JSON.stringify(wf).includes('apify_api_'));
  const start = node('Start Apify report');
  const startUrl = new URL(start.parameters.url);
  assert.equal(start.parameters.method, 'POST');
  assert.equal(startUrl.searchParams.get('maxTotalChargeUsd'), '0.75');
  assert.equal(startUrl.searchParams.get('memory'), '256');
  assert.equal(startUrl.searchParams.get('timeout'), '90');
  assert.equal(startUrl.searchParams.get('waitForFinish'), '60');
  assert.equal(start.retryOnFail, false);
  assert.equal(node('Wait for same run').retryOnFail, false);
  assert.equal(node('Wait for same run').parameters.options.timeout, 75000);
  assert.equal(requests.filter(n => n.parameters.method === 'POST').length, 1);
  assert.match(node('Safety gates').parameters.content, /Full n8n runtime execution has not yet been verified/);
});

console.log(`${checked} checks passed. Connected-workflow tests use mocked HTTP responses and real exported Code-node JavaScript. No API calls or paid Actor runs were made. Full n8n runtime execution is not verified.`);
