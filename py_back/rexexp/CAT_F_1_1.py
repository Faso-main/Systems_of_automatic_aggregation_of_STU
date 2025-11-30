import psycopg2
import psycopg2.extras

PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# Порог, по которому ребро попадает в семейство.
# Можно крутить, чтобы получить примерно нужное количество групп.
EDGE_THRESHOLD = 0.7  # начинаем с 0.7, дальше можно подстроить


def load_edges(conn):
    """
    Тянем ребра из category_similarity, только достаточно "сильные".
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT category_id_a, category_id_b, similarity
            FROM category_similarity
            WHERE similarity >= %s
            """,
            (EDGE_THRESHOLD,),
        )
        rows = cur.fetchall()

    edges = []
    for row in rows:
        a = int(row["category_id_a"])
        b = int(row["category_id_b"])
        sim = float(row["similarity"])
        edges.append((a, b, sim))

    print(f"[families] загружено рёбер: {len(edges)} (threshold={EDGE_THRESHOLD})")
    return edges


def build_components(edges):
    """
    По списку рёбер строим связные компоненты.
    """
    from collections import defaultdict, deque

    graph = defaultdict(set)
    nodes = set()

    for a, b, _ in edges:
        graph[a].add(b)
        graph[b].add(a)
        nodes.add(a)
        nodes.add(b)

    components = []
    visited = set()

    for start in nodes:
        if start in visited:
            continue
        comp = []
        dq = deque([start])
        visited.add(start)
        while dq:
            v = dq.popleft()
            comp.append(v)
            for nei in graph[v]:
                if nei not in visited:
                    visited.add(nei)
                    dq.append(nei)
        components.append(sorted(comp))

    # важно: категории, у которых НЕТ ни одного ребра,
    # мы тоже хотим видеть как "отдельные одиночные семьи".
    # Поэтому добавим одиночки, которых нет в nodes.
    return components, nodes


def load_all_category_ids(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM product_category")
        return [int(r[0]) for r in cur.fetchall()]


def rebuild_families():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        edges = load_edges(conn)
        components, nodes_with_edges = build_components(edges)

        all_ids = set(load_all_category_ids(conn))
        lonely_categories = sorted(all_ids - nodes_with_edges)

        # добавляем одиночные категории как отдельные компоненты
        for cat_id in lonely_categories:
            components.append([cat_id])

        print(f"[families] всего компонент (семейств): {len(components)}")

        with conn.cursor() as cur:
            # чистим старое
            cur.execute("TRUNCATE TABLE category_family_member;")
            cur.execute("TRUNCATE TABLE category_family RESTART IDENTITY;")

            # для имени семейства возьмём имя первой категории внутри него
            for comp_idx, comp in enumerate(components, start=1):
                # получаем имя первой категории
                first_cat_id = comp[0]
                cur.execute(
                    "SELECT name FROM product_category WHERE id = %s",
                    (first_cat_id,),
                )
                row = cur.fetchone()
                base_name = row[0] if row and row[0] else f"Семейство #{comp_idx}"

                # создаём семейство
                cur.execute(
                    """
                    INSERT INTO category_family (name)
                    VALUES (%s)
                    RETURNING id
                    """,
                    (base_name,),
                )
                family_id = cur.fetchone()[0]

                # заполняем участников
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO category_family_member (family_id, category_id)
                    VALUES %s
                    """,
                    [(family_id, cid) for cid in comp],
                )

        conn.commit()
        print("[families] готово, семейства пересчитаны.")
    except Exception as e:
        conn.rollback()
        print("[families] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_families()
