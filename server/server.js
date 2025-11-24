import express from 'express';
import cors from 'cors';
import bcrypt from 'bcryptjs';
import { Pool } from 'pg';

const app = express();
const PORT = 5000;

// Настройки CORS (для React на localhost:3000)
app.use(cors({
  origin: ['http://localhost:3000', 'http://127.0.0.1:3000'],
  credentials: true,
}));
app.use(express.json({ limit: '10mb' }));

// === ПОДКЛЮЧЕНИЕ К ПОЛНОСТЬЮ ПУСТОЙ БАЗЕ ===
const pool = new Pool({
  user: 'postgres',           // или store_app1 — как у тебя есть доступ
  host: 'localhost',
  database: 'pc_db',          // любая существующая база (можно online_store1)
  password: '1234',           // твой реальный пароль!
  port: 5432,
});

// Простое in-memory хранилище сессий
const sessions = new Map();
const generateSessionId = () => Math.random().toString(36).substring(2) + Date.now();

// === АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ВСЕХ ТАБЛИЦ ПРИ ЗАПУСКЕ ===
async function initDatabase() {
  const client = await pool.connect();
  try {
    console.log('Создаём схему и таблицы...');

    await client.query(`CREATE SCHEMA IF NOT EXISTS store AUTHORIZATION postgres`);

    // 1. Пользователи
    await client.query(`
      CREATE TABLE IF NOT EXISTS store.users (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        INN VARCHAR(20),
        company_name VARCHAR(255),
        phone_number VARCHAR(50),
        location TEXT,
        role VARCHAR(50) DEFAULT 'user',
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );
    `);

    // 2. Категории (деревовидные)
    await client.query(`
      CREATE TABLE IF NOT EXISTS store.categories (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        parent_id INTEGER REFERENCES store.categories(id),
        level INTEGER DEFAULT 1,
        description TEXT,
        is_active BOOLEAN DEFAULT true,
        sort_order INTEGER DEFAULT 0
      );
    `);

    // 3. Товары
    await client.query(`
      CREATE TABLE IF NOT EXISTS store.products (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        price_per_item DECIMAL(12,2) NOT NULL,
        company VARCHAR(255),
        category_id INTEGER REFERENCES store.categories(id),
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW()
      );
    `);

    // 4. Закупки
    await client.query(`
      CREATE TABLE IF NOT EXISTS store.procurements (
        id SERIAL PRIMARY KEY,
        title VARCHAR(500) NOT NULL,
        description TEXT,
        session_number VARCHAR(100) UNIQUE NOT NULL,
        customer_name VARCHAR(255),
        customer_inn VARCHAR(20),
        current_price DECIMAL(14,2) NOT NULL,
        start_date TIMESTAMPTZ NOT NULL,
        end_date TIMESTAMPTZ NOT NULL,
        law_type VARCHAR(50) DEFAULT '44-ФЗ',
        contract_terms TEXT,
        contract_security TEXT,
        status VARCHAR(50) DEFAULT 'active',
        created_by INTEGER REFERENCES store.users(id),
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
      );
    `);

    // 5. Товары в закупке
    await client.query(`
      CREATE TABLE IF NOT EXISTS store.procurement_products (
        id SERIAL PRIMARY KEY,
        procurement_id INTEGER REFERENCES store.procurements(id) ON DELETE CASCADE,
        product_id INTEGER REFERENCES store.products(id),
        required_quantity INTEGER NOT NULL,
        max_price DECIMAL(14,2),
        created_at TIMESTAMPTZ DEFAULT NOW()
      );
    `);

    // 6. Участие в закупках
    await client.query(`
      CREATE TABLE IF NOT EXISTS store.procurement_participants (
        id SERIAL PRIMARY KEY,
        procurement_id INTEGER REFERENCES store.procurements(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES store.users(id),
        proposed_price DECIMAL(14,2),
        proposal_text TEXT,
        status VARCHAR(50) DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(procurement_id, user_id)
      );
    `);

    console.log('Все таблицы успешно созданы в схеме "store"');
  } catch (err) {
    console.error('Ошибка при создании таблиц:', err.message);
  } finally {
    client.release();
  }
}

// === ЗАПУСК СЕРВЕРА ===
app.listen(PORT, async () => {
  console.log(`Сервер запущен: http://localhost:${PORT}`);
  await initDatabase(); // ← создаём всё автоматически
});

// === МИДЛВАРЫ ===
const checkSession = (req, res, next) => {
  const sessionId = req.headers['session-id'];
  if (!sessionId || !sessions.has(sessionId)) {
    return res.status(401).json({ error: 'Неавторизован' });
  }
  req.user = sessions.get(sessionId); // теперь точно есть .id
  next();
};

// Логирование (по желанию)
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
  next();
});

// === МАРШРУТЫ ===

// Health check
app.get('/api/health', async (req, res) => {
  try {
    const result = await pool.query('SELECT NOW()');
    res.json({ status: 'OK', db_time: result.rows[0].now, sessions: sessions.size });
  } catch (err) {
    res.status(500).json({ error: 'Нет подключения к БД' });
  }
});

// Регистрация
app.post('/api/auth/register', async (req, res) => {
  try {
    const { name, email, password, INN, company_name, phone_number, location } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ error: 'Имя, email и пароль обязательны' });
    }

    const exists = await pool.query('SELECT id FROM store.users WHERE email = $1', [email]);
    if (exists.rows.length > 0) {
      return res.status(400).json({ error: 'Email уже занят' });
    }

    const hash = await bcrypt.hash(password, 10);
    const result = await pool.query(`
      INSERT INTO store.users (name, email, password_hash, INN, company_name, phone_number, location)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING id, name, email, INN, company_name, phone_number, location, role
    `, [name, email, hash, INN, company_name, phone_number, location]);

    const user = result.rows[0];
    const sessionId = generateSessionId();
    sessions.set(sessionId, { id: user.id, email: user.email, role: user.role || 'user' });

    res.json({ message: 'Регистрация успешна', user, sessionId });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Ошибка регистрации' });
  }
});

// Логин
app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const result = await pool.query('SELECT * FROM store.users WHERE email = $1', [email]);
    if (result.rows.length === 0) return res.status(400).json({ error: 'Пользователь не найден' });

    const user = result.rows[0];
    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) return res.status(400).json({ error: 'Неверный пароль' });

    const sessionId = generateSessionId();
    sessions.set(sessionId, { id: user.id, email: user.email, role: user.role });

    res.json({
      message: 'Вход успешен',
      user: { id: user.id, name: user.name, email: user.email, role: user.role },
      sessionId
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Ошибка входа' });
  }
});

// Выход
app.post('/api/auth/logout', checkSession, (req, res) => {
  sessions.delete(req.headers['session-id']);
  res.json({ message: 'Выход выполнен' });
});

// Профиль
app.get('/api/user/profile', checkSession, async (req, res) => {
  try {
    const result = await pool.query('SELECT id, name, email, INN, company_name, phone_number, location, role FROM store.users WHERE id = $1', [req.user.id]);
    if (result.rows.length === 0) return res.status(404).json({ error: 'Пользователь не найден' });
    res.json({ user: result.rows[0] });
  } catch (err) {
    res.status(500).json({ error: 'Ошибка профиля' });
  }
});

// Всё остальное (закупки, товары и т.д.) можешь постепенно добавлять из старого кода
// Главное — теперь база создаётся сама и сессии работают правильно!

console.log('Готов к запуску. Просто выполни: node server.js');