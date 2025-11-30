// server.js
import express from 'express';
import cors from 'cors';
import { Pool } from 'pg';

const app = express();
const PORT = 5000;

const RUNTIME_LLM_URL = process.env.RUNTIME_LLM_URL || 'http://127.0.0.1:8002';

app.use(
  cors({
    origin: ['https://faso312.ru', 'http://127.0.0.1:5000'],
    credentials: false,
  })
);

app.use(express.json({ limit: '10mb' }));

// ===========================
// Настройка подключения к БД
// ===========================
const pool = new Pool({
  user: 'th3_app',
  host: 'localhost',
  database: 'th3_db',
  password: '1234', // поправь на свой если нужно
  port: 5432,
});

// ===========================
// Вспомогательные функции
// ===========================

/**
 * Преобразует строку категории из БД к формату, который удобен фронтенду.
 */
function mapCategoryRow(row) {
  const createdAt = row.generated_at || row.created_at || null;

  // нормализуем статус и рейтинг
  const status = row.admin_status || 'pending';
  const rating =
    row.admin_rating === null || row.admin_rating === undefined
      ? 0
      : Number(row.admin_rating);

  const hasNewItems = row.has_new_items === true;
  const newItemsCount =
    row.new_items_count === null || row.new_items_count === undefined
      ? 0
      : Number(row.new_items_count);

  return {
    id: Number(row.id),
    name: row.name,
    description: row.short_description || '',
    createdAt,
    status, // 'pending' | 'approved' | 'rejected'
    rating, // number
    productIds: row.product_ids || [],
    features: row.category_features || [], // [{ key, values: [...] }, ...]
    hasNewItems,
    newItemsCount,
  };
}

// оформляем СТЕ в формат, который ждёт runtime_llm_itr3
function buildItemForRuntime(product, categoryName) {
  const specsText =
    typeof product.raw_specs === 'string' ? product.raw_specs : '';
  const specsLines = specsText
    ? specsText
        .split(/[;\n]/)
        .map((s) => s.trim())
        .filter(Boolean)
    : [];

  const item = {
    ste_id: Number(product.id),
    'название_сте': product.name || '',
    'производитель': product.producer || '',
    'страна_происхождения': product.country || '',
    'название_категории': categoryName || '',
  };

  specsLines.forEach((line, idx) => {
    item[`spec${idx + 1}`] = line;
  });

  return item;
}

// Базовый SELECT для категорий
const CATEGORY_SELECT = `
  SELECT
      c.id                                      AS id,
      c.name                                    AS name,
      c.short_description                       AS short_description,
      c.generated_at                            AS generated_at,
      c.created_at                              AS created_at,
      c.admin_rating                            AS admin_rating,
      c.admin_status                            AS admin_status,
      c.has_new_items                           AS has_new_items,
      c.new_items_count                         AS new_items_count,

      ARRAY_AGG(DISTINCT p.id ORDER BY p.id)    AS product_ids,

      (
          SELECT JSON_AGG(
                     JSONB_BUILD_OBJECT(
                         'key', key,
                         'values', values
                     )
                     ORDER BY key
                 )
          FROM (
              SELECT
                  cf.key,
                  ARRAY_AGG(DISTINCT cf.value ORDER BY cf.value) AS values
              FROM category_feature cf
              WHERE cf.category_id = c.id
              GROUP BY cf.key
          ) t
      ) AS category_features

  FROM product_category c
  LEFT JOIN product p ON p.category_id = c.id
`;

// ===========================
// РОУТЫ
// ===========================

// Health-check
app.get('/api/health', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW()');
    res.json({ status: 'OK', db_time: result.rows[0].now });
  } catch (err) {
    console.error('Ошибка /api/health:', err);
    res.status(500).json({ status: 'ERROR', error: 'DB not available' });
  }
});

// Все категории
app.get('/api/categories', async (req, res) => {
  try {
    const query = `
      ${CATEGORY_SELECT}
      GROUP BY
        c.id,
        c.name,
        c.short_description,
        c.generated_at,
        c.created_at,
        c.admin_rating,
        c.admin_status,
        c.has_new_items,
        c.new_items_count
      ORDER BY c.id;
    `;

    const result = await pool.query(query);
    const categories = result.rows.map(mapCategoryRow);

    res.json({ categories });
  } catch (err) {
    console.error('Ошибка /api/categories:', err);
    res.status(500).json({ error: 'Не удалось загрузить категории' });
  }
});

