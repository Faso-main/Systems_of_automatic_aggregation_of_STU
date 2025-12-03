// server.js
import express from 'express';
import cors from 'cors';
import { Pool } from 'pg';

const app = express();
const PORT = 5000;

const RUNTIME_LLM_URL = process.env.RUNTIME_LLM_URL || 'http://127.0.0.1:8002';

app.use(
  cors({
    origin: ['https://faso312.ru', 'https://www.faso312.ru', 'http://127.0.0.1:5000'],
    credentials: false,
  })
);

app.use(express.json({ limit: '10mb' }));


const pool = new Pool({
  user: 'th3_app',
  host: 'localhost',
  database: 'th3_db',
  password: '1234',
  port: 5432,
});



function mapCategoryRow(row) {
  const createdAt = row.generated_at || row.created_at || null;

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

  const hasUntrainedItems = row.has_untrained_items === true;
  const untrainedItemsCount =
    row.untrained_items_count === null ||
    row.untrained_items_count === undefined
      ? 0
      : Number(row.untrained_items_count);

  return {
    id: Number(row.id),
    name: row.name,
    description: row.short_description || '',
    createdAt,
    status,
    rating,
    productIds: row.product_ids || [],
    features: row.category_features || [],
    hasNewItems,
    newItemsCount,
    hasUntrainedItems,
    untrainedItemsCount,
  };
}


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

      COALESCE(
        SUM(
          CASE
            WHEN p.id IS NOT NULL AND p.is_used_for_training = FALSE THEN 1
            ELSE 0
          END
        ),
        0
      )                                         AS untrained_items_count,
      COALESCE(
        BOOL_OR(p.id IS NOT NULL AND p.is_used_for_training = FALSE),
        FALSE
      )                                         AS has_untrained_items,

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



app.get('/api/health', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW()');
    res.json({ status: 'OK', db_time: result.rows[0].now });
  } catch (err) {
    console.error('Ошибка /api/health:', err);
    res.status(500).json({ status: 'ERROR', error: 'DB not available' });
  }
});


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



app.post('/api/categories/:id/regenerate', async (req, res) => {
  const client = await pool.connect();

  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      client.release();
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }

    const { product_ids } = req.body || {};


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

  
    let prodResult;
    let usedProductIds = [];

    if (Array.isArray(product_ids) && product_ids.length > 0) {
      const cleanIds = [
        ...new Set(
          product_ids
            .map((x) => Number(x))
            .filter((x) => Number.isInteger(x))
        ),
      ];

      if (cleanIds.length === 0) {
        client.release();
        return res.status(400).json({ error: 'Некорректные product_ids' });
      }

      prodResult = await client.query(
        `
        SELECT id, name, producer, country, raw_specs, is_used_for_training
        FROM product
        WHERE category_id = $1
          AND id = ANY($2::bigint[])
        ORDER BY id;
        `,
        [id, cleanIds]
      );
    } else {

      prodResult = await client.query(
        `
        SELECT id, name, producer, country, raw_specs, is_used_for_training
        FROM product
        WHERE category_id = $1
        ORDER BY id;
        `,
        [id]
      );
    }

    const products = prodResult.rows;
    if (products.length === 0) {
      client.release();
      return res.status(400).json({
        error: 'Нет товаров для перегенерации (проверьте выбор)',
      });
    }

    usedProductIds = products.map((p) => p.id);


    const items = products.map((p) => buildItemForRuntime(p, categoryName));


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
    const features = Array.isArray(runtimeData.features)
      ? runtimeData.features
      : [];



    await client.query('BEGIN');

    await client.query(
      `
      UPDATE product_category
      SET
        generated_at    = NOW(),
        has_new_items   = FALSE,
        new_items_count = 0
      WHERE id = $1;
      `,
      [id]
    );


    await client.query(
      `DELETE FROM category_feature WHERE category_id = $1;`,
      [id]
    );


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

    if (usedProductIds.length > 0) {
      await client.query(
        `
        UPDATE product
        SET
          is_used_for_training = TRUE,
          training_used_at     = COALESCE(training_used_at, NOW())
        WHERE id = ANY($1::bigint[]);
        `,
        [usedProductIds]
      );
    }

    await client.query('COMMIT');
    client.release();

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


app.get('/api/categories/:id/family', async (req, res) => {
  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }


    const familyRes = await pool.query(
      `
      SELECT
        cf.id   AS family_id,
        cf.name AS family_name
      FROM category_family_member cfm
      JOIN category_family cf ON cf.id = cfm.family_id
      WHERE cfm.category_id = $1
      LIMIT 1;
      `,
      [id]
    );

    if (familyRes.rows.length === 0) {

      return res.json({
        base: { id, name: null },
        family: null,
        members: [],
      });
    }

    const familyRow = familyRes.rows[0];
    const familyId = Number(familyRow.family_id);


    const membersRes = await pool.query(
      `
      SELECT
        m.category_id,
        pc.name,
        pc.short_description,
        cs.similarity,
        cs.key_similarity,
        cs.value_similarity
      FROM category_family_member m
      JOIN product_category pc
        ON pc.id = m.category_id
      LEFT JOIN category_similarity cs
        ON (
             (cs.category_id_a = $1 AND cs.category_id_b = m.category_id)
          OR (cs.category_id_b = $1 AND cs.category_id_a = m.category_id)
        )
      WHERE m.family_id = $2
      ORDER BY pc.id;
      `,
      [id, familyId]
    );

    const members = membersRes.rows.map((row) => {
      const catId = Number(row.category_id);
      const isBase = catId === id;

      const sim =
        isBase
          ? 1.0
          : row.similarity !== null && row.similarity !== undefined
          ? Number(row.similarity)
          : null;

      const keySim =
        row.key_similarity !== null && row.key_similarity !== undefined
          ? Number(row.key_similarity)
          : null;

      const valueSim =
        row.value_similarity !== null && row.value_similarity !== undefined
          ? Number(row.value_similarity)
          : null;

      return {
        categoryId: catId,
        name: row.name,
        description: row.short_description || '',
        similarity: sim,
        keySimilarity: keySim,
        valueSimilarity: valueSim,
        isBase,
      };
    });


    const baseMember = members.find((m) => m.isBase) || null;

    res.json({
      base: baseMember
        ? { id: baseMember.categoryId, name: baseMember.name }
        : { id, name: null },
      family: {
        id: familyId,
        name: familyRow.family_name,
      },
      members,
    });
  } catch (err) {
    console.error('Ошибка /api/categories/:id/family:', err);
    res
      .status(500)
      .json({ error: 'Не удалось загрузить семейство для категории' });
  }
});


