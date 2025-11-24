import express from 'express';
import cors from 'cors';
import bcrypt from 'bcryptjs';
import pkg from 'pg';

const { Pool } = pkg;
const app = express();
const PORT = 5000;

const corsOptions = {
  origin: ['http://localhost:3000', 'http://127.0.0.1:3000'],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: [
    'Content-Type', 
    'Authorization', 
    'session-id',
    'Referer',
    'sec-ch-ua',
    'sec-ch-ua-mobile', 
    'sec-ch-ua-platform',
    'User-Agent'
  ],
  exposedHeaders: ['session-id']
};

// Middleware
app.use(cors(corsOptions));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Обработка OPTIONS запросов для CORS preflight
app.options('/api/*', cors(corsOptions));

// Логирование входящих запросов
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
  console.log('Headers:', {
    'content-type': req.headers['content-type'],
    'user-agent': req.headers['user-agent'],
    'session-id': req.headers['session-id'],
    'origin': req.headers['origin']
  });
  next();
});

// Префикс API
app.use('/api', (req, res, next) => {
  console.log('API request:', req.path);
  next();
});

// PostgreSQL connection
const pool = new Pool({
  user: 'store_app1',
  host: 'localhost',
  database: 'online_store1',
  password: '1234',
  port: 5432,
});

// Простое хранилище сессий
const sessions = new Map();
const generateSessionId = () => Math.random().toString(36).substring(2) + Date.now().toString(36);

// Auth middleware
const checkSession = (req, res, next) => {
  const sessionId = req.headers['session-id'];
  console.log('Session check:', { sessionId, hasSession: sessions.has(sessionId) });
  
  if (!sessionId || !sessions.has(sessionId)) {
    return res.status(401).json({ error: 'Неавторизован' });
  }
  req.user = sessions.get(sessionId);
  next();
};

// Получить профиль пользователя
app.get('/api/user/profile', checkSession, async (req, res) => {
  try {
    const result = await pool.query(
      'SELECT id, name, email, INN, company_name, phone_number, location, role, created_at FROM store.users WHERE id = $1',
      [req.user.id]
    );
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Пользователь не найден' });
    }
    
    res.json({ user: result.rows[0] });
  } catch (error) {
    console.error('Get profile error:', error);
    res.status(500).json({ error: 'Ошибка при получении профиля' });
  }
});

// Обновить профиль пользователя
app.put('/api/user/profile', checkSession, async (req, res) => {
  try {
    const { name, email, company_name, phone_number, location } = req.body;
    
    const result = await pool.query(
      `UPDATE store.users 
       SET name = $1, email = $2, company_name = $3, phone_number = $4, location = $5, updated_at = NOW()
       WHERE id = $6
       RETURNING id, name, email, INN, company_name, phone_number, location, role, created_at`,
      [name, email, company_name, phone_number, location, req.user.id]
    );
    
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Пользователь не найден' });
    }
    
    // Обновляем данные в сессии
    const sessionId = req.headers['session-id'];
    if (sessions.has(sessionId)) {
      sessions.set(sessionId, { ...sessions.get(sessionId), ...result.rows[0] });
    }
    
    res.json({ user: result.rows[0], message: 'Профиль успешно обновлен' });
  } catch (error) {
    console.error('Update profile error:', error);
    
    if (error.code === '23505') { // unique violation
      return res.status(400).json({ error: 'Email уже используется' });
    }
    
    res.status(500).json({ error: 'Ошибка при обновлении профиля' });
  }
});

