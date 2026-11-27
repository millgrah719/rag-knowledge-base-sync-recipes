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
const chosenInput = {inputMode: 'dataset', datasetId: 'fixture-source', corpusId: 'fixture-corpus', completeSnapshot: true, previousManifestStoreId: 'accepted-baseline'};
const approval = {downstreamReady: true, approvalStatus: 'READY', approvalReasons: [], approvalScope: 'SUPPLIED_RECORDS_ONLY'};
const completeStatus = {status: 'COMPLETE', baselineEligible: true, operationCount: 2, ...approval};
const sampleOps = [
  {operation: 'UPSERT', chunkId: 'a', source: 'https://example.com/current', corpusId: 'fixture-corpus', text: 'Current document.'},
  {operation: 'DELETE', chunkId: 'b', source: 'https://example.com/removed', corpusId: 'fixture-corpus'},
];
const sampleQa = {
  ...approval, inputRows: 3, acceptedDocuments: 2, duplicateRowsRemoved: 1, rejectedRows: 0,
  identicalTextAcrossSources: 0, unchangedDocuments: 1, totalChunks: 2,
  upsertCount: 1, deleteCount: 1, deletionEnabled: true, completeSnapshot: true, issues: [],
};
const sampleManifest = {schemaVersion: 1, config: {corpus: 'fixture-corpus'}, complete: true, documents: {
  'https://example.com/current': {contentHash: 'current-hash', chunkIds: ['a']},
  'https://example.com/unchanged': {contentHash: 'unchanged-hash', chunkIds: ['unchanged']},
}};
// Captured offline from the updated Actor execute() with its in-memory adapter
// and the exact exported Choose input demo settings; no platform run was made.
const actualDemoOutput = {
  "completion": {
    "stateVersion": 1,
    "inputFingerprint": "070480a931adebe11010fa310bb3c794ec844ebfad9ca3b0f454cd04deae450d",
    "reportDigest": "76465a3c5dac867aa3ae8a8ea4ff5ebc3adfe932c630d65fd3456522c4071471",
    "operationCount": 2,
    "mode": "demo",
    "baselineEligible": false,
    "downstreamReady": false,
    "approvalStatus": "REVIEW_REQUIRED",
    "approvalReasons": [
      "DEMO_ONLY"
    ],
    "approvalScope": "SUPPLIED_RECORDS_ONLY",
    "summary": {
      "inputRows": 3,
      "acceptedDocuments": 2,
      "duplicateRowsRemoved": 1,
      "rejectedRows": 0,
      "identicalTextAcrossSources": 0,
      "unchangedDocuments": 0,
      "totalChunks": 2,
      "upsertCount": 2,
      "deleteCount": 0,
      "deletionEnabled": false,
      "completeSnapshot": true,
      "downstreamReady": false,
      "approvalStatus": "REVIEW_REQUIRED",
      "approvalReasons": [
        "DEMO_ONLY"
      ],
      "approvalScope": "SUPPLIED_RECORDS_ONLY"
    },
    "chargedEventCount": 0,
    "billingStatus": "NOT_APPLICABLE",
    "status": "COMPLETE"
  },
  "qa": {
    "inputRows": 3,
    "acceptedDocuments": 2,
    "duplicateRowsRemoved": 1,
    "rejectedRows": 0,
    "identicalTextAcrossSources": 0,
    "unchangedDocuments": 0,
    "totalChunks": 2,
    "upsertCount": 2,
    "deleteCount": 0,
    "deletionEnabled": false,
    "completeSnapshot": true,
    "issues": [],
    "downstreamReady": false,
    "approvalStatus": "REVIEW_REQUIRED",
    "approvalReasons": [
      "DEMO_ONLY"
    ],
    "approvalScope": "SUPPLIED_RECORDS_ONLY"
  },
  "manifest": {
    "schemaVersion": 1,
    "config": {
      "version": 1,
      "corpus": "demo",
      "sourceField": "url",
      "textField": "auto",
      "chunkChars": 250,
      "overlapChars": 50
    },
    "complete": true,
    "documents": {
      "https://example.com/faq": {
        "contentHash": "d7e0f29486e958816fb482ebdba213ac8c843015e236e93066852d070fe545f9",
        "chunkIds": [
          "13c48e86c9c4249722f71aa8920f0e61fabbe317019cc904f6ea3f38dc7d571b"
        ]
      },
      "https://example.com/guide": {
        "contentHash": "eb988440d737b0c693c9f6a9c015501e67f02d2afe46efb063232360c7690bd2",
        "chunkIds": [
          "58c79ad4248b1348b840698ca0ac83ccd4ae012672cba4741473d73bd921f1b5"
        ]
      }
    }
  },
  "operations": [
    {
      "operation": "UPSERT",
      "chunkId": "13c48e86c9c4249722f71aa8920f0e61fabbe317019cc904f6ea3f38dc7d571b",
      "source": "https://example.com/faq",
      "text": "# Frequently asked questions\n\nYou can export your records as JSON.",
      "startChar": 0,
      "endChar": 66,
      "contentHash": "d7e0f29486e958816fb482ebdba213ac8c843015e236e93066852d070fe545f9",
      "chunkHash": "d7e0f29486e958816fb482ebdba213ac8c843015e236e93066852d070fe545f9",
      "corpusId": "demo"
    },
    {
      "operation": "UPSERT",
      "chunkId": "58c79ad4248b1348b840698ca0ac83ccd4ae012672cba4741473d73bd921f1b5",
      "source": "https://example.com/guide",
      "text": "# Getting started\n\nOpen the dashboard and create a workspace. Your documents remain in the workspace.",
      "startChar": 0,
      "endChar": 101,
      "contentHash": "eb988440d737b0c693c9f6a9c015501e67f02d2afe46efb063232360c7690bd2",
      "chunkHash": "eb988440d737b0c693c9f6a9c015501e67f02d2afe46efb063232360c7690bd2",
      "corpusId": "demo"
    }
  ]
};
const partial = {
  chosenInput: {...chosenInput, completeSnapshot: false},
  completion: {...completeStatus, baselineEligible: false, operationCount: 1},
  qa: {...sampleQa, completeSnapshot: false, deleteCount: 0, deletionEnabled: false},
  manifest: {...sampleManifest, complete: false},
  operations: [sampleOps[0]],
};

