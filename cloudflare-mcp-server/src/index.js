/**
 * src/index.js
 * ============
 * Cloudflare Worker MCP Server (Streamable HTTP JSON-RPC 2.0) for the
 * AITADZ Primary School English Teacher Assistant (aitadz.pro).
 *
 * Exposes:
 *   GET  /health  -> Health status JSON
 *   POST /mcp     -> MCP JSON-RPC 2.0 endpoint (initialize, tools/list, tools/call)
 *
 * AI Backends (in priority order):
 *   1. Optional external OpenAI-compatible gateway (env.LLM_BASE_URL + env.LLM_API_KEY)
 *   2. Native Cloudflare Workers AI binding (env.AI.run)
 *   3. Deterministic Algerian Didactic Guide fallback synthesizer
 */

const PROTOCOL_VERSION = "2024-11-05";
const DEFAULT_WORKERS_AI_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
const OBJECTIVE_PREFIX = "By the end of the session, learners will be able to";

const LEVEL_GUIDELINES = {
  "3PS": {
    level: "3PS - Year 3 Primary (Key Stage 1)",
    guide: "Didactic Guide of English - Key Stage 1 Primary Education (2023)",
    duration_minutes: 60,
    duration_label: "60 mn",
    project: "My Pictionary",
    handwriting:
      "Print/script handwriting ONLY by letter formation families (lowercase then UPPERCASE). No cursive and no free paragraph writing.",
    rules: [
      "Every session totals exactly 60 minutes across its ordered stages.",
      "No written text on the board during Session 1 (I Sing & Have Fun / I Listen & Repeat).",
      "Phonemic awareness covers isolating, blending, and segmenting VC/CVC sounds only; NO sight words.",
      "Grammar is taught implicitly via formulaic chunks — never explicit grammar lectures.",
      "Non-monetary classroom gamification only: Gold Stars, Explorer Badges, Team Points, Stickers.",
    ],
  },
  "4PS": {
    level: "4PS - Year 4 Primary (Key Stage 1)",
    guide: "Didactic Guide of English - Key Stage 1 Primary Education (2023)",
    duration_minutes: 60,
    duration_label: "60 mn",
    project: "Mini Dictionary",
    handwriting:
      "Connected/joined (cursive) handwriting used to complete topic-related forms (ID cards, family trees, health forms) rather than free essays.",
    rules: [
      "Every session totals exactly 60 minutes across its ordered stages.",
      "Session 3 (I Read & Enjoy) runs structured, inclusive reading games with rules demonstrated first.",
      "Session 4 (I Read & Write) focuses on completing a topic-related form in cursive after reviewing Session 2 text.",
      "Short texts scale from ~30 to ~40 words; NO sight-word memorization drills.",
      "Non-monetary classroom gamification only: Gold Stars, Explorer Badges, Team Points, Stickers.",
    ],
  },
  "5PS": {
    level: "5PS - Year 5 Primary (Key Stage 3)",
    guide: "Didactic Guide of English - Key Stage 3 Primary Education (2024)",
    duration_minutes: 45,
    duration_label: "45 mn",
    project: "My Booklet",
    handwriting:
      "Joined handwriting transforming notes from a form into simple accurate sentences (~10/15/20 words) linked into a short message (writing for reinforcement).",
    rules: [
      "Every session totals exactly 45 minutes across its ordered stages.",
      "Writing is 'writing for reinforcement' (form notes to short sentences), NOT free essay writing.",
      "Never use learner-facing meta-terms ('skim', 'scan', 'gist', 'prediction') when addressing learners.",
      "Grammar is discovered inductively and implicitly in context — never explicit rules or metalanguage.",
      "Non-monetary classroom gamification only: Gold Stars, Explorer Badges, Team Points, Stickers.",
    ],
  },
};

