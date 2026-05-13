# Proposal: MCP Context-Life Auto-Invocation Improvements

## Intent

Resolver gaps, optimizaciones y features complementarias descubiertas durante la implementación de la auto-invocación base de context-life, mejorando latencia, gobernanza, métricas y soporte multi-stack.

## Scope

### In Scope
- Cache layer para auto-invoke con TTL y deduplicación
- Skill de gobernanza mejorado con más triggers e intención de usuario
- Usage tracking dashboard en TUI
- Soporte para Cursor AI, Windsurf, Codex AI
- Persistencia cross-session más robusta
- Integración con sistema de telemetry existente
- Dashboard TUI de gobernanza

### Out of Scope
- No re-diseñar la arquitectura base (ya definida en SDD principal)
- No implementar UI compleja — solo dashboard básico TUI
- No implementación de provider adapters (ya en RFC-003)

## Capabilities

### New Capabilities
- `auto-invoke-cache`: Cache con TTL para resultados de auto-invoke, evita re-ejecución de llamadas idénticas
- `governance-triggers`: Skill expandido con triggers adicionales y detección de intención de usuario
- `usage-tracking`: Métricas de invocaciones, tokens filtrados, savings por host/agent/provider
- `multi-stack-detection`: Detección de Cursor AI, Windsurf, Codex AI como hosts MCP
- `cross-session-state`: Persistencia mejorada del file system adapter para estados más robustos
- `governance-dashboard`: Pantalla TUI que muestra estado actual del MCP y sesión

### Modified Capabilities
- `context-slice`: Extender para soportar auto-invoke context con cache y latencia optimizada
- `telemetry-service`: Integrar auto-invoke events con el pipeline de telemetría existente

## Approach

1. **Cache Layer** (`mmcp/infrastructure/context/auto_invoke_cache.py`): Implementar TTL cache con key hashing, deduplicación de invocaciones idénticas, y lazy loading de módulos pesados.

2. **Skill Enhancement** (`skills/context-life/governance.md`): Agregar más triggers (patrones de conversación, longitud de mensajes, keywords de ansiedad), detección de intención via embeddings simples.

3. **Usage Metrics** (`mmcp/application/features/telemetry/service.py`): Trackear invocaciones auto-invoke, tokens filtrados, savings. Exponer via MCP resources y CLI.

4. **Stack Expansion** (`mmcp/infrastructure/environment/orchestrator_detector.py`): Detectar Cursor AI (variable env `CURSOR_DIR`), Windsurf (variable env `WINDURF_DATA_DIR`), Codex AI (process name `codex-cli`).

5. **State Persistence** (`mmcp/infrastructure/persistence/session_store.py`): Mejorar el file system adapter conJournaling de estados, atomic writes, y recovery on crash.

6. **Governance Dashboard** (`mmcp/presentation/cli/ui/`): Nueva pantalla TUI que muestra estado actual del MCP, sesiones activas, cache hit rate, y alertas de gobernanza.

7. **Telemetry Integration** (`mmcp/infrastructure/telemetry/telemetry_service.py`): Integrar auto-invoke events al servicio de telemetría existente, usar el schema de RFC-003.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `mmcp/infrastructure/context/` | New | `auto_invoke_cache.py` — cache layer |
| `mmcp/application/features/context/service.py` | Modified | Soporte cache para auto-invoke |
| `skills/context-life/governance.md` | Modified | Triggers expandidos, detección de intención |
| `mmcp/infrastructure/environment/orchestrator_detector.py` | Modified | Detección multi-stack |
| `mmcp/infrastructure/persistence/session_store.py` | Modified | Cross-session state robusto |
| `mmcp/infrastructure/telemetry/telemetry_service.py` | Modified | Auto-invoke event integration |
| `mmcp/presentation/cli/ui/` | Modified | Governance dashboard |
| `openspec/specs/operations/rfc-session-cache-and-usage-tui-v1.md` | Modified | TUI specs ya existentes |
| `openspec/specs/telemetry/RFC-003-telemetry-budget-integrity-and-scalability.md` | Reference | Canonical telemetry schema |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Complexity growth en skill de gobernanza | Medium | Modularizar triggers, feature flags para cada uno |
| Overhead de métricas si no se diseñan bien | Medium | Sampling rate configurable, async event emission |
| Cache invalidation complexity | Low | TTL + manual invalidation + config flags |
| Multi-stack detection falsos positivos | Low | Validar contra múltiples signals antes de confirmar |

## Rollback Plan

Cada mejora es independiente y se puede disable via config flags:
- `auto_invoke_cache.enabled: false` — desactiva cache layer
- `governance.triggers.enabled: false` — desactiva triggers adicionales
- `usage_tracking.enabled: false` — desactiva métricas
- `multi_stack_detection.enabled: false` — desactiva detección extendida
- `cross_session_state.enabled: false` — usa solo memoria
- `governance_dashboard.enabled: false` — oculta dashboard

Para rollback manual: reverting change set individual en git, cada feature es un commit atómico.

## Dependencies

- `openspec/specs/telemetry/RFC-003-telemetry-budget-integrity-and-scalability.md` — schema de telemetría
- `openspec/specs/operations/rfc-session-cache-and-usage-tui-v1.md` — TUI existente a extender
- `openspec/specs/architecture/hexagonal-refactor-plan.md` — arquitectura base

## Success Criteria

- [ ] Cache de auto-invoke reduce latencia en ≥50% para invocaciones repetidas
- [ ] Skill de gobernanza detecta al menos 5 nuevos patrones de intención
- [ ] Usage dashboard muestra métricas por host, agent, provider, model
- [ ] Detección de Cursor, Windsurf, Codex funciona correctamente
- [ ] Estado persiste correctamente entre sesiones (verify con cold restart)
- [ ] Telemetry integration no introduce overhead measurable (<5ms)
- [ ] Governance TUI muestra estado actual sin errores
- [ ] Todos los feature flags funcionan independently

## Strict TDD Mode

**ENABLED** — cada feature requiere:
1. Test primero que falla (cache miss scenario, trigger detection, stack detection)
2. Implementación mínima que hace pasar el test
3. Refactor sin cambiar comportamiento

## Delivery Strategy

Review budget: 400 líneas. Si el change set excede este límite, se generarán chained PRs usando `chained-pr` skill. Cada feature (cache, skill, metrics, stack, persistence, dashboard, telemetry) será un slice independiente.