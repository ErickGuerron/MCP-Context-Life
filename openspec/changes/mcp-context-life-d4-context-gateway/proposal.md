# Proposal: MCP Context-Life D4 Context Gateway

## Intent

Convertir Context-Life de un buscador de memorias genérico a un **Middleware de Ciclo de Vida de Contexto** que actúa como "RAM de Trabajo" técnico, complementando la "memoria a largo plazo" de Engram. El objetivo es que Context-Life siempre aporte valor, independientemente de si Engram está activo.

## Problem Statement

### Diagnóstico Actual

1. **Conflicto arquitectural**: Si Engram está activo y encuentra contexto, Context-Life queda como código muerto. Esto viola el principio de que ambas herramientas deben ser **independientes y complementarias**.

2. **Rol indefinido**: Context-Life actualmente compite con Engram en el mismo espacio (búsqueda de contexto), causando canibalización.

3. **Falta de especialización**: Sin un rol claro, el LLM prioriza Engram (core de Gentle AI) dejando a Context-Life sin uso real.

### Consecuencia

```
gentle-ai detectado → engram FIRST → si encuentra → context-life = código muerto
```

## Solution: D4 Context Gateway

### Modelo D4 (Decision-Driven Dynamic Delivery)

Context-Life actúa como **Gobernador de Contexto** que analiza el estado del hilo actual y aplica niveles de intervención basados en la salud del contexto:

| Nivel D4 | Condición | Acción | Resultado |
|----------|-----------|--------|-----------|
| **NOP** | Contexto limpio (<2k tokens) | No hace nada | Ahorra latencia |
| **LIGHT** | Mensajes 5-15, tokens moderados | Resumen básico de últimos mensajes | Mantiene coherencia |
| **REQUIRED** | Mensajes 15-50, tokens crecidos | Filtra metadatos + aplica summary_objective | Comprensión precisa |
| **CRITICAL** | >50 mensajes, >80% presupuesto | Purga historial, re-inyecta Engramas + estado código | Previene colapso |

### Roles complementarios

```
ENGRAM (Memoria a Largo Plazo):
  - Decisiones históricas
  - Bugs resueltos
  - Reglas globales del proyecto
  → Busca "qué pasó hace un mes"

CONTEXT-LIFE (RAM de Trabajo):
  - Task States actuales
  - Code Blueprints del hilo
  - Metadatos técnicos (file_hash, token_cost, summary_objective)
  → Busca "cómo comprimir los últimos 20 mensajes para el siguiente agente"
```

## Scope

### In Scope
- D4 Governance Engine: nivel NOP/LIGHT/REQUIRED/CRITICAL basado en análisis de contexto
- Metadatos técnicos indexados: file_hash, summary_objective, token_cost, chunk_index, task_state
- Skill de integración corregido: no más "código muerto cuando Engram está activo"
- Contexto enriquecido para sub-agentes: ContextSlice con metadata técnica
- Rollo de contexto por nivel D4: compresión selectiva vs purge total

### Out of Scope
- No rediseñar la arquitectura base de hexagonal
- No implementar provider adapters (ya en RFC-003)
- No crear UI compleja — solo metadata y governance

## Capabilities

### New Capabilities

- `d4-governance-engine`: Análisis del estado del contexto y aplicación de nivel D4
- `technical-metadata-index`: Indexación de metadatos técnicos (file_hash, task_state, summary_objective)
- `context-slice-enriched`: ContextSlice con campos técnicos para sub-agentes
- `engram-complement-mode`: Context-Life actúa siempre en rol complementario a Engram

### Modified Capabilities

- `context-life-integration`: Corregir skill para usar D4 y no canibalizar Engram
- `orchestrator_detector`: Detectar nivel D4 y pasar hints al orquestador

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `mmcp/orchestration/d4_governance.py` | New | D4 engine: análisis + nivel + acción |
| `mmcp/domain/context_slice.py` | Modified | Agregar metadata técnica |
| `skills/context-life-integration/SKILL.md` | Modified | Corregir rol, D4, no canibalización |
| `mmcp/infrastructure/context/rag_engine.py` | Modified | Indexar metadata técnica |

## Dependencies

- `openspec/specs/optimization/RFC-002-optimization-orchestration.md` — D4 concepto base
- `openspec/changes/mcp-context-life-auto-invocation-improvements/` — fases 9-10 pendientes
- `openspec/specs/operations/rfc-session-cache-and-usage-tui-v1.md` — telemetry schema

## Success Criteria

- [ ] Context-Life aporta valor cuando Engram está activo (no código muerto)
- [ ] D4 niveles aplicados correctamente según estado del contexto
- [ ] Metadatos técnicos indexados y usados para decisiones
- [ ] Orchestrator recibe D4 hints para decisiones de handoff

## Rollback Plan

Feature flags:
- `d4_governance.enabled: false` → behavior anterior (sin D4)
- `d4_governance.level_override` → forzar nivel para testing

## Strict TDD Mode

**ENABLED** — cada feature requiere test primero.

## Delivery Strategy

Chained PRs si >400 líneas. Este spec se implementa DESPUÉS de `mcp-context-life-auto-invocation-improvements`.

---

**Status**: Draft — para implementar post auto-invocation-improvements
**Priority**: High — corrige canibalización con Engram