const TOOLS = [
  {
    name: "generate_lesson_plan",
    description:
      "Generate a structured, Algerian Didactic-Guide-compliant primary school English lesson plan (60 mn for 3PS/4PS; 45 mn for 5PS) ready for DOCX export.",
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: true,
    },
    inputSchema: {
      type: "object",
      properties: {
        grade: {
          type: "string",
          enum: ["3PS", "4PS", "5PS"],
          description: "Algerian primary grade level: 3PS, 4PS, or 5PS.",
        },
        sequence: { type: "string", description: "Official sequence label." },
        sequence_id: { type: "string", description: "Canonical sequence ID." },
        section: { type: "string", description: "Official section label." },
        section_id: { type: "string", description: "Canonical section ID." },
        session: { type: "string", description: "Official session title." },
        session_id: { type: "string", description: "Canonical session ID." },
        topic: {
          type: "string",
          description: "Specific lesson topic, vocabulary, or target chunk.",
        },
        duration_minutes: {
          type: "integer",
          description: "60 for 3PS/4PS, 45 for 5PS.",
        },
        system_prompt: {
          type: "string",
          description: "Didactic Guide system instructions supplied by the client.",
        },
        user_prompt: {
          type: "string",
          description: "Lesson parameters & stage template supplied by the client.",
        },
        didactic_schema: {
          type: "object",
          description: "Structured schema constraints (word targets, phonics, stages).",
        },
      },
      required: ["grade", "topic"],
    },
  },
  {
    name: "get_didactic_guidelines",
    description:
      "Retrieve official Algerian Primary School English Didactic Guide constraints, session timings (60 mn for 3PS/4PS, 45 mn for 5PS), handwriting rules, and non-monetary gamification rules.",
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: "object",
      properties: {
        grade: {
          type: "string",
          enum: ["3PS", "4PS", "5PS"],
          description: "Target primary school grade level.",
        },
      },
      required: ["grade"],
    },
  },
];

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers":
      "Content-Type, Accept, CF-Access-Client-Id, CF-Access-Client-Secret, Mcp-Session-Id",
  };
}

function jsonResponse(payload, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(),
      ...extraHeaders,
    },
  });
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const enc = new TextEncoder();
  const bufA = enc.encode(a);
  const bufB = enc.encode(b);
  if (bufA.length !== bufB.length) return false;
  let diff = 0;
  for (let i = 0; i < bufA.length; i++) {
    diff |= bufA[i] ^ bufB[i];
  }
  return diff === 0;
}

/**
 * Verify Cloudflare Access Service Token headers when configured in Worker secrets.
 * If neither CF_ACCESS_CLIENT_ID nor CF_ACCESS_CLIENT_SECRET is bound on the Worker,
 * authentication is assumed to be enforced upstream by Cloudflare Access / MCP Portal.
 */
export function verifyAccessHeaders(request, env = {}) {
  const expectedId = (env.CF_ACCESS_CLIENT_ID || "").trim();
  const expectedSecret = (env.CF_ACCESS_CLIENT_SECRET || "").trim();
  if (!expectedId && !expectedSecret) {
    return true;
  }
  const providedId = (request.headers.get("CF-Access-Client-Id") || "").trim();
  const providedSecret = (request.headers.get("CF-Access-Client-Secret") || "").trim();
  if (!expectedId || !expectedSecret) {
    return false;
  }
  return timingSafeEqual(providedId, expectedId) && timingSafeEqual(providedSecret, expectedSecret);
}

export function normalizeGrade(rawGrade) {
  const g = String(rawGrade || "3PS").trim().toUpperCase();
  if (g.includes("5")) return "5PS";
  if (g.includes("4")) return "4PS";
  return "3PS";
}

export function extractJsonObject(rawInput) {
  if (!rawInput) return null;
  if (typeof rawInput === "object" && !Array.isArray(rawInput)) {
    if (rawInput.header || rawInput.stages || rawInput.whiteboard_layout) {
      return rawInput;
    }
    if (typeof rawInput.response === "string") {
      return extractJsonObject(rawInput.response);
    }
    if (typeof rawInput.response === "object" && rawInput.response !== null) {
      return extractJsonObject(rawInput.response);
    }
    if (Array.isArray(rawInput.choices) && rawInput.choices[0]?.message?.content) {
      return extractJsonObject(rawInput.choices[0].message.content);
    }
    return null;
  }

  if (typeof rawInput !== "string") return null;
  let text = rawInput.trim();
  if (!text) return null;

  const fence = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (fence) {
    text = fence[1].trim();
  }

  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed;
    }
  } catch {
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start !== -1 && end > start) {
      try {
        const sliced = JSON.parse(text.slice(start, end + 1));
        if (sliced && typeof sliced === "object" && !Array.isArray(sliced)) {
          return sliced;
        }
      } catch {
        return null;
      }
    }
  }
  return null;
}

