import psycopg2
import psycopg2.extras

PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# Порог для того, чтобы ребро "категория-похожа-на-категорию"
FAMILY_SIM_THRESHOLD = 0.6


def load_similarity_edges(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT category_id_a, category_id_b, similarity
            FROM category_similarity
            WHERE similarity >= %s
            """,
            (FAMILY_SIM_THRESHOLD,),
        )

        edges = []
        for row in cur:
            a = int(row["category_id_a"])
            b = int(row["category_id_b"])
            edges.append((a, b))
    return edges


def build_components(edges):
    """
    По списку ребер строим связные компоненты (семейства).
    """
    from collections import defaultdict, deque

    graph = defaultdict(set)

    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)

    visited = set()
    components = []

    for node in graph.keys():
        if node in visited:
            continue
        comp = []
        dq = deque([node])
        visited.add(node)
        while dq:
            v = dq.popleft()
            comp.append(v)
            for nei in graph[v]:
                if nei not in visited:
                    visited.add(nei)
                    dq.append(nei)
        components.append(sorted(comp))

    return components


def rebuild_families():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        edges = load_similarity_edges(conn)
        print(f"[families] edges: {len(edges)}")

        components = build_components(edges)
        print(f"[families] components: {len(components)}")

        with conn.cursor() as cur:
            # очищаем старые семьи
            cur.execute("TRUNCATE TABLE category_family_member;")
            cur.execute("TRUNCATE TABLE category_family RESTART IDENTITY;")

            for comp_idx, comp in enumerate(components, start=1):
                # для имени можно взять название первой категории
                cur.execute(
                    """
                    INSERT INTO category_family (name)
                    VALUES (%s)
                    RETURNING id;
                    """,
                    (f"Семейство #{comp_idx}",),
                )
                family_id = cur.fetchone()[0]

                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO category_family_member (family_id, category_id)
                    VALUES %s
                    """,
                    [(family_id, cat_id) for cat_id in comp],
                )

        conn.commit()
        print("[families] готово, транзакция зафиксирована.")
    except Exception as e:
        conn.rollback()
        print("[families] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_families()