// Получить закупки пользователя
app.get('/api/user/my-procurements', checkSession, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT p.id, p.session_number, p.title, p.status, p.current_price, 
              p.customer_name, p.customer_inn, p.start_date, p.end_date,
              p.created_at, p.updated_at,
              COUNT(pp.id) as participants_count
       FROM store.procurements p
       LEFT JOIN store.procurement_participants pp ON p.id = pp.procurement_id
       WHERE p.created_by = $1
       GROUP BY p.id
       ORDER BY p.created_at DESC`,
      [req.user.userId]
    );
    
    console.log('My procurements for user:', req.user.userId, 'count:', result.rows.length);
    
    res.json({ procurements: result.rows });
  } catch (error) {
    console.error('Get my procurements error:', error);
    res.status(500).json({ error: 'Ошибка при получении закупок' });
  }
});

// Получить участия пользователя в закупках
app.get('/api/user/my-participations', checkSession, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT pp.id, pp.proposed_price, pp.status, pp.proposal_text, pp.created_at,
              p.title as procurement_title, p.session_number, p.customer_name, p.customer_inn
       FROM store.procurement_participants pp
       JOIN store.procurements p ON pp.procurement_id = p.id
       WHERE pp.user_id = $1
       ORDER BY pp.created_at DESC`,
      [req.user.id]
    );
    
    res.json({ participations: result.rows });
  } catch (error) {
    console.error('Get my participations error:', error);
    res.status(500).json({ error: 'Ошибка при получении участий' });
  }
});

// Health check
app.get('/api/health', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW() as time');
    res.json({ 
      status: 'OK', 
      database: 'online_store1',
      time: result.rows[0].time,
      sessions: sessions.size
    });
  } catch (error) {
    console.error('Health check error:', error);
    res.status(500).json({ error: 'Database connection error' });
  }
});

// Регистрация
app.post('/api/auth/register', async (req, res) => {
  try {
    console.log('Register request body:', req.body);
    
    const { name, email, password, INN, company_name, location, phone_number } = req.body;

    if (!name || !email || !password || !INN) {
      return res.status(400).json({ error: 'Все обязательные поля должны быть заполнены' });
    }

    // Проверка существующего пользователя
    const userExists = await pool.query('SELECT id FROM store.users WHERE email = $1', [email]);
    if (userExists.rows.length > 0) {
      return res.status(400).json({ error: 'Пользователь с таким email уже существует' });
    }

    // Хеширование пароля
    const passwordHash = await bcrypt.hash(password, 10);

    // Создание пользователя
    const result = await pool.query(
      `INSERT INTO store.users (name, email, password_hash, INN, company_name, location, phone_number) 
       VALUES ($1, $2, $3, $4, $5, $6, $7) 
       RETURNING id, name, email, INN, company_name, location, phone_number, role`,
      [name, email, passwordHash, INN, company_name, location, phone_number]
    );

    const user = result.rows[0];
    const sessionId = generateSessionId();
    sessions.set(sessionId, { userId: user.id, email: user.email, role: user.role });

    console.log('User registered:', { userId: user.id, email: user.email });

    res.json({
      message: 'Пользователь успешно зарегистрирован',
      user: user,
      sessionId
    });

  } catch (error) {
    console.error('Registration error:', error);
    res.status(500).json({ error: 'Ошибка при регистрации' });
  }
});

// Авторизация
app.post('/api/auth/login', async (req, res) => {
  try {
    console.log('Login request body:', req.body);

    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ error: 'Email и пароль обязательны' });
    }

    // Поиск пользователя
    const result = await pool.query(
      'SELECT id, name, email, password_hash, role, is_active FROM store.users WHERE email = $1',
      [email]
    );

    if (result.rows.length === 0) {
      return res.status(400).json({ error: 'Пользователь не найден' });
    }

    const user = result.rows[0];

    // Проверка пароля
    const isPasswordValid = await bcrypt.compare(password, user.password_hash);
    if (!isPasswordValid) {
      return res.status(400).json({ error: 'Неверный пароль' });
    }

    // Создание сессии
    const sessionId = generateSessionId();
    sessions.set(sessionId, { userId: user.id, email: user.email, role: user.role });

    console.log('User logged in:', { userId: user.id, email: user.email });

    res.json({
      message: 'Успешный вход',
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        role: user.role
      },
      sessionId
    });

  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Ошибка при авторизации' });
  }
});