function scrubMetaTerms(text) {
  return String(text || "")
    .replace(/\bskimming\b/gi, "reading quickly for the main idea")
    .replace(/\bskim\b/gi, "read quickly for the main idea")
    .replace(/\bscanning\b/gi, "looking carefully for specific details")
    .replace(/\bscan\b/gi, "look carefully for specific details")
    .replace(/\bgist\b/gi, "overall idea")
    .replace(/\bpredictions\b/gi, "initial guesses")
    .replace(/\bprediction\b/gi, "initial guess")
    .replace(/\bSV\s+agreement\b/gi, "subject-action word matching")
    .replace(/\bsubject[-\s]+verb\s+agreement\b/gi, "subject-action word matching")
    .replace(/\bsubject[-\s]+verb\s+patterns?\b/gi, "chunk and word-order patterns")
    .replace(/\bpresent\s+simple(?:\s+tense)?\b/gi, "target action chunks")
    .replace(/\bsimple\s+present(?:\s+tense)?\b/gi, "target action chunks")
    .replace(/\bpresent\s+continuous(?:\s+tense)?\b/gi, "ongoing action chunks (-ing)")
    .replace(/\bpresent\s+progressive(?:\s+tense)?\b/gi, "ongoing action chunks (-ing)")
    .replace(/\bprepositions?(?:\s+of\s+(?:place|location|time|movement))?\b/gi, "location and time words (in, on, at)")
    .replace(/\bpossessive\s+adjectives?\b/gi, "ownership words (my, your, his, her)")
    .replace(/\b(?:personal|subject)\s+pronouns?\b/gi, "person words (I, you, he, she)")
    .replace(/\bimperatives?\b/gi, "action instructions");
}

function sanitizeNonMonetary(text) {
  return String(text || "")
    .replace(/\bprize\s+money\b/gi, "gold stars and explorer badges")
    .replace(/\bcrypto(?:currency)?\b/gi, "explorer badges")
    .replace(/\bdollar(?:s)?\b/gi, "team points")
    .replace(/\bdinar(?:s)?\b/gi, "team points")
    .replace(/\beuro(?:s)?\b/gi, "team points")
    .replace(/\bcoin(?:s)?\b/gi, "gold stars")
    .replace(/\bbanknote(?:s)?\b/gi, "stickers")
    .replace(/\bcash\b/gi, "team points")
    .replace(/\bmoney\b/gi, "team points")
    .replace(/\btoken(?:s)?\b/gi, "explorer badges");
}

function ensureObjectiveFormula(rawObjective, topic) {
  const cleaned = String(rawObjective || "").trim();
  if (!cleaned) {
    return `${OBJECTIVE_PREFIX} identify and use key language related to ${topic}.`;
  }
  if (cleaned.toLowerCase().startsWith(OBJECTIVE_PREFIX.toLowerCase())) {
    return OBJECTIVE_PREFIX + cleaned.slice(OBJECTIVE_PREFIX.length);
  }
  return `${OBJECTIVE_PREFIX} ${cleaned.charAt(0).toLowerCase()}${cleaned.slice(1)}`;
}

function buildRichFallbackProcedure(stageName, topic, interaction) {
  const lower = String(stageName || "").toLowerCase();
  if (lower.includes("exit ticket") || lower.includes("feedback")) {
    return (
      `Activity 1 (Ticket to Leave): Show 3 flashcards for "${topic}" and prompt each pupil individually.\n` +
      `T: "Share one word or phrase you learnt today and show your confidence card!"\n` +
      `Ls: Produce one target item aloud and raise a green/amber/red smiley card to earn a Gold Star Sticker.`
    );
  }
  if (lower.includes("warmer") || lower.includes("warm-up") || lower.includes("sing")) {
    return (
      `Activity 1 (VAKT Energizer): Display topic visuals for "${topic}" and run a brisk song/flashcard chant.\n` +
      `T: "Look, listen, and clap when you hear the key words!"\n` +
      `Ls: Sing/chant together in ${interaction || "Whole class"} with gestures to earn Team Points.`
    );
  }
  return (
    `Activity 1 (Visual Context & Model): Present "${topic}" using flashcards, realia, and mimes (no explicit grammar lectures).\n` +
    `Listening / Reading Model: Amine: "Look at ${topic}!" | Lina: "Is it nice?" | Amine: "Yes, it is great!"\n` +
    `Activity 2 (Guided Practice & Scaffolding): Lead choral then pair practice in ${interaction || "T-Ls / Pair"} checking pronunciation, word boundaries, and meaning.\n` +
    `Activity 3 (Interactive Classroom Task & Star Challenge): Pairs/teams complete 4 target card prompts and earn Gold Stars & Explorer Badges.\n` +
    `T: "Great teamwork! Check your answers together." | Ls: Verify answers and report aloud.`
  );
}

