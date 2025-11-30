import psycopg2
import psycopg2.extras

PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

GROUP_THRESHOLD = 0.75  # порог для групп СТЕ


def load_edges(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """
            SELECT product_id_a, product_id_b, similarity
            FROM product_similarity
            WHERE similarity >= %s
            """,
            (GROUP_THRESHOLD,),
        )
        rows = cur.fetchall()

    edges = []
    for row in rows:
        a = int(row["product_id_a"])
        b = int(row["product_id_b"])
        sim = float(row["similarity"])
        edges.append((a, b, sim))

    print(f"[prod_groups] рёбер: {len(edges)} (threshold={GROUP_THRESHOLD})")
    return edges


def build_components(edges):
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

    return components, nodes


def load_all_product_ids(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM product")
        return [int(r[0]) for r in cur.fetchall()]


def rebuild_product_groups():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        edges = load_edges(conn)
        comps, nodes_with_edges = build_components(edges)

        all_ids = set(load_all_product_ids(conn))
        lonely = sorted(all_ids - nodes_with_edges)

        for pid in lonely:
            comps.append([pid])

        print(f"[prod_groups] всего групп (компонент): {len(comps)}")

        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE TABLE product_group_member, product_group
                RESTART IDENTITY;
                """
            )

            total_groups = 0

            for comp in comps:
                first_pid = comp[0]

                cur.execute(
                    "SELECT name FROM product WHERE id = %s",
                    (first_pid,),
                )
                row = cur.fetchone()
                group_name = (
                    row[0] if row and row[0] else f"Группа товаров #{total_groups+1}"
                )

                cur.execute(
                    """
                    INSERT INTO product_group (name)
                    VALUES (%s)
                    RETURNING id
                    """,
                    (group_name,),
                )
                group_id = cur.fetchone()[0]

                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO product_group_member (group_id, product_id)
                    VALUES %s
                    """,
                    [(group_id, pid) for pid in comp],
                )

                total_groups += 1

        conn.commit()
        print(f"[prod_groups] готово, всего групп: {total_groups}")
    except Exception as e:
        conn.rollback()
        print("[prod_groups] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_product_groups()
