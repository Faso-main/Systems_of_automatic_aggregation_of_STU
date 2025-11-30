import psycopg2
import psycopg2.extras
from collections import defaultdict, deque

PG_DSN = "postgresql://th3_app:1234@localhost:5432/th3_db"

# Порог для объединения товаров в одну группу.
# product_similarity уже фильтруется по ~0.7;
# здесь можно сделать чуть жёстче, чтобы группы были компактнее.
GROUP_THRESHOLD = 0.8


def load_edges(conn):
    """
    Тянем рёбра из product_similarity по порогу GROUP_THRESHOLD.
    """
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
    nodes = set()
    for row in rows:
        a = int(row["product_id_a"])
        b = int(row["product_id_b"])
        sim = float(row["similarity"])
        edges.append((a, b, sim))
        nodes.add(a)
        nodes.add(b)

    print(f"[prod_groups] рёбер: {len(edges)} (threshold={GROUP_THRESHOLD}), узлов в графе: {len(nodes)}")
    return edges, nodes


def load_all_product_ids(conn):
    """
    Все товары из таблицы product.
    Нужны, чтобы добавить одиночные группы для тех, кто никому не похож.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM product")
        return [int(r[0]) for r in cur.fetchall()]


def build_components(edges):
    """
    Компоненты связности графа по рёбрам product_similarity.
    """
    graph = defaultdict(set)
    for a, b, _sim in edges:
        graph[a].add(b)
        graph[b].add(a)

    visited = set()
    components = []

    for start in graph.keys():
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

    return components, visited


def rebuild_product_groups():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False

    try:
        edges, nodes_in_edges = load_edges(conn)
        components, visited_nodes = build_components(edges)

        # Добавим одиночные товары, у которых вообще нет рёбер >= GROUP_THRESHOLD
        all_products = set(load_all_product_ids(conn))
        lonely = sorted(all_products - visited_nodes)

        for pid in lonely:
            components.append([pid])

        print(f"[prod_groups] всего компонент (групп): {len(components)}")

        with conn.cursor() as cur:
            # чистим старые группы
            cur.execute(
                """
                TRUNCATE TABLE product_group_member, product_group
                RESTART IDENTITY;
                """
            )

            total_groups = 0

            for comp in components:
                # имя группы по умолчанию — название первого товара
                first_pid = comp[0]
                cur.execute(
                    "SELECT name FROM product WHERE id = %s",
                    (first_pid,),
                )
                row = cur.fetchone()
                group_name = row[0] if row and row[0] else f"Группа товаров #{total_groups+1}"

                # создаём группу
                cur.execute(
                    """
                    INSERT INTO product_group (name)
                    VALUES (%s)
                    RETURNING id
                    """,
                    (group_name,),
                )
                group_id = cur.fetchone()[0]

                # добавляем участников
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
        print(f"[prod_groups] готово, пересчитано групп: {total_groups}")
    except Exception as e:
        conn.rollback()
        print("[prod_groups] ОШИБКА, откат:", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    rebuild_product_groups()