function buildBaselineStages(args, targetMinutes) {
  const schemaStages = args?.didactic_schema?.stages;
  const topic = String(args?.topic || "the lesson topic").trim();

  if (Array.isArray(schemaStages) && schemaStages.length > 0) {
    const mins = schemaStages.map((s) => Number(s.minutes) || 5);
    const total = mins.reduce((acc, v) => acc + v, 0);
    if (total !== targetMinutes && total > 0) {
      const scaled = mins.map((m) => Math.max(1, Math.round((m * targetMinutes) / total)));
      const diff = targetMinutes - scaled.reduce((a, b) => a + b, 0);
      const maxIdx = scaled.indexOf(Math.max(...scaled));
      scaled[maxIdx] = Math.max(1, scaled[maxIdx] + diff);
      for (let i = 0; i < scaled.length; i++) mins[i] = scaled[i];
    }
    return schemaStages.map((s, idx) => ({
      minutes: mins[idx],
      time: `${mins[idx]} mn`,
      stage: String(s.stage || `Stage ${idx + 1}`),
      procedure: buildRichFallbackProcedure(s.stage, topic, s.interaction),
      interaction: String(s.interaction || "T-Ls"),
      competency_materials: "Flashcards, realia, whiteboard, slates",
    }));
  }

  if (targetMinutes === 60) {
    return [
      {
        minutes: 15,
        time: "15 mn",
        stage: "Stage 1: Warm-up (Warmer)",
        procedure:
          `Activity 1 (Visual Song / Chant): Pin flashcards for "${topic}" and lead a 2-pass rhythm chant.\n` +
          `T: "Clap and point when you hear our new topic words!" | Ls: Sing/chant with mimes to win Team Points.`,
        interaction: "T-Ls / Whole class",
        competency_materials: "Flashcards, song audio",
      },
      {
        minutes: 20,
        time: "20 mn",
        stage: "Stage 2: Presentation & Discovery (Install Resources)",
        procedure:
          `Activity 1 (Visual Context & Input): Introduce "${topic}" through flashcards, realia, and a short 4-line dialogue.\n` +
          `Listening Script: Amine: "Hello, Lina! Look at ${topic}!" | Lina: "Wow, I like it!"\n` +
          `Activity 2 (Choral -> Group -> Individual Drilling): Model chunks and target sounds; pupils repeat chorally and individually.\n` +
          `T: "Repeat after me with gestures!" | Ls: Echo chunks cleanly.`,
        interaction: "T-Ls / Ls-T",
        competency_materials: "Flashcards, puppets, board",
      },
      {
        minutes: 20,
        time: "20 mn",
        stage: "Stage 3: Guided Practice & Classroom Game (Install Resources)",
        procedure:
          `Activity 1 (Pair Card Matching): Pairs match 4 visual cue cards to target chunks for "${topic}".\n` +
          `Activity 2 (Friendly Star Challenge — Board Race): Teams race in turns to identify/read cards and earn Gold Stars & Explorer Badges.\n` +
          `T: "Ready, set, point and say!" | Ls: Collaborate respectfully and pronounce items clearly.`,
        interaction: "Pair / Group",
        competency_materials: "Word/picture cards, Star Tracker",
      },
      {
        minutes: 5,
        time: "5 mn",
        stage: "Stage 4: Feedback / Exit Ticket (Assessment)",
        procedure:
          `Activity 1 (Ticket to Leave): Each pupil produces one target chunk for "${topic}" and holds up a green/amber/red smiley card.\n` +
          `Activity 2 (Positive Closure): Award final Star Stickers on the team chart.`,
        interaction: "Individual / T-Ls",
        competency_materials: "Exit Ticket cards, stickers",
      },
    ];
  }

  return [
    {
      minutes: 5,
      time: "5 mn",
      stage: "Stage 1: Warm-up (Warmer)",
      procedure:
        `Activity 1 (Phonemic Flash Game): Flash 4 cards for "${topic}" and guide sound blending/segmenting.\n` +
        `T: "Sound it out together!" | Ls: Blend sounds orally for Team Points.`,
      interaction: "T-Ls",
      competency_materials: "Flashcards",
    },
    {
      minutes: 15,
      time: "15 mn",
      stage: "Stage 2: Discovery & Modelling (Install Resources)",
      procedure:
        `Activity 1 (Visual Anticipation via Think-Pair-Share): Show 3 pictures for "${topic}" and gather initial guesses.\n` +
        `Activity 2 (Implicit Noticing): Present the short text/script and use Who/What/Where leading questions (zero grammar labels).\n` +
        `Listening / Reading Model: Amine: "Today we explore ${topic}." | Meriem: "Let's look closely!"`,
      interaction: "T-Ls / Pair (TPS)",
      competency_materials: "Text/audio prompt, flashcards",
    },
    {
      minutes: 20,
      time: "20 mn",
      stage: "Stage 3: Practice & Communicative Use (Install Resources / Assessment)",
      procedure:
        `Activity 1 (Controlled Substitution Drill): Model chunks with finger word boundaries and hand intonation; pairs substitute prompts.\n` +
        `Activity 2 (Guided Gap-Fill / Anagram Task): Pairs complete 3 short items with immediate feedback.\n` +
        `Activity 3 (Personalized Role-Play): Pairs act out a real-life mini-dialogue on "${topic}" to earn Gold Stars & Explorer Badges.`,
      interaction: "Pair / Group",
      competency_materials: "Cue cards, slates, Star Chart",
    },
    {
      minutes: 5,
      time: "5 mn",
      stage: "Stage 4: Feedback / Exit Ticket (Assessment)",
      procedure:
        `Activity 1 (Ticket to Leave): Learners share one thing they learnt and one challenge on an Exit Ticket card.\n` +
        `T: "Great effort today!" | Ls: Hand in exit cards and collect Star Stickers.`,
      interaction: "Individual / T-Ls",
      competency_materials: "Exit Ticket slips, stickers",
    },
  ];
}

