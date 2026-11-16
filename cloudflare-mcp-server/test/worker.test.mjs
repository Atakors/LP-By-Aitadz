import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const TEST_ENV = {
  CF_ACCESS_CLIENT_ID: "cf-id-test.access",
  CF_ACCESS_CLIENT_SECRET: "cf-secret-test",
  DEFAULT_AI_MODEL: "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
  SERVICE_NAME: "aitadz-cloudflare-mcp-server",
};

function makeMcpRequest(payload, headers = {}) {
  return new Request("https://mcp.aitadz.pro/mcp", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify(payload),
  });
}

test("GET /health returns 200 OK", async () => {
  const req = new Request("https://mcp.aitadz.pro/health", { method: "GET" });
  const res = await worker.fetch(req, TEST_ENV);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.status, "ok");
  assert.equal(data.protocol, "mcp/2024-11-05");
});

test("POST /mcp enforces CF-Access-Client-Id and CF-Access-Client-Secret when configured", async () => {
  const reqMissing = makeMcpRequest({ jsonrpc: "2.0", id: 1, method: "tools/list" });
  const resMissing = await worker.fetch(reqMissing, TEST_ENV);
  assert.equal(resMissing.status, 401);

  const reqWrong = makeMcpRequest(
    { jsonrpc: "2.0", id: 1, method: "tools/list" },
    {
      "CF-Access-Client-Id": "cf-id-test.access",
      "CF-Access-Client-Secret": "wrong-secret",
    }
  );
  const resWrong = await worker.fetch(reqWrong, TEST_ENV);
  assert.equal(resWrong.status, 401);
});

test("POST /mcp handles initialize and tools/list", async () => {
  const authHeaders = {
    "CF-Access-Client-Id": TEST_ENV.CF_ACCESS_CLIENT_ID,
    "CF-Access-Client-Secret": TEST_ENV.CF_ACCESS_CLIENT_SECRET,
  };

  const initRes = await worker.fetch(
    makeMcpRequest({ jsonrpc: "2.0", id: 1, method: "initialize" }, authHeaders),
    TEST_ENV
  );
  assert.equal(initRes.status, 200);
  const initJson = await initRes.json();
  assert.equal(initJson.result.protocolVersion, "2024-11-05");

  const listRes = await worker.fetch(
    makeMcpRequest({ jsonrpc: "2.0", id: 2, method: "tools/list" }, authHeaders),
    TEST_ENV
  );
  assert.equal(listRes.status, 200);
  const listJson = await listRes.json();
  const toolNames = listJson.result.tools.map((t) => t.name);
  assert.deepEqual(toolNames, ["generate_lesson_plan", "get_didactic_guidelines"]);
});

test("tools/call get_didactic_guidelines returns 60 mn for 3PS/4PS and 45 mn for 5PS", async () => {
  const authHeaders = {
    "CF-Access-Client-Id": TEST_ENV.CF_ACCESS_CLIENT_ID,
    "CF-Access-Client-Secret": TEST_ENV.CF_ACCESS_CLIENT_SECRET,
  };

  for (const [grade, expectedMinutes] of [
    ["3PS", 60],
    ["4PS", 60],
    ["5PS", 45],
  ]) {
    const res = await worker.fetch(
      makeMcpRequest(
        {
          jsonrpc: "2.0",
          id: `guideline-${grade}`,
          method: "tools/call",
          params: {
            name: "get_didactic_guidelines",
            arguments: { grade },
          },
        },
        authHeaders
      ),
      TEST_ENV
    );
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.result.isError, false);
    assert.equal(body.result.structuredContent.duration_minutes, expectedMinutes);
    assert.equal(body.result.structuredContent.duration_label, `${expectedMinutes} mn`);
  }
});

test("tools/call generate_lesson_plan invokes Workers AI, scrubs meta/monetary terms, and enforces 60/45 mn", async () => {
  const authHeaders = {
    "CF-Access-Client-Id": TEST_ENV.CF_ACCESS_CLIENT_ID,
    "CF-Access-Client-Secret": TEST_ENV.CF_ACCESS_CLIENT_SECRET,
  };

  let aiCalls = 0;
  const mockEnv = {
    ...TEST_ENV,
    AI: {
      async run(model, input) {
        aiCalls += 1;
        assert.equal(model, TEST_ENV.DEFAULT_AI_MODEL);
        assert.equal(input.messages.length, 2);
        return {
          response:
            "```json\n" +
            JSON.stringify({
              header: {
                session_objectives: "name school facilities and describe them.",
              },
              stages: [
                {
                  minutes: 10,
                  stage: "Stage 1: Warm-up",
                  procedure: "Warm up with flashcards and earn coins or money.",
                  interaction: "T-Ls",
                  competency_materials: "Flashcards",
                },
                {
                  minutes: 10,
                  stage: "Stage 2: Practice",
                  procedure: "Ask pupils to skim and scan for gist and make a prediction.",
                  interaction: "Pair",
                  competency_materials: "Word cards",
                },
              ],
            }) +
            "\n```",
        };
      },
    },
  };

  // Test 4PS -> must enforce 60 mn
  const res4 = await worker.fetch(
    makeMcpRequest(
      {
        jsonrpc: "2.0",
        id: "gen-4ps",
        method: "tools/call",
        params: {
          name: "generate_lesson_plan",
          arguments: {
            grade: "4PS",
            sequence: "Sequence 2: School",
            section: "Section 1: Facilities",
            session: "Session 3: I Read & Enjoy",
            topic: "Library & Canteen",
          },
        },
      },
      authHeaders
    ),
    mockEnv
  );
  assert.equal(res4.status, 200);
  const body4 = await res4.json();
  assert.equal(aiCalls, 1);
  assert.equal(body4.result.isError, false);

  const plan4 = JSON.parse(body4.result.content[0].text);
  assert.equal(plan4.header.duration, "60 mn");
  assert.ok(plan4.header.session_objectives.startsWith("By the end of the session, learners will be able to"));
  const total4 = plan4.stages.reduce((acc, s) => acc + s.minutes, 0);
  assert.equal(total4, 60);

  const serialized4 = JSON.stringify(plan4).toLowerCase();
  for (const banned of ["coins", "money", "skim", "scan", "gist", "prediction"]) {
    assert.ok(!serialized4.includes(banned), `Found banned term ${banned}`);
  }

  // Test 5PS -> must enforce 45 mn
  const res5 = await worker.fetch(
    makeMcpRequest(
      {
        jsonrpc: "2.0",
        id: "gen-5ps",
        method: "tools/call",
        params: {
          name: "generate_lesson_plan",
          arguments: {
            grade: "5PS",
            sequence: "Sequence 1: Jobs, Occupations and Hobbies",
            section: "Section 1: Jobs and Occupations",
            session: "I Listen and Interact",
            topic: "Jobs in Algeria",
          },
        },
      },
      authHeaders
    ),
    mockEnv
  );
  const body5 = await res5.json();
  const plan5 = body5.result.structuredContent;
  assert.equal(plan5.header.duration, "45 mn");
  assert.equal(
    plan5.stages.reduce((acc, s) => acc + s.minutes, 0),
    45
  );
});
