# Proposal: Context-Life MCP Auto-Invocación por Stack

## Intent

Completar el mecanismo de auto-invocación del MCP context-life en cada prompt, detectando automáticamente el tipo de entorno (solo-agente o multi-agente con delegate()) y aplicando la estrategia correcta de gobernanza de contexto sin intervención manual.

## Scope

### In Scope
- Detección automática de stack: solo-agente vs orchestrator con delegate()
- Tool `autoinvoke_context` expuesta por el servidor MCP (session_id server-side)
- Skill `context-life.md` para solo-agents
- Sub-agente `context-life-advisor` (stack-agnóstico) para orchestrators con delegate()
- Persistencia forzada al final de cada prompt (sleep_context)

### Out of Scope
- Modificar agentes externos (Windsurf, Codex, etc.)
- Orquestación SDD completa (solo auto-invocación MCP)
- Gobernanza absoluta (depende del agente host)
- Transiciones mid-session (v2)

## Capabilities

### New Capabilities
- `context-auto-invocation`: MCP tool que se invoca automáticamente al inicio de cada prompt sin intervención del agente
- `context-life-governance`: Skill que define reglas de "sleep & wake" para solo-agentes y "handoff" para orchestrators con delegate()

### Modified Capabilities
- None

## Approach

### 1. Detección de Stack

Reusar `orchestrator_detector.py` de `gentle-ai-stack-detection`:
- IF `GENTLE_AI_ACTIVE=1` (env var) AND `.gga` file exists in `cwd` → `gentle-ai`
- ELSE (including partial matches) → `solo-agent`

Custom orchestrators set `GENTLE_AI_ACTIVE=1` if they implement `delegate()`.

### 2. Tool `autoinvoke_context`

El servidor MCP expone:
```python
@mcp.tool()
def autoinvoke_context(stack_type: str) -> dict:
    """
    Session ID es derivado server-side (no se pasa como parámetro).
    Retorna ContextPack con context_items, session_state, recommendations, active_session_id.
    """
```

Session ID derivation (server-side):
- IF `ENGRAM_SESSION_ID` env var exists → use directly
- ELSE IF `.context-session.id` file exists and < 12 hours old → read from file
- ELSE → compute `hash(cwd + current_timestamp)`, persist to `.context-session.id`

### 3. Skill `context-life.md` (Solo-Agent)

Crear en `skills/context-life/SKILL.md`:

**Wake (Zero-Step):**
- Agent MUST call `autoinvoke_context(stack_type="solo-agent")` as ABSOLUTE FIRST token
- MUST NOT analyze prompt, write code, or output text until ContextPack received

**Sleep:**
- Agent MUST call `sleep_context()` at task end
- Chat history treated as volatile and unreliable

### 4. Sub-Agente `context-life-advisor` (Orchestrator con delegate())

El advisor es **stack-agnóstico**: funciona con gentle-ai o cualquier orchestrator que exponga `delegate()`.

**System Prompt:**
```
You are the `context-life-advisor` sub-agent. Your role is to optimize and validate context
before the orchestrator begins working on a task.

When you receive a raw user request from the orchestrator:
1. Immediately call `autoinvoke_context(stack_type="<stack_type>")`
2. Return the resulting ContextPack to the orchestrator as ground truth.
Do not attempt to write code.
```

**Registration:** Via `context_life_installer.py` appending to `opencode.json` agents array.

### 5. Advisor Workflow (Zero-Step Routing)

```
Orchestrator receives prompt
  └─> stack_detector.detect()
  └─> IF orchestrator supports delegate():
        └─> delegate(agent="context-life-advisor", prompt=raw_user_prompt)
        └─> Advisor calls autoinvoke_context(stack_type)
        └─> Advisor returns ContextPack to orchestrator
        └─> Orchestrator proceeds with enriched context
      ELSE (solo-agent):
        └─> Skill injects Zero-Step instruction
        └─> LLM calls autoinvoke_context as first token
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `mmcp/presentation/mcp/server.py` | Modified | Agregar tool `autoinvoke_context` (sin session_id en firma) |
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modified | Reusar detección existente con ELSE explícito |
| `skills/context-life/` | New | Skill para solo-agents |
| `opencode.json` agents array | Modified | Append `context-life-advisor` sub-agent definition |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Latencia por auto-invocación | Medium | Flag `DISABLE_AUTOINVOKE=1` para desactivar |
| Orchestrator sin delegate() | N/A | Fallback a skill-based governance |
| Session amnesia on server restart | Low | `.context-session.id` file con TTL 12h |

## Rollback Plan

1. Si la tool genera latencia: agregar `DISABLE_AUTOINVOKE=1` al entorno
2. Si el skill genera conflictos: desinstalar skill via eliminación de archivo
3. Ningún cambio a herramientas existentes (`intercept_user_request`, etc.)

## Dependencies

- `orchestrator_detector.py` (gentle-ai-stack-detection, existente)
- `autoinvoke_context`, `sleep_context` (MCP tools nuevos)
- Engram para persistencia de sesión multi-agente

## Success Criteria

- [ ] `autoinvoke_context` se llama automáticamente al inicio de cada prompt
- [ ] Skill `context-life.md` aplica reglas Zero-Step para solo-agents
- [ ] `context-life-advisor` funciona con cualquier orchestrator con delegate()
- [ ] Estado persiste entre prompts (`.context-session.id` file)
- [ ] `DISABLE_AUTOINVOKE=1` desactiva auto-invocación sin romper otras funciones
- [ ] Tests de regresión para auto-invocación pasan