// Одна категория по id
app.get('/api/categories/:id', async (req, res) => {
  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }

    const query = `
      ${CATEGORY_SELECT}
      WHERE c.id = $1
      GROUP BY
        c.id,
        c.name,
        c.short_description,
        c.generated_at,
        c.created_at,
        c.admin_rating,
        c.admin_status,
        c.has_new_items,
        c.new_items_count
      LIMIT 1;
    `;

    const result = await pool.query(query, [id]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Категория не найдена' });
    }

    const category = mapCategoryRow(result.rows[0]);
    res.json({ category });
  } catch (err) {
    console.error('Ошибка /api/categories/:id:', err);
    res.status(500).json({ error: 'Не удалось загрузить категорию' });
  }
});

// Рейтинг категории (1–5)
app.post('/api/categories/:id/rating', async (req, res) => {
  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      return res.status(400).json({ error: 'Некорректный id категории' });
    }

    const { rating } = req.body || {};
    const ratingInt = Number(rating);

    if (!Number.isInteger(ratingInt) || ratingInt < 1 || ratingInt > 5) {
      return res
        .status(400)
        .json({ error: 'rating должен быть целым числом от 1 до 5' });
    }

    const upd = await pool.query(
      `
      UPDATE product_category
      SET admin_rating = $1
      WHERE id = $2
      RETURNING id, name, admin_rating;
      `,
      [ratingInt, id]
    );

    if (upd.rowCount === 0) {
      return res.status(404).json({ error: 'Категория не найдена' });
    }

    return res.json({ category: upd.rows[0] });
  } catch (err) {
    console.error('Ошибка POST /api/categories/:id/rating:', err);
    return res.status(500).json({ error: 'Не удалось обновить рейтинг' });
  }
});

// Обновление категории (описание / статус / рейтинг)
app.patch('/api/categories/:id', async (req, res) => {
  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }

    const { rating, status, description } = req.body || {};

    const fields = [];
    const values = [];
    let idx = 1;

    if (rating !== undefined) {
      fields.push(`admin_rating = $${idx++}`);
      values.push(Number(rating));
    }
    if (status !== undefined) {
      fields.push(`admin_status = $${idx++}`);
      values.push(status);
    }
    if (description !== undefined) {
      fields.push(`short_description = $${idx++}`);
      values.push(description);
    }

    if (fields.length === 0) {
      return res.status(400).json({ error: 'Нечего обновлять' });
    }

    values.push(id);

    const updateQuery = `
      UPDATE product_category
      SET ${fields.join(', ')}
      WHERE id = $${idx}
      RETURNING id;
    `;
    const upd = await pool.query(updateQuery, values);

    if (upd.rowCount === 0) {
      return res.status(404).json({ error: 'Категория не найдена' });
    }

    res.json({ ok: true });
  } catch (err) {
    console.error('Ошибка PATCH /api/categories/:id:', err);
    res.status(500).json({ error: 'Не удалось обновить категорию' });
  }
});

