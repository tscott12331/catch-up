# Codebase Onboarding Assistant

## Overall goal

Build a local-first web application that helps an engineer understand an unfamiliar codebase by answering natural-language questions with precise, verifiable references to the repository.

The assistant should reduce the time required to locate relevant code, understand important concepts and relationships, and trace application behavior. It must ground its explanations in retrieved repository content, clearly distinguish evidence from inference, and make it easy to move from an answer to the cited source.

## Product principles

1. **Evidence before eloquence** — Prefer a smaller, well-supported answer over a confident answer without adequate repository evidence.
2. **Source navigation is central** — Every material claim should lead back to a file, symbol, and line range whenever possible.
3. **Code is structured data** — Preserve functions, classes, modules, imports, and other semantic boundaries during indexing instead of treating a repository as undifferentiated text.
4. **Retrieval must handle developer language** — Support both conceptual questions and exact searches for identifiers, paths, configuration keys, and error messages.
5. **Local-first and resource-conscious** — The complete development experience should run without paid APIs on a mid-tier machine.
6. **Quality must be observable** — Retrieval results, citations, latency, failures, and evaluation outcomes should be inspectable rather than hidden behind the chat interface.

## Primary user journey

1. A user adds a local repository or an allowed Git repository.
2. The application analyzes its files and builds a searchable index.
3. The user sees indexing progress and a basic repository overview.
4. The user asks a question about architecture, behavior, ownership, or implementation.
5. The system retrieves relevant source material and produces a grounded answer.
6. The user inspects cited passages in a source viewer and asks follow-up questions.
7. When the repository changes, the user can update the index without rebuilding unrelated content.

## System boundaries

### Frontend

The Next.js application owns the user experience:

- Repository selection and indexing status
- Conversational question-and-answer interface
- Retrieval and citation display
- Source-file browsing and line-level navigation
- Repository overview and later visualization features
- Evaluation and diagnostic views intended for the developer

### Backend

The Python uv application owns repository intelligence:

- Repository acquisition and safe file discovery
- Language detection, parsing, and structure-aware chunking
- Embedding generation and index maintenance
- Lexical, semantic, and hybrid retrieval
- Context assembly and local model interaction
- Conversations, repository metadata, jobs, and evaluation data
- Streaming API contracts consumed by the frontend

### Supporting services

Supporting services provide durable relational/vector storage, background job execution, local model inference, and local repository storage. They should remain replaceable behind narrow interfaces.

## Delivery plan

### Phase 1: Application foundation

Establish the frontend/backend boundary and a minimal vertical slice.

- Define the repository, indexing-job, conversation, message, citation, and source-passage concepts.
- Establish API error and streaming-event formats.
- Add local configuration, health checks, structured logging, and a repeatable development environment.
- Prove that the frontend can start an operation, observe progress, and render a streamed result from the backend.

**Outcome:** Both applications communicate through an explicit contract, and the project has a stable skeleton for incremental work.

### Phase 2: Repository ingestion

Turn a repository into structured, searchable records.

- Discover files while respecting ignore rules, size limits, supported languages, and binary exclusions.
- Record repository revision information so indexed content has a known source version.
- Extract language, symbols, line ranges, imports, and surrounding context where supported.
- Chunk code along semantic boundaries and documentation along document boundaries.
- Make ingestion repeatable and observable, including partial failures and cancellation.

**Outcome:** A supported repository can be indexed deterministically, and every stored passage can be traced back to its original location.

### Phase 3: Retrieval

Return useful evidence for both exact and conceptual questions.

- Implement lexical search for identifiers, paths, configuration values, and error strings.
- Implement semantic search over embedded passages.
- Combine and rank both result sets with repository and path filters.
- Expose retrieved passages and scores for debugging.
- Create a small question set with expected source files or symbols.

**Outcome:** The system consistently places relevant source passages near the top of the result set before answer generation is introduced.

### Phase 4: Grounded question answering

Generate useful explanations without losing provenance.

- Assemble context within a controlled token budget.
- Stream responses from a locally hosted model.
- Attach citations to answer claims and validate that citations refer to supplied context.
- Support conversational follow-ups without allowing chat history to replace repository evidence.
- Return an explicit insufficient-evidence response when retrieval cannot support an answer.

**Outcome:** Users receive readable answers with working, line-level citations and predictable behavior when the evidence is weak.

### Phase 5: Onboarding experience

Shape the retrieval system into a cohesive developer tool.

- Add repository management and indexing-status screens.
- Build chat history, suggested starter questions, and loading/error states.
- Add a source viewer that opens citations at the correct lines and shows surrounding context.
- Provide a repository overview based on indexed facts, such as languages, important entry points, and major directories.
- Make latency and indexing progress understandable to the user.

**Outcome:** A new user can index a repository, ask useful questions, verify answers, and recover from errors without developer intervention.

### Phase 6: Evaluation and hardening

Measure whether the assistant is trustworthy and maintainable.

- Track retrieval recall, citation validity, groundedness, response latency, and indexing duration.
- Add automated tests for parsers, chunking, retrieval, API contracts, and the primary browser workflow.
- Address repository safety concerns such as symlinks, secrets, oversized files, and untrusted content.
- Add incremental re-indexing based on file content or repository revision changes.
- Document resource requirements and expected behavior without hardware acceleration.

**Outcome:** The project has repeatable evidence of quality and can handle realistic repositories without fragile manual steps.

### Phase 7: Portfolio extensions

Add only after the core retrieval and citation experience is dependable.

- Symbol and dependency graphs
- Commit- or branch-aware questions
- Side-by-side comparison of revisions
- Generated architecture tours and onboarding checklists
- Multi-repository workspaces
- Retrieval reranking and query decomposition
- User feedback that feeds an offline evaluation set

## MVP scope

The first complete release should:

- Index one repository at a time.
- Support a deliberately limited set of common languages.
- Parse source files and Markdown documentation.
- Perform hybrid lexical and semantic retrieval.
- Answer questions using a local model.
- Stream answers to the browser.
- Cite repository paths and line ranges.
- Open citations in a read-only source viewer.
- Display indexing progress and actionable failures.
- Include a small, repeatable retrieval and citation evaluation suite.

## Initial non-goals

- Executing or building indexed repositories
- Autonomous code modification
- IDE extensions
- Organization-wide authorization and tenancy
- Internet-scale repository indexing
- Support for every programming language
- Perfect static analysis or whole-program call graphs
- Cloud deployment and distributed scaling

These are intentionally deferred so the project can first demonstrate the core claim: it helps an engineer understand code through grounded, navigable answers.

## Definition of success

The initial project goal is achieved when a developer can point the application at a representative repository, ask a curated set of onboarding questions, receive useful answers whose important claims link to correct source passages, and run the entire workflow locally without a paid service.

The portfolio should also make the engineering quality visible: a reviewer should be able to inspect retrieval inputs and results, understand system boundaries, run automated evaluations, and see how the application behaves when it lacks sufficient evidence.