// Follow the exported connections and execute the real Code-node JavaScript.
// HTTP responses are fixtures: this does not execute an n8n server or a paid Actor.
function fixture({initial = run, followUp = run, completion = completeStatus,
  operations = sampleOps, qa = sampleQa, manifest = sampleManifest,
  chosenInput: inputOverride = chosenInput, useExportedInput = false} = {}) {
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
        if (name === 'Choose input' && !useExportedInput) input = inputOverride;
      } else if (current.type === 'n8n-nodes-base.httpRequest') {
        const method = current.parameters.method || 'GET';
        const url = new URL(expression(current.parameters.url, input, refs));
        calls.push({name, method, url, body: method === 'POST' ? input : undefined});
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
          input = qa;
        } else if (url.pathname.endsWith('/records/MANIFEST')) {
          input = manifest;
        } else if (url.pathname.endsWith('/items')) {
          assert.equal(url.searchParams.get('limit'), '16001');
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
function assertNoHandoff(result) {
  assert.ifError(result.error);
  assert.equal(result.result.reportComplete, true);
  assert.equal(result.result.downstreamReady, false);
  assert.deepEqual(result.result.upserts, []);
  assert.deepEqual(result.result.deleteSuggestions, []);
  assert.equal(result.result.baseline.candidateManifestStoreId, null);
  assert.equal(result.result.baseline.commitAllowed, false);
  assert.equal(result.result.baseline.updated, false);
}

check('explicitly approved clean full snapshot yields a candidate, never a committed baseline', () => {
  const result = fixture();
  assert.ifError(result.error);
  assertSingleStart(result);
  assert.equal(result.result.runId, run.id);
  assert.equal(result.result.reportComplete, true);
  assert.equal(result.result.qaAccepted, true);
  assert.equal(result.result.downstreamReady, true);
  assert.equal(result.result.upserts.length, 1);
  assert.equal(result.result.deleteSuggestions.length, 1);
  assert.equal(result.result.baseline.previousManifestStoreId, 'accepted-baseline');
  assert.equal(result.result.baseline.candidateManifestStoreId, run.defaultKeyValueStoreId);
  assert.equal(result.result.baseline.requiresDestinationAcknowledgement, true);
  assert.equal(result.result.baseline.commitAllowed, false);
  assert.equal(result.result.baseline.updated, false);
  assert.equal(result.calls.length, 6);
  assert(!wf.connections['Review result'], 'No automatic baseline or destination write follows the result');
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

check('legacy 0.0.3 output remains review-only even for a clean full snapshot', () => {
  const {downstreamReady, approvalStatus, approvalReasons, approvalScope, ...legacyQa} = sampleQa;
  const legacyStatus = {status: 'COMPLETE', baselineEligible: true, operationCount: 2};
  const result = fixture({qa: legacyQa, completion: legacyStatus});
  assertNoHandoff(result);
  assert.equal(result.result.qaAccepted, true);
  assert.equal(result.result.actorApprovalAvailable, false);
  assert.match(result.result.blockedReasons.join(' '), /ACTOR_APPROVAL_UNAVAILABLE/);
});

check('missing approval scope cannot be inferred from a readiness boolean', () => {
  const {approvalScope, ...unscoped} = sampleQa;
  const result = fixture({qa: unscoped});
  assertNoHandoff(result);
  assert.match(result.result.blockedReasons.join(' '), /ACTOR_APPROVAL_UNAVAILABLE/);
});

check('Actor review-required status overrides a positive readiness flag', () => {
  const result = fixture({qa: {...sampleQa, approvalStatus: 'REVIEW_REQUIRED'}});
  assertNoHandoff(result);
  assert.match(result.result.blockedReasons.join(' '), /Actor explicitly withheld/);
});

check('COMPLETE with rejected rows remains review-only', () => {
  const result = fixture({...partial,
    chosenInput,
    qa: {...partial.qa, duplicateRowsRemoved: 0, rejectedRows: 1, issues: [{row: 2, reason: 'MISSING_OR_EMPTY_TEXT'}]},
  });
  assertNoHandoff(result);
  assert.equal(result.result.qaAccepted, false);
  assert.equal(result.result.review.upserts.length, 1);
  assert.match(result.result.blockedReasons.join(' '), /QA rejected/);
});

check('clean partial data does not advance the baseline or hand off updates', () => {
  const result = fixture(partial);
  assertNoHandoff(result);
  assert.equal(result.result.qaAccepted, true);
  assert.equal(result.result.review.upserts.length, 1);
  assert.equal(result.result.baseline.previousManifestStoreId, 'accepted-baseline');
  assert.match(result.result.blockedReasons.join(' '), /Partial or incremental/);
});

check('omitted snapshot flag becomes false before the paid start', () => {
  const {completeSnapshot, ...withoutSnapshot} = chosenInput;
  const result = fixture({...partial, chosenInput: withoutSnapshot});
  assertNoHandoff(result);
  assert.equal(result.calls[0].body.completeSnapshot, false);
});

for (const completeSnapshot of ['true', 1, null]) {
  check('ambiguous snapshot flag is rejected before a paid request', () => {
    const result = fixture({chosenInput: {...chosenInput, completeSnapshot}});
    assert(result.error);
    assert.match(result.error.message, /explicit boolean/);
    assert.equal(result.calls.length, 0);
  });
}

check('producer cannot silently promote partial input to a full snapshot', () => {
  const result = fixture({chosenInput: {...chosenInput, completeSnapshot: false}});
  assert(result.error);
  assert.match(result.error.message, /partial input/);
});

check('actual updated Actor demo stays preview-only with an ineligible complete manifest', () => {
  assert.equal(actualDemoOutput.manifest.complete, true);
  assert.equal(actualDemoOutput.completion.baselineEligible, false);
  const result = fixture({useExportedInput: true, ...actualDemoOutput});
  assertNoHandoff(result);
  assert.equal(result.result.qaAccepted, true);
  assert.equal(result.result.actorApprovalAvailable, true);
  assert.equal(result.result.review.upserts.length, 2);
  assert.match(result.result.blockedReasons.join(' '), /Fictional demo/);
});

check('legacy demo stays preview-only when its old status marks the manifest eligible', () => {
  const legacy = structuredClone(actualDemoOutput);
  for (const record of [legacy.qa, legacy.completion, legacy.completion.summary]) {
    for (const key of ['downstreamReady', 'approvalStatus', 'approvalReasons', 'approvalScope']) delete record[key];
  }
  legacy.completion.baselineEligible = true;
  const result = fixture({useExportedInput: true, ...legacy});
  assertNoHandoff(result);
  assert.equal(result.result.review.upserts.length, 2);
  assert.equal(result.result.actorApprovalAvailable, false);
  assert.match(result.result.blockedReasons.join(' '), /ACTOR_APPROVAL_UNAVAILABLE/);
});

for (const record of ['qa', 'completion']) {
  check('optional Actor ' + record + ' downstreamReady=false tightens the gate', () => {
    const result = fixture({[record]: {...(record === 'qa' ? sampleQa : completeStatus), downstreamReady: false}});
    assertNoHandoff(result);
    assert.match(result.result.blockedReasons.join(' '), /Actor explicitly withheld/);
  });
}

check('Actor downstreamReady=true cannot override the partial snapshot gate', () => {
  const result = fixture({...partial, qa: {...partial.qa, downstreamReady: true}, completion: {...partial.completion, downstreamReady: true}});
  assertNoHandoff(result);
});

for (const qa of [null, {}, {...sampleQa, rejectedRows: '0'}, {...sampleQa, issues: [{row: 1, reason: 'ERROR'}]}, {...sampleQa, acceptedDocuments: 4}]) {
  check('malformed or inconsistent QA cannot unlock a handoff', () => {
    const result = fixture({qa});
    assert(result.error);
    assert.match(result.error.message, /QA report/);
  });
}

check('manifest completeness must agree with the completed report', () => {
  const result = fixture({manifest: {...sampleManifest, complete: false}});
  assert(result.error);
  assert.match(result.error.message, /Manifest and completion/);
});

check('a manifest for another corpus is rejected', () => {
  const result = fixture({manifest: {...sampleManifest, config: {corpus: 'different-corpus'}}});
  assert(result.error);
  assert.match(result.error.message, /corpus/);
});

check('unchanged full snapshot with no operations is eligible but still not committed', () => {
  const result = fixture({operations: [], completion: {...completeStatus, operationCount: 0}, qa: {...sampleQa, unchangedDocuments: 2, upsertCount: 0, deleteCount: 0}});
  assert.ifError(result.error);
  assertSingleStart(result);
  assert.deepEqual(result.result.upserts, []);
  assert.deepEqual(result.result.deleteSuggestions, []);
  assert.equal(result.result.downstreamReady, true);
  assert.equal(result.result.baseline.updated, false);
});

for (const operations of [{}, [], [sampleOps[0]]]) {
  check('missing or truncated operation arrays cannot be consumed', () => {
    const result = fixture({operations});
    assert(result.error);
    assert.match(result.error.message, /complete JSON array/);
    assertSingleStart(result);
  });
}

for (const op of [null, {...sampleOps[0], operation: 'UNKNOWN'}, {...sampleOps[0], corpusId: 'foreign'}, {...sampleOps[0], text: ''}, {...sampleOps[0], chunkId: 'b'}]) {
  check('invalid, duplicate or foreign-corpus operations are blocked', () => {
    const result = fixture({operations: [op, sampleOps[1]]});
    assert(result.error);
    assert.match(result.error.message, /chunk operation/);
  });
}

check('deletion suggestions require a supplied previous baseline', () => {
  const {previousManifestStoreId, ...withoutBaseline} = chosenInput;
  const result = fixture({chosenInput: withoutBaseline});
  assert(result.error);
  assert.match(result.error.message, /deletion eligibility/);
});

check('export remains inactive, credential-free, capped and bounded', () => {
  assert.equal(wf.active, false);
  assert.equal(execute('Choose input', {})[0].json.inputMode, 'demo');
  assert.equal(execute('Choose input', {})[0].json.completeSnapshot, false);
  const requests = wf.nodes.filter(n => n.type === 'n8n-nodes-base.httpRequest');
  assert.equal(requests.length, 6);
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