// Перегенерация категории через Python LLM-рантайм
app.post('/api/categories/:id/regenerate', async (req, res) => {
  const client = await pool.connect();

  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      client.release();
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }

    // 1. Получаем категорию (название) + список id СТЕ
    const catQuery = `
      ${CATEGORY_SELECT}
      WHERE c.id = $1
      GROUP BY
        c.id,
        c.name,
        c.short_description,
        c.generated_at,
        c.created_at,
        c.admin_rating,
        c.admin_status,
        c.has_new_items,
        c.new_items_count
      LIMIT 1;
    `;

    const catResult = await client.query(catQuery, [id]);

    if (catResult.rows.length === 0) {
      client.release();
      return res.status(404).json({ error: 'Категория не найдена' });
    }

    const catRow = mapCategoryRow(catResult.rows[0]);
    const categoryName = catRow.name;
    const productIds = catRow.productIds || [];

    // 2. Загружаем все товары по этой категории
    const prodResult = await client.query(
      `
      SELECT id, name, producer, country, raw_specs
      FROM product
      WHERE category_id = $1
      ORDER BY id;
      `,
      [id]
    );

    const products = prodResult.rows;
    if (products.length === 0) {
      client.release();
      return res.status(400).json({
        error: 'У категории нет СТЕ — нечего перегенерировать',
      });
    }

    // 3. Оформляем СТЕ так, как ждёт runtime_llm_itr3
    const items = products.map((p) => buildItemForRuntime(p, categoryName));

    // 4. Отправляем в Python-сервис
    const runtimeResp = await fetch(
      `${RUNTIME_LLM_URL}/regenerate-category`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category_id: id,
          category_name: categoryName,
          items,
        }),
      }
    );

    if (!runtimeResp.ok) {
      console.error(
        'runtime_llm_itr3 error:',
        runtimeResp.status,
        await runtimeResp.text()
      );
      client.release();
      return res.status(502).json({
        error: 'LLM-сервис недоступен или вернул ошибку',
      });
    }

    const runtimeData = await runtimeResp.json();
    const shortDescription = runtimeData.short_description || '';
    const features = Array.isArray(runtimeData.features)
      ? runtimeData.features
      : [];

    // 5. Обновляем БД в транзакции:
    //    - обновляем описание и служебные флаги категории,
    //    - пересоздаём записи в category_feature.
    await client.query('BEGIN');

    await client.query(
      `
      UPDATE product_category
      SET
        short_description = $1,
        generated_at      = NOW(),
        has_new_items     = FALSE,
        new_items_count   = 0
      WHERE id = $2;
      `,
      [shortDescription, id]
    );

    // удаляем старые характеристики
    await client.query(
      `DELETE FROM category_feature WHERE category_id = $1;`,
      [id]
    );

    // вставляем новые
    for (const f of features) {
      const key = f.key;
      const values = Array.isArray(f.values) ? f.values : [];
      if (!key || values.length === 0) continue;

      for (const value of values) {
        if (!value) continue;
        await client.query(
          `
          INSERT INTO category_feature (category_id, key, value)
          VALUES ($1, $2, $3);
          `,
          [id, key, value]
        );
      }
    }

    await client.query('COMMIT');
    client.release();

    // Можно вернуть просто ok, фронт при желании может дернуть GET /api/categories/:id
    res.json({ ok: true });
  } catch (err) {
    console.error('Ошибка POST /api/categories/:id/regenerate:', err);
    try {
      await client.query('ROLLBACK');
    } catch (e) {
      console.error('Ошибка rollback:', e);
    }
    client.release();
    res.status(500).json({ error: 'Не удалось перегенерировать категорию' });
  }
});

// ===============================
// Получить товары по списку id СТЕ
// ===============================
app.post('/api/products/by-ids', async (req, res) => {
  try {
    const { ids } = req.body || {};

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ error: 'Не переданы id товаров' });
    }

    const cleanIds = [...new Set(
      ids
        .map((x) => Number(x))
        .filter((x) => Number.isInteger(x))
    )];

    if (cleanIds.length === 0) {
      return res.status(400).json({ error: 'Некорректные id товаров' });
    }

    const result = await pool.query(
      `
      SELECT *
      FROM product
      WHERE id = ANY($1::bigint[])
      ORDER BY id;
      `,
      [cleanIds]
    );

    res.json({ products: result.rows });
  } catch (err) {
    console.error('Ошибка POST /api/products/by-ids:', err);
    res.status(500).json({ error: 'Не удалось загрузить товары' });
  }
});

app.get('/api/search/categories', async (req, res) => {
  try {
    const q = (req.query.q || '').toString();
    if (!q.trim()) {
      return res.json([]);
    }

    const params = new URLSearchParams({
      q,
      top_k: '10',
      min_score: '40',
    });

    const resp = await fetch(
      `http://127.0.0.1:8001/search/categories?${params.toString()}`
    );

    if (!resp.ok) {
      console.error('search service error', resp.status);
      return res.status(500).json({ error: 'search service unavailable' });
    }

    const data = await resp.json();
    res.json(data);
  } catch (err) {
    console.error('Ошибка /api/search/categories:', err);
    res.status(500).json({ error: 'internal search error' });
  }
});

app.listen(PORT, () => {
  console.log(`API сервер запущен на http://localhost:${PORT}`);
});