app.get('/api/categories/:id/family', async (req, res) => {
  try {
    const id = Number(req.params.id);
    if (Number.isNaN(id)) {
      return res.status(400).json({ error: 'Некорректный ID категории' });
    }


    const familyRes = await pool.query(
      `
      SELECT
        cf.id   AS family_id,
        cf.name AS family_name
      FROM category_family_member cfm
      JOIN category_family cf ON cf.id = cfm.family_id
      WHERE cfm.category_id = $1
      LIMIT 1;
      `,
      [id]
    );


    if (familyRes.rows.length === 0) {
      return res.json({
        baseCategoryId: id,
        family: null,
        members: [],
      });
    }

    const familyRow = familyRes.rows[0];
    const familyId = Number(familyRow.family_id);


    const membersRes = await pool.query(
      `
      SELECT
        pc.id                  AS category_id,
        pc.name                AS name,
        pc.short_description   AS description,
        cs.similarity          AS similarity,
        cs.key_similarity      AS key_similarity,
        cs.value_similarity    AS value_similarity
      FROM category_family_member m
      JOIN product_category pc
        ON pc.id = m.category_id
      LEFT JOIN category_similarity cs
        ON (
             (cs.category_id_a = $1 AND cs.category_id_b = m.category_id)
          OR (cs.category_id_b = $1 AND cs.category_id_a = m.category_id)
        )
      WHERE m.family_id = $2
      ORDER BY pc.id;
      `,
      [id, familyId]
    );

    const members = membersRes.rows.map((row) => {
      const catId = Number(row.category_id);
      const isBase = catId === id;

      return {
        categoryId: catId,
        name: row.name,
        description: row.description || '',
        isBase,
        similarity: isBase
          ? 1.0
          : row.similarity != null
          ? Number(row.similarity)
          : null,
        keySimilarity:
          row.key_similarity != null ? Number(row.key_similarity) : null,
        valueSimilarity:
          row.value_similarity != null ? Number(row.value_similarity) : null,
      };
    });

    res.json({
      baseCategoryId: id,
      family: {
        id: familyId,
        name: familyRow.family_name,
      },
      members,
    });
  } catch (err) {
    console.error('Ошибка /api/categories/:id/family:', err);
    res
      .status(500)
      .json({ error: 'Не удалось загрузить семейство для категории' });
  }
});


app.get('/api/category-families', async (req, res) => {
  try {
    const result = await pool.query(
      `
      SELECT
        cf.id   AS family_id,
        cf.name AS family_name,
        COALESCE(
          JSON_AGG(
            JSON_BUILD_OBJECT(
              'categoryId', pc.id,
              'name',       pc.name,
              'description', pc.short_description
            )
            ORDER BY pc.id
          )
          FILTER (WHERE pc.id IS NOT NULL),
          '[]'::json
        ) AS members
      FROM category_family cf
      LEFT JOIN category_family_member cfm
        ON cfm.family_id = cf.id
      LEFT JOIN product_category pc
        ON pc.id = cfm.category_id
      GROUP BY cf.id, cf.name
      ORDER BY cf.id;
      `
    );

    const families = result.rows.map((row) => ({
      id: Number(row.family_id),
      name: row.family_name,
      members: row.members || [],
      size: Array.isArray(row.members) ? row.members.length : 0,
    }));

    res.json({ families });
  } catch (err) {
    console.error('Ошибка /api/category-families:', err);
    res
      .status(500)
      .json({ error: 'Не удалось загрузить семейства категорий' });
  }
});


app.listen(PORT, () => {
  console.log(`API сервер запущен на http://localhost:${PORT}`);
});