// Выход
app.post('/api/auth/logout', checkSession, (req, res) => {
  const sessionId = req.headers['session-id'];
  sessions.delete(sessionId);
  console.log('User logged out:', { sessionId });
  res.json({ message: 'Успешный выход' });
});

// Получение категорий
app.get('/api/categories', async (req, res) => {
  try {
    const result = await pool.query(`
      SELECT id, name, parent_id, level, description
      FROM store.categories 
      WHERE is_active = true
      ORDER BY level, parent_id NULLS FIRST, sort_order
    `);
    
    res.json({ categories: result.rows });
  } catch (error) {
    console.error('Categories error:', error);
    res.status(500).json({ error: 'Ошибка при получении категорий' });
  }
});

// Получение товаров
app.get('/api/products', async (req, res) => {
  try {
    const { category, minPrice, maxPrice, search, limit = 50 } = req.query;
    
    console.log('Products request query:', { category, minPrice, maxPrice, search, limit });
    
    let query = `
      SELECT 
        p.*, 
        c.name as category_name,
        c2.name as parent_category_name
      FROM store.products p 
      LEFT JOIN store.categories c ON p.category_id = c.id
      LEFT JOIN store.categories c2 ON c.parent_id = c2.id
      WHERE p.is_active = true
    `;
    const params = [];
    let paramCount = 0;

    if (category) {
      paramCount++;
      query += ` AND (c.name ILIKE $${paramCount} OR c2.name ILIKE $${paramCount})`;
      params.push(`%${category}%`);
    }

    if (minPrice) {
      paramCount++;
      query += ` AND p.price_per_item >= $${paramCount}`;
      params.push(parseFloat(minPrice));
    }

    if (maxPrice) {
      paramCount++;
      query += ` AND p.price_per_item <= $${paramCount}`;
      params.push(parseFloat(maxPrice));
    }

    if (search) {
      paramCount++;
      query += ` AND (p.name ILIKE $${paramCount} OR p.description ILIKE $${paramCount} OR p.company ILIKE $${paramCount})`;
      params.push(`%${search}%`);
    }

    query += ' ORDER BY p.created_at DESC LIMIT $' + (paramCount + 1);
    params.push(parseInt(limit));

    const result = await pool.query(query, params);
    
    console.log(`Found ${result.rows.length} products`);
    
    res.json({
      products: result.rows,
      total: result.rows.length
    });

  } catch (error) {
    console.error('Products error:', error);
    res.status(500).json({ error: 'Ошибка при получении товаров' });
  }
});

// Получение закупок
app.get('/api/procurements', async (req, res) => {
  try {
    const { status, limit = 20 } = req.query;
    
    console.log('Procurements request query:', { status, limit });
    
    let query = `
      SELECT 
        p.*,
        u.name as created_by_name,
        u.company_name as created_by_company
      FROM store.procurements p
      LEFT JOIN store.users u ON p.created_by = u.id
      WHERE p.is_active = true
    `;
    const params = [];
    let paramCount = 0;

    if (status) {
      paramCount++;
      query += ` AND p.status = $${paramCount}`;
      params.push(status);
    }

    query += ' ORDER BY p.start_date DESC LIMIT $' + (paramCount + 1);
    params.push(parseInt(limit));

    const result = await pool.query(query, params);
    
    // Получаем товары для каждой закупки
    const procurementsWithProducts = await Promise.all(
      result.rows.map(async (procurement) => {
        const productsResult = await pool.query(`
          SELECT 
            pp.*,
            p.name as product_name,
            p.price_per_item as market_price,
            p.description as product_description,
            c.name as category_name
          FROM store.procurement_products pp
          JOIN store.products p ON pp.product_id = p.id
          JOIN store.categories c ON p.category_id = c.id
          WHERE pp.procurement_id = $1
        `, [procurement.id]);

        const participantsResult = await pool.query(`
          SELECT COUNT(*) as participants_count 
          FROM store.procurement_participants 
          WHERE procurement_id = $1
        `, [procurement.id]);

        return {
          ...procurement,
          products: productsResult.rows,
          participants_count: parseInt(participantsResult.rows[0].participants_count)
        };
      })
    );

    console.log(`Found ${procurementsWithProducts.length} procurements`);
    
    res.json({
      procurements: procurementsWithProducts,
      total: procurementsWithProducts.length
    });

  } catch (error) {
    console.error('Procurements error:', error);
    res.status(500).json({ error: 'Ошибка при получении закупок' });
  }
});