function resolveOfficialDomains(sessionText, rawDomains) {
  const cleaned = String(rawDomains || "").trim();
  if (/comprehension|production/i.test(cleaned)) {
    return cleaned;
  }
  const s = String(sessionText || "").toLowerCase();
  if (s.includes("write")) return "Written Comprehension / Written Production";
  if (s.includes("read")) return "Written Comprehension / Oral Production";
  return "Oral Comprehension / Oral Production";
}

function isGenericWhiteboardPanel(text) {
  const low = String(text || "").trim().toLowerCase();
  if (low.length < 20) return true;
  return (
    low.includes("date, sequence/section/session") ||
    low.includes("visual flashcards & target vocabulary") ||
    low.includes("core model chunks / text / form") ||
    low.includes("classroom star & team points tracker + learner slate practice")
  );
}

export function normalizePlan(rawPlan, args = {}, targetMinutes = null) {
  const grade = normalizeGrade(args.grade);
  const guide = LEVEL_GUIDELINES[grade];
  const expectedMinutes = Number(targetMinutes || guide.duration_minutes);
  const topic = String(args.topic || args.section || "Primary English").trim();
  const baselineStages = buildBaselineStages(args, expectedMinutes);

  const rawHeader = rawPlan?.header && typeof rawPlan.header === "object" ? rawPlan.header : {};
  const sessionLabel = String(args.session || rawHeader.session || "Lesson Session");
  const header = {
    class_profile: `${grade} Primary Class`,
    level: guide.level,
    number_of_learners: "[To be completed by teacher]",
    duration: `${expectedMinutes} mn`,
    sequence: String(args.sequence || rawHeader.sequence || "Sequence 1"),
    section: String(args.section || rawHeader.section || "Section 1"),
    session: sessionLabel,
    domains: resolveOfficialDomains(sessionLabel, rawHeader.domains),
    target_competence: scrubMetaTerms(
      String(
        rawHeader.target_competence ||
          `Comprehend and interact using simple language related to ${topic}.`
      )
    ),
    session_objectives: scrubMetaTerms(ensureObjectiveFormula(rawHeader.session_objectives, topic)),
    subsidiary_objectives: scrubMetaTerms(
      String(
        rawHeader.subsidiary_objectives ||
          `Practice target phonics (${args?.didactic_schema?.phonics_target || "level phonics"}) and handwriting mechanics implicitly.`
      )
    ),
    phonics_focus: scrubMetaTerms(
      String(
        args?.didactic_schema?.phonics_target || rawHeader.phonics_focus || "Level phonics target"
      )
    ),
    core_values:
      "National Identity, National Conscience, Citizenship, Openness to the World",
    cross_curricular_competencies:
      "Intellectual, Methodological, Communicative, Personal and Social",
    teaching_materials: sanitizeNonMonetary(
      String(
        rawHeader.teaching_materials ||
          `Flashcards (${topic}), realia, audio/song, whiteboard, slates, Gold Stars & Explorer Badges`
      )
    ),
    anticipated_problems: scrubMetaTerms(
      String(
        rawHeader.anticipated_problems || "Shyness during oral turns or L1 interference."
      )
    ),
    solutions_plan_b: scrubMetaTerms(
      String(
        rawHeader.solutions_plan_b || "Use choral drilling, visual prompts, and Think-Pair-Share."
      )
    ),
  };

  let stages = Array.isArray(rawPlan?.stages) && rawPlan.stages.length > 0
    ? rawPlan.stages
    : baselineStages;

  // Enforce strict expectedMinutes total
  let mins = stages.map((st, i) => {
    const fallback = baselineStages[i]?.minutes || 5;
    const m = Number(st.minutes || String(st.time || "").match(/\d+/)?.[0] || fallback);
    return Number.isFinite(m) && m > 0 ? Math.round(m) : fallback;
  });
  if (mins.reduce((a, b) => a + b, 0) !== expectedMinutes) {
    if (stages.length === baselineStages.length) {
      mins = baselineStages.map((s) => s.minutes);
    } else {
      const sum = mins.reduce((a, b) => a + b, 0) || 1;
      mins = mins.map((m) => Math.max(1, Math.round((m * expectedMinutes) / sum)));
      const diff = expectedMinutes - mins.reduce((a, b) => a + b, 0);
      const maxIdx = mins.indexOf(Math.max(...mins));
      mins[maxIdx] = Math.max(1, mins[maxIdx] + diff);
    }
  }

  stages = stages.map((st, i) => {
    const bpProc = baselineStages[i]?.procedure || "";
    let proc = sanitizeNonMonetary(
      scrubMetaTerms(st.procedure || st.procedure_tasks || bpProc)
    );
    if (i === 0 && mins[i] <= 5 && /scavenger hunt/i.test(proc) && bpProc) {
      proc = bpProc;
    }
    return {
      minutes: mins[i],
      time: `${mins[i]} mn`,
      stage: String(st.stage || baselineStages[i]?.stage || `Stage ${i + 1}`),
      procedure: proc,
      interaction: String(st.interaction || baselineStages[i]?.interaction || "T-Ls"),
      competency_materials: sanitizeNonMonetary(
        String(st.competency_materials || baselineStages[i]?.competency_materials || "Flashcards")
      ),
    };
  });

  const rawGam = rawPlan?.gamification && typeof rawPlan.gamification === "object"
    ? rawPlan.gamification
    : {};
  const gamification = {
    title: sanitizeNonMonetary(String(rawGam.title || "AITADZ Non-Monetary Star & Explorer Quest")),
    rewards: Array.isArray(rawGam.rewards) && rawGam.rewards.length > 0
      ? rawGam.rewards.map((r) => sanitizeNonMonetary(String(r)))
      : ["Gold Stars", "Explorer Badges", "Team Points", "Stickers"],
    description: sanitizeNonMonetary(
      String(
        rawGam.description ||
          `Learners earn Gold Stars, Explorer Badges, and Team Points for active participation during "${topic}".`
      )
    ),
  };

  const rawWb = rawPlan?.whiteboard_layout && typeof rawPlan.whiteboard_layout === "object"
    ? rawPlan.whiteboard_layout
    : {};
  const defaultLeft = `Date: [Day, Date]\n${header.sequence} | ${header.section}\nTopic: ${topic}\nFlashcards & Vocabulary`;
  const defaultCenter = `Session: ${header.session}\nPhonics & Chunks: ${header.phonics_focus}`;
  const defaultRight = "Classroom Star Board:\nTeam A ★ ★ ★ | Team B ★ ★ ★\nLearner Slate Practice Zone";
  const whiteboard_layout = {
    left_panel: sanitizeNonMonetary(
      scrubMetaTerms(
        !isGenericWhiteboardPanel(rawWb.left_panel) ? rawWb.left_panel : defaultLeft
      )
    ),
    center_panel: sanitizeNonMonetary(
      scrubMetaTerms(
        !isGenericWhiteboardPanel(rawWb.center_panel) ? rawWb.center_panel : defaultCenter
      )
    ),
    right_panel: sanitizeNonMonetary(
      scrubMetaTerms(
        !isGenericWhiteboardPanel(rawWb.right_panel) ? rawWb.right_panel : defaultRight
      )
    ),
  };

  const exit_ticket = sanitizeNonMonetary(
    scrubMetaTerms(
      rawPlan?.exit_ticket ||
        `Ticket to Leave: Learners demonstrate one target word/phrase for "${topic}" and pick an emoji card.`
    )
  );

  const self_reflection = {
    what_worked: "[To be completed by teacher after session]",
    what_hindered: "[To be completed by teacher after session]",
    action_plan: "[To be completed by teacher after session]",
  };

  return {
    header,
    stages,
    gamification,
    exit_ticket,
    whiteboard_layout,
    self_reflection,
  };
}

