import statistics
import tempfile
import time
from pathlib import Path

import pytest

from mmcp.rag_engine import RAGEngine
from mmcp.token_counter import count_messages_tokens, count_tokens
from mmcp.trim_history import trim_messages

# --- 1. VERIFICACIÓN DE EXACTITUD (TRUTHFULNESS) ---


def test_token_counter_accuracy():
    """Verifica que el contador de tokens sea exacto con casos conocidos."""
    assert count_tokens("") == 0
    assert count_tokens(" ") == 1

    text = "MMCP is awesome"
    tokens = count_tokens(text)
    assert tokens > 0

    # Verificación de mensajes (overhead de OpenAI: 4 por msg + 3 al final)
    messages = [{"role": "user", "content": "hello"}]
    # Lógica validada: 4 (msg) + 1 ("user") + 1 ("hello") + 3 (priming) = 9
    assert count_messages_tokens(messages) == 9


# --- 2. BENCHMARK DE RAG (COLD VS WARM + RECALL) ---


@pytest.mark.performance
@pytest.mark.slow
def test_rag_performance_and_recall():
    """
    Mide el ciclo de vida del RAG y la calidad de recuperación.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # COLD START
        start_init = time.perf_counter()
        engine = RAGEngine(db_path=tmp_dir, table_name="test_bench")
        end_init = time.perf_counter()
        cold_init_ms = (end_init - start_init) * 1000

        # INDEXING: Datos diversos para probar el "Recall"
        corpus = [
            ("arch.txt", "The system uses a hexagonal architecture with ports and adapters."),
            ("auth.txt", "Authentication is handled via JWT tokens in the Authorization header."),
            ("db.txt", "The database is PostgreSQL with a vector extension for semantic search."),
        ]

        for name, content in corpus:
            p = Path(tmp_dir) / name
            p.write_text(content)
            engine.index_file(str(p))

        # WARM SEARCH & RECALL
        # Probamos que un query sobre 'auth' traiga el archivo de auth primero
        start_search = time.perf_counter()
        results = engine.search("how does authentication work?", top_k=1)
        end_search = time.perf_counter()

        search_ms = (end_search - start_search) * 1000

        print("\n[RAG BENCHMARK]")
        print(f"Cold Init: {cold_init_ms:.2f}ms")
        print(f"Search Latency: {search_ms:.2f}ms")

        # Validación cualitativa (recall) estable
        assert results, "La búsqueda RAG no devolvió resultados."
        assert "JWT" in results[0].text, "El RAG falló en recuperar el contexto más relevante."
        assert results[0].source == "auth.txt"


# --- 3. ESTRÉS DE TRIM HISTORY (ESTADÍSTICA SIGNIFICATIVA) ---


@pytest.mark.performance
def test_trim_history_stress():
    """
    Corre el algoritmo de trimming 50 veces con un historial pesado.
    """
    heavy_history = [
        {"role": "system", "content": "System prompt " * 100},
    ]
    for i in range(99):
        role = "user" if i % 2 == 0 else "assistant"
        heavy_history.append({"role": role, "content": f"Message {i} " * 50})

    iterations = 50
    durations = []

    trimmed_counts = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        result = trim_messages(heavy_history, max_tokens=1000, strategy="smart")
        t1 = time.perf_counter()
        durations.append((t1 - t0) * 1000)
        trimmed_counts.append(result.trimmed_token_count)

    avg_trim = statistics.mean(durations)
    median_trim = statistics.median(durations)
    steady_state = durations[5:] if len(durations) > 5 else durations
    steady_state_sorted = sorted(steady_state)
    p95_index = max(0, int(len(steady_state_sorted) * 0.95) - 1)
    p95_trim = steady_state_sorted[p95_index]

    print(f"\n[TRIM STRESS TEST - {iterations} iterations]")
    print(f"Avg: {avg_trim:.4f}ms (Median: {median_trim:.4f}ms, P95 steady-state: {p95_trim:.4f}ms)")

    # Validación funcional dura: nunca debe exceder el budget.
    assert all(token_count <= 1000 for token_count in trimmed_counts)

    # Señal de performance robusta: evitar regresiones evidentes sin depender del hardware exacto.
    assert median_trim > 0
    assert p95_trim <= median_trim * 4, "La variabilidad del trimming aumentó demasiado."


# --- 4. DETERMINISMO ---


def test_rag_determinism():
    """Asegura que los resultados sean reproducibles."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = RAGEngine(db_path=tmp_dir)
        f = Path(tmp_dir) / "data.txt"
        f.write_text("Unique key: AFK-9922-X")
        engine.index_file(str(f))

        res1 = engine.search("what is the key?")
        res2 = engine.search("what is the key?")

        assert res1[0].text == res2[0].text
        assert res1[0].score == res2[0].score
