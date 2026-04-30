# Análisis final — benchmark, budget y tokens por modelo

Fecha: 2026-04-04

## Resumen ejecutivo

Estado general de las implementaciones de hoy:

- ✅ **Benchmark actual funcionando**
- ✅ **Telemetría por modelo presente**
- ✅ **Dashboard TUI mostrando savings, budget y model usage**
- ⚠️ **Budget funcional, pero no integral**
- ⚠️ **Cálculo de “tokens quemados por modelo” todavía no es 100% confiable**

Conclusión corta: el sistema quedó **bien encaminado**, pero todavía **no conviene tomar el número de tokens usados por modelo como costo final exacto** hasta corregir la semántica de uso y el doble conteo en ciertos eventos.

---

## Qué se verificó

Se revisaron y/o ejecutaron los siguientes componentes:

- `benchmarks/run_context_benchmarks.py`
- `benchmarks/context_benchmark_results.json`
- `mmcp/server.py`
- `mmcp/token_counter.py`
- `mmcp/telemetry_service.py`
- `mmcp/session_store.py`
- `mmcp/cli.py`
- `tests/test_telemetry_service.py`
- `tests/test_rag_warmup_cli.py`

Además, se ejecutó:

- `pytest tests/test_telemetry_service.py tests/test_rag_warmup_cli.py`
- `python benchmarks/run_context_benchmarks.py`

---

## Resultado de tests

Resultado verificado:

- ✅ `34 passed`

Esto confirma que la detección de modelo, la extracción de métricas relevantes y el layout del panel de telemetría siguen consistentes con el comportamiento esperado hoy.

---

## Resultado del benchmark actual

Última ejecución verificada:

- **Tiempo total:** ~`35.2s`
- **Trim:** todos los casos quedaron dentro de presupuesto (`within_budget: true`)
- **Cache:** patrón correcto en `stable_prefix` → `false, true, true`
- **RAG:**
  - `12` archivos indexados
  - `492` chunks creados
  - `0` errores

### Lectura técnica

#### 1. Trim

La capa de trimming está cumpliendo el objetivo principal: **reducir contexto y respetar el budget configurado**.

Se observaron reducciones fuertes de tokens en los escenarios realistas y overflow. En particular, el caso overflow siguió entrando en budget sin romper la ejecución.

#### 2. Cache

El comportamiento del prefijo estable es correcto:

- primera llamada: miss
- segunda llamada: hit
- tercera llamada: hit

Eso indica que el mecanismo de reutilización del prefijo está operando como se espera para casos estables.

#### 3. RAG

La selección con límite de tokens está funcionando, y el benchmark también muestra una observación útil:

- en algunos escenarios, una estrategia tipo **skip candidate** puede meter más resultados en el mismo presupuesto que la estrategia actual.

Eso no rompe nada, pero sí sugiere una futura optimización de selección.

---

## Estado del Budget

## Veredicto

**Funciona, pero solo parcialmente como budget global.**

### Lo que sí hace bien

La estructura base de `TokenBudget` en `mmcp/token_counter.py` está correcta:

- define `max_tokens`
- aplica `safety_buffer`
- calcula `effective_limit`
- expone `consumed`, `remaining` y `usage_percent`

Además existe el recurso:

- `status://token_budget`

Y también existe:

- `reset_token_budget`

### Limitación actual

El problema es conceptual: **el budget global no se consume en todas las herramientas relevantes**.

Hoy, en `mmcp/server.py`, el consumo explícito ocurre solamente en:

- `count_tokens_tool`
- `count_messages_tokens_tool`

Eso significa que herramientas como:

- `optimize_messages`
- `search_context`
- `cache_context`
- `analyze_context_health_tool`
- `get_orchestration_advice`

**no impactan directamente el budget global**, aunque sí trabajan con contexto, conteo, caché o selección bajo presupuesto.

### Conclusión sobre Budget

El budget actual sirve como:

- **contador técnico local**
- **recurso de visibilidad**
- **base para evolución**

Pero **todavía no representa un budget integral del runtime completo**.

---

## Estado de la identificación de tokens por modelo

## Veredicto

**Sí existe y sí está funcionando.**

La resolución de modelo/proveedor en `mmcp/telemetry_service.py` está contemplando:

- hints explícitos por variables de entorno:
  - `OPENAI_MODEL`
  - `ANTHROPIC_MODEL`
  - `GEMINI_MODEL`
  - `GOOGLE_MODEL`
  - `OPENROUTER_MODEL`
  - `MODEL`, `LLM_MODEL`, `MCP_MODEL`, etc.
- fallback por orchestrator (`opencode`, `gentle-ai`)
- inferencia básica por prefijo del nombre del modelo

Luego eso se persiste en SQLite mediante `UsageEvent` y `SessionStore`.

### Qué sí queda cubierto

- provider/model detectado
- agrupación semanal por `model_name`
- visualización en CLI/TUI
- tests de detección y extracción de métricas pasando

### Qué NO significa todavía

Esto **no garantiza** que el total mostrado como “used” sea un reflejo exacto del costo real por modelo en todos los casos.

---

## Problema detectado: posible doble conteo

Este es el punto más importante a corregir.

En `mmcp/session_store.py`, la agregación semanal hace:

- `SUM(input_tokens + output_tokens)` como `total_used`

Pero en `mmcp/telemetry_service.py`, para eventos de `cache_context`, se asigna:

- `input_tokens = total_tokens`
- `output_tokens = total_tokens`

Entonces, al agregarse semanalmente:

- el valor de `used` puede quedar **duplicado** para ese tipo de evento.

### Impacto

Esto afecta directamente la interpretación de:

- budget por modelo
- uso semanal por modelo
- “tokens quemados”

### Conclusión sobre tokens quemados por modelo

La respuesta correcta hoy es:

> **Se identifican y se agrupan por modelo, pero el total todavía no debe considerarse costo exacto final.**

---

## Estado del dashboard TUI

La UI está bien resuelta para inspección rápida.

Se verificó que el contenido de telemetría muestra:

- **Savings**
- **Budget**
- **Model usage**

Y los tests de layout asociados pasan correctamente.

Además, el panel aclara dos cosas sanas:

- la ventana es de **7 días rolling**
- el budget aplica **por distinct model string**

Eso está bien desde el punto de vista de producto, pero depende de que la contabilidad base esté bien definida.

---

## Veredicto final (QA)

### ✅ OK

- Benchmark ejecutable y estable
- Trim respetando budget
- Cache con hits esperados
- RAG funcionando con selección limitada por tokens
- Detección de provider/model funcionando
- Persistencia y agrupación por modelo presentes
- Dashboard TUI útil para inspección
- Tests relevantes en verde

### ⚠️ WARNING

- El budget actual no cubre todas las herramientas del sistema
- El benchmark no valida todavía la telemetría por modelo ni el budget tracker end-to-end
- El total semanal por modelo mezcla métricas que no siempre representan costo homogéneo

### ❌ CRITICAL a corregir antes de confiar en el número final

- Posible doble conteo en `cache_context` por usar `input_tokens + output_tokens` mientras ambos valen `total_tokens`

---

## Recomendaciones inmediatas para la próxima sesión

1. **Definir semántica única de uso**
   - decidir qué significa exactamente `input_tokens`
   - decidir qué significa exactamente `output_tokens`
   - decidir qué significa `used` para dashboards y budget

2. **Corregir agregación semanal**
   - evitar doble conteo en eventos donde `output_tokens` no representa salida real del modelo

3. **Expandir budget global**
   - decidir si el tracker debe cubrir solo conteo local o todas las operaciones relevantes del runtime

4. **Agregar benchmark específico de telemetría**
   - validar end-to-end:
     - detección de modelo
     - persistencia
     - agregación semanal
     - budget por modelo

5. **Probar tras recargar MCP local**
   - reset de budget
   - ejecutar tools instrumentadas
   - inspeccionar `status://token_budget`
   - inspeccionar dashboard de telemetry

---

## Cierre

Estado honesto del sistema al cierre de hoy:

> **La base está bien y sirve para seguir iterando, pero todavía no hay garantía de exactitud final para “tokens quemados por modelo”.**

Lo importante es que el problema ya está localizado y no es difuso:

- la telemetría existe
- el dashboard existe
- el benchmark existe
- los tests pasan
- la precisión final depende de corregir la semántica y la agregación

Eso es una MUY buena señal para la próxima sesión.