function buildFallbackPrompts(args, expectedMinutes) {
  const grade = normalizeGrade(args.grade);
  const guide = LEVEL_GUIDELINES[grade];
  const topic = String(args.topic || "Primary English").trim();
  const sysPrompt =
    args.system_prompt ||
    `You are an Algerian Primary English Didactic Designer. Return ONLY valid JSON for a ${expectedMinutes}-minute ${grade} (${guide.guide}) lesson plan. Handwriting rule: ${guide.handwriting} Every Install Resources / Practice / Reading / Writing stage MUST contain 2-3 numbered classroom activities ('Activity 1 (...): ...\\nActivity 2 (...): ...\\nActivity 3 (...): ...'), verbatim Listening Script / Reading Text / Model Form + Answer Key, and explicit 'T:' / 'Ls:' micro-interactions. No explicit grammar lectures, no learner meta-terms (skim/scan/gist/prediction), and non-monetary classroom rewards only (Gold Stars, Explorer Badges, Team Points, Stickers).`;
  const userPrompt =
    args.user_prompt ||
    `Create a deeply detailed ${expectedMinutes}-minute ${grade} lesson plan for Sequence "${args.sequence || ""}", Section "${args.section || ""}", Session "${args.session || ""}", Topic "${topic}". Return valid JSON with keys: header, stages, gamification, exit_ticket, whiteboard_layout, self_reflection.`;
  return { sysPrompt, userPrompt };
}

