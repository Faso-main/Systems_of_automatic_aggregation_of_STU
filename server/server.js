// server.js
import express from 'express';
import cors from 'cors';
import { Pool } from 'pg';

const app = express();
const PORT = 5000;

app.use(
  cors({
    origin: ['https://faso312.ru','http://127.0.0.1:5000',],
    credentials: false,
  })
);

app.use(express.json({ limit: '10mb' }));

// ====== Подключение к th3_db ======
const pool = new Pool({
  user: 'th3_app',
  host: 'localhost',
  database: 'th3_db',
  password: '1234',      // подставь реально нужный
  port: 5432,
});

// ====== Вспомогательные функции ======

/**
 * Приведение строки из БД к формату, удобному для фронта.
 */
function mapCategoryRow(row) {
  // generated_at и created_at приходят как Date в node-pg → JSON сделает ISO-строку
  const createdAt = row.generated_at || row.created_at || null;

  // нормализуем статус и рейтинг
  const status = row.admin_status || 'pending';
  const rating =
    row.admin_rating === null || row.admin_rating === undefined
      ? 0
      : Number(row.admin_rating);

  return {
    id: Number(row.id),
    name: row.name,
    description: row.short_description || '',
    createdAt,
    status, // 'pending' | 'approved' | 'rejected'
    rating, // number
    productIds: row.product_ids || [],
    features: row.category_features || [], // [{ key, values: [...] }, ...]
  };
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

// ====== Роуты ======

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
      GROUP BY c.id, c.name, c.short_description, c.generated_at, c.created_at, c.admin_rating, c.admin_status
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
      GROUP BY c.id, c.name, c.short_description, c.generated_at, c.created_at, c.admin_rating, c.admin_status
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

// Обновление категории (оценка / статус)
app.patch('/api/categories/:id', async (req, res) => {
  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }

    const { rating, status } = req.body;

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
    await pool.query(updateQuery, values);

    // Можно вернуть обновлённую категорию, но для простоты вернём ok
    res.json({ ok: true });
  } catch (err) {
    console.error('Ошибка PATCH /api/categories/:id:', err);
    res.status(500).json({ error: 'Не удалось обновить категорию' });
  }
});

// Заглушка "перегенерация"
app.post('/api/categories/:id/regenerate', async (req, res) => {
  const id = req.params.id;
  console.log(`Запрос на перегенерацию категории ${id}`);
  // Тут потом можно подвесить вызов пайплайна / LLM
  res.json({ ok: true, message: `Перегенерация категории ${id} ещё не реализована` });
});

app.listen(PORT, () => {
  console.log(`API сервер запущен на http://localhost:${PORT}`);
});