// Участие в закупке
app.post('/api/procurements', checkSession, async (req, res) => {
  try {
    const {
      title,
      description,
      session_number,
      customer_name,
      customer_inn,
      current_price,
      start_date,
      end_date,
      law_type = '44-ФЗ',
      contract_terms,
      contract_security,
      products = []
    } = req.body;

    console.log('Create procurement request:', req.body);

    // Валидация обязательных полей
    if (!title || !session_number || !current_price || !start_date || !end_date) {
      return res.status(400).json({ error: 'Заполните все обязательные поля: название, номер сессии, цена, даты начала и окончания' });
    }

    // Создаем закупку
    const procurementResult = await pool.query(
      `INSERT INTO store.procurements 
       (title, description, session_number, customer_name, customer_inn, 
        current_price, start_date, end_date, law_type, contract_terms, 
        contract_security, created_by, status)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'active')
       RETURNING *`,
      [
        title,
        description,
        session_number,
        customer_name,
        customer_inn,
        parseFloat(current_price),
        new Date(start_date),
        new Date(end_date),
        law_type,
        contract_terms,
        contract_security,
        req.user.userId
      ]
    );

    const procurement = procurementResult.rows[0];
    console.log('Procurement created:', procurement);

    // Добавляем товары в закупку
    if (products && products.length > 0) {
      for (const product of products) {
        if (product.product_id && product.required_quantity > 0) {
          await pool.query(
            `INSERT INTO store.procurement_products 
             (procurement_id, product_id, required_quantity, max_price)
             VALUES ($1, $2, $3, $4)`,
            [
              procurement.id,
              product.product_id,
              product.required_quantity,
              product.max_price ? parseFloat(product.max_price) : null
            ]
          );
        }
      }
    }

    // Получаем полные данные закупки для ответа
    const fullProcurementResult = await pool.query(
      `SELECT p.*, u.name as created_by_name, u.company_name as created_by_company
       FROM store.procurements p
       LEFT JOIN store.users u ON p.created_by = u.id
       WHERE p.id = $1`,
      [procurement.id]
    );

    const productsResult = await pool.query(
      `SELECT pp.*, p.name as product_name
       FROM store.procurement_products pp
       JOIN store.products p ON pp.product_id = p.id
       WHERE pp.procurement_id = $1`,
      [procurement.id]
    );

    const participantsResult = await pool.query(
      `SELECT COUNT(*) as participants_count 
       FROM store.procurement_participants 
       WHERE procurement_id = $1`,
      [procurement.id]
    );

    const procurementWithProducts = {
      ...fullProcurementResult.rows[0],
      products: productsResult.rows,
      participants_count: parseInt(participantsResult.rows[0].participants_count)
    };

    console.log('Final procurement data:', procurementWithProducts);

    res.json({ 
      message: 'Закупка успешно создана',
      procurement: procurementWithProducts 
    });

  } catch (error) {
    console.error('Create procurement error:', error);
    res.status(500).json({ error: 'Ошибка при создании закупки: ' + error.message });
  }
});

// Обработка ошибок
app.use((error, req, res, next) => {
  console.error('Unhandled error:', error);
  res.status(500).json({ error: 'Внутренняя ошибка сервера' });
});

// Обработка 404 для API
app.use('/api/*', (req, res) => {
  res.status(404).json({ error: 'API маршрут не найден' });
});

app.listen(PORT, () => {
  console.log(`Сервер запущен на порту ${PORT}`);
  console.log(`База данных: online_store1`);
  console.log(`Пользователь БД: store_app1`);
  console.log(`API доступно: http://localhost:${PORT}/api`);
});