async function runLessonGeneration(args, env = {}) {
  const grade = normalizeGrade(args.grade);
  const expectedMinutes = LEVEL_GUIDELINES[grade].duration_minutes;
  const { sysPrompt, userPrompt } = buildFallbackPrompts(args, expectedMinutes);
  let rawModelOutput = null;

  // 1. Optional external OpenAI-compatible gateway / provider
  if (env.LLM_BASE_URL && env.LLM_API_KEY) {
    const endpoint = `${String(env.LLM_BASE_URL).replace(/\/+$/, "")}/chat/completions`;
    const modelId = env.LLM_MODEL || "gpt-4o-mini";
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.LLM_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: modelId,
        messages: [
          { role: "system", content: sysPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.2,
        response_format: { type: "json_object" },
      }),
    });
    if (!resp.ok) {
      throw new Error(`Upstream LLM HTTP ${resp.status}`);
    }
    rawModelOutput = await resp.json();
  } else if (env.AI && typeof env.AI.run === "function") {
    // 2. Native Cloudflare Workers AI binding
    const model = env.DEFAULT_AI_MODEL || DEFAULT_WORKERS_AI_MODEL;
    rawModelOutput = await env.AI.run(model, {
      messages: [
        { role: "system", content: sysPrompt },
        { role: "user", content: userPrompt },
      ],
      temperature: 0.2,
      max_tokens: 4096,
    });
  }

  const extracted = extractJsonObject(rawModelOutput);
  return normalizePlan(extracted, args, expectedMinutes);
}

export async function handleJsonRpc(rpcBody, env = {}) {
  const id = rpcBody?.id ?? null;
  const method = rpcBody?.method;
  const params = rpcBody?.params || {};

  // JSON-RPC notifications (no id) require no response payload
  if (method === "notifications/initialized" && id === null) {
    return { status: 202, body: null };
  }

  if (method === "initialize") {
    return {
      status: 200,
      body: {
        jsonrpc: "2.0",
        id,
        result: {
          protocolVersion: PROTOCOL_VERSION,
          capabilities: {
            tools: { listChanged: false },
          },
          serverInfo: {
            name: env.SERVICE_NAME || "aitadz-mcp-server",
            version: "1.0.0",
          },
        },
      },
    };
  }

  if (method === "ping") {
    return { status: 200, body: { jsonrpc: "2.0", id, result: {} } };
  }

  if (method === "tools/list") {
    return {
      status: 200,
      body: {
        jsonrpc: "2.0",
        id,
        result: { tools: TOOLS },
      },
    };
  }

  if (method === "tools/call") {
    const toolName = params.name;
    const args = params.arguments || {};

    if (toolName === "get_didactic_guidelines") {
      const grade = normalizeGrade(args.grade);
      const guidelines = { grade, ...LEVEL_GUIDELINES[grade] };
      return {
        status: 200,
        body: {
          jsonrpc: "2.0",
          id,
          result: {
            content: [{ type: "text", text: JSON.stringify(guidelines, null, 2) }],
            structuredContent: guidelines,
            isError: false,
          },
        },
      };
    }

    if (toolName === "generate_lesson_plan") {
      try {
        const plan = await runLessonGeneration(args, env);
        return {
          status: 200,
          body: {
            jsonrpc: "2.0",
            id,
            result: {
              content: [{ type: "text", text: JSON.stringify(plan) }],
              structuredContent: plan,
              isError: false,
            },
          },
        };
      } catch (err) {
        return {
          status: 200,
          body: {
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: `Lesson generation error: ${err?.message || String(err)}`,
                },
              ],
              isError: true,
            },
          },
        };
      }
    }

    return {
      status: 200,
      body: {
        jsonrpc: "2.0",
        id,
        error: {
          code: -32601,
          message: `Unknown MCP tool: ${toolName}`,
        },
      },
    };
  }

  return {
    status: 200,
    body: {
      jsonrpc: "2.0",
      id,
      error: {
        code: -32601,
        message: `Unsupported MCP method: ${method}`,
      },
    },
  };
}

export default {
  async fetch(request, env = {}) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (request.method === "GET" && (url.pathname === "/health" || url.pathname === "/")) {
      return jsonResponse({
        status: "ok",
        service: env.SERVICE_NAME || "aitadz-cloudflare-mcp-server",
        protocol: `mcp/${PROTOCOL_VERSION}`,
      });
    }

    if (request.method === "POST" && (url.pathname === "/mcp" || url.pathname === "/")) {
      if (!verifyAccessHeaders(request, env)) {
        return jsonResponse(
          {
            jsonrpc: "2.0",
            id: null,
            error: {
              code: -32001,
              message: "Unauthorized: invalid CF-Access-Client-Id or CF-Access-Client-Secret.",
            },
          },
          401
        );
      }

      let rpcBody;
      try {
        rpcBody = await request.json();
      } catch {
        return jsonResponse(
          {
            jsonrpc: "2.0",
            id: null,
            error: { code: -32700, message: "Parse error: invalid JSON body." },
          },
          400
        );
      }

      const { status, body } = await handleJsonRpc(rpcBody, env);
      if (body === null) {
        return new Response(null, { status, headers: corsHeaders() });
      }
      return jsonResponse(body, status);
    }

    return jsonResponse({ error: "Not found" }, 404);
  },